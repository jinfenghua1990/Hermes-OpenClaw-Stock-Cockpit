#!/usr/bin/env python3
"""
position_adapter.py - Phase-1.7 Data Adapter Layer
数据源优先级:
  1. mx_api   东方财富模拟盘（第一数据源）
  2. skill    mx-moni skill 第二输入源
  3. manual   manual_positions.json 兜底

规则:
  - 不自动交易
  - 不自动调仓
  - 不写 strategy_positions
  - 只读取和分析持仓
  - 持仓数据必须进入统一 schema
  - 持仓异常才允许 red_alert
"""
import os
import sys
import json
import requests
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# =============================================================================
# 配置
# =============================================================================
CRON_BASE        = Path.home() / "project_ai_trading"
UNIFIED_SCHEMA   = CRON_BASE / "portfolio" / "unified_positions.json"
MANUAL_POSITIONS = CRON_BASE / "portfolio" / "manual_positions.json"
MX_DATA_DIR      = Path.home() / ".hermes" / "mx_data" / "output"
LOG_FILE         = CRON_BASE / "cron" / "logs" / "position_adapter.log"
CACHE_DIR        = CRON_BASE / "cron" / ".notify_cache"

MX_APIKEY = os.environ.get("MX_APIKEY", "")
MX_API_URL = os.environ.get("MX_API_URL", "https://mkapi2.dfcfs.com/finskillshub")
HERMES_GROUP_ID = "oc_174834d2967c4dfbdd692464f85398e0"

ALLOWED_NOTIFY = {"pre_market", "daily_review", "cron_error", "red_alert"}

# =============================================================================
# 日志
# =============================================================================
def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [position_adapter] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.open("a").write(line + "\n")

# =============================================================================
# 数据源 1: MX API（东方财富模拟盘）
# =============================================================================
def fetch_mx_api() -> tuple[List[dict], dict]:
    """调用东方财富模拟盘持仓API，返回 (持仓列表, 资金信息)"""
    headers = {
        "Content-Type": "application/json",
        "apikey": MX_APIKEY,
        "source": "mx_moni_skill",
    }
    try:
        # 持仓
        r = requests.post(
            f"{MX_API_URL}/api/claw/mockTrading/positions",
            headers=headers, json={"moneyUnit": 1}, timeout=30
        )
        r.raise_for_status()
        result = r.json()
        if result.get("code") == "200":
            data = result.get("data", {})
            pos_list = data.get("posList", [])
            capital = {
                "total_assets":  data.get("totalAssets", 0),
                "avail_balance": data.get("availBalance", 0),
                "total_pos_value": data.get("totalPosValue", 0),
                "pos_count": data.get("posCount", 0),
            }
            log(f"MX API 成功: {len(pos_list)} 只持仓")
            return pos_list, capital
        else:
            log(f"MX API 失败: code={result.get('code')} msg={result.get('message')}")
    except Exception as e:
        log(f"MX API 异常: {e}")
    return [], {}

# =============================================================================
# 数据源 2: mx-moni skill 输出文件
# =============================================================================
def fetch_mx_skill() -> List[dict]:
    """读取 mx-moni skill 缓存的持仓文件"""
    candidates = [
        MX_DATA_DIR / "mx_moni_我的持仓.json",
        MX_DATA_DIR / "mx_moni_持仓.json",
        MX_DATA_DIR / "mx_moni_query.json",
    ]
    for f in candidates:
        if f.exists():
            try:
                data = json.loads(f.read_text())
                # 尝试提取持仓列表（兼容不同格式）
                pos = data.get("data", {}).get("list", []) \
                   or data.get("data", {}).get("posList", []) \
                   or data.get("positions", []) \
                   or data.get("list", [])
                if pos:
                    log(f"MX skill 文件读取成功: {f.name}, {len(pos)} 只")
                    return pos
            except Exception as e:
                log(f"MX skill 文件解析失败 {f.name}: {e}")
    return []

# =============================================================================
# 数据源 3: manual_positions.json 兜底
# =============================================================================
def fetch_manual() -> List[dict]:
    """读取手动维护的持仓文件"""
    if MANUAL_POSITIONS.exists():
        try:
            data = json.loads(MANUAL_POSITIONS.read_text())
            pos = data if isinstance(data, list) else data.get("positions", [])
            log(f"manual_positions 读取: {len(pos)} 只")
            return pos
        except Exception as e:
            log(f"manual_positions 解析失败: {e}")
    return []

# =============================================================================
# 统一 Schema 转换（兼容三种来源格式）
# =============================================================================
def normalize_mx_api(item: dict) -> dict:
    """MX API → 统一 schema（价格单位：分→元）"""
    cost_price_fen = float(item.get("costPrice", 0) or 0)
    current_price_fen = float(item.get("price", 0) or 0)
    return {
        "symbol":       str(item.get("secCode", "")),
        "name":         str(item.get("secName", "")),
        "volume":       int(item.get("count", 0)),
        "avail_volume": int(item.get("availCount", 0)),
        "avg_cost":     round(cost_price_fen / 1000, 3),     # 分→元（costPriceDec=3位小数）
        "current_price":round(current_price_fen / 100, 2),    # 分→元（priceDec=2位小数）
        "market_value": float(item.get("value", 0)),
        "day_profit":   float(item.get("dayProfit", 0)),
        "day_profit_pct": float(item.get("dayProfitPct", 0)),
        "profit":       float(item.get("profit", 0)),
        "profit_ratio": float(item.get("profitPct", 0)),
        "pos_pct":      float(item.get("posPct", 0)),
        "delist":       int(item.get("delist", 0)),
        "source":       "mx_api",
    }

def normalize_mx_skill(item: dict) -> dict:
    """mx-moni skill 文件 → 统一 schema"""
    return {
        "symbol":       str(item.get("stockCode") or item.get("stock_code", "")),
        "name":         str(item.get("stockName") or item.get("stock_name", "")),
        "volume":       int(item.get("enableVolume") or item.get("volume", 0)),
        "avail_volume": int(item.get("enableVolume", 0)),
        "avg_cost":     float(item.get("costPrice") or item.get("cost_price", 0)),
        "current_price":float(item.get("currentPrice") or item.get("current_price", 0)),
        "market_value": float(item.get("marketValue") or item.get("market_value", 0)),
        "profit":       float(item.get("profitLoss") or item.get("profit_loss", 0)),
        "profit_ratio": float(item.get("profitRatio") or item.get("profit_ratio", 0)),
        "source":       "mx_skill",
    }

def normalize_manual(item: dict) -> dict:
    """manual JSON → 统一 schema"""
    return {
        "symbol":        str(item.get("symbol", "")),
        "name":          str(item.get("name", "")),
        "volume":        int(item.get("volume", 0)),
        "avail_volume":  int(item.get("avail_volume", item.get("availCount", 0))),
        "avg_cost":      float(item.get("avg_cost", 0)),
        "current_price": float(item.get("current_price", 0)),
        "market_value":  float(item.get("market_value", 0)),
        "profit":        float(item.get("profit", 0)),
        "profit_ratio":  float(item.get("profit_ratio", 0)),
        "source":        "manual",
    }

# =============================================================================
# Schema 验证
# =============================================================================
def validate(positions: List[dict]) -> dict:
    issues = []
    for i, pos in enumerate(positions):
        s = pos.get("symbol", "")
        if not s:
            issues.append(f"持仓[{i}] 缺少 symbol")
        if pos.get("volume", 0) < 0:
            issues.append(f"{s} volume < 0: {pos['volume']}")
        # avg_cost 允许负数（融资/特殊账户），只检查非数字
        if pos.get("avg_cost") is None:
            issues.append(f"{s} avg_cost 为空")
    return {"valid": len(issues) == 0, "count": len(positions), "issues": issues}

# =============================================================================
# 持仓异常检测 → red_alert
# =============================================================================
def detect_anomalies(positions: List[dict], capital: dict) -> List[dict]:
    alerts = []
    total_mv = capital.get("total_pos_value", sum(p.get("market_value", 0) for p in positions))

    for pos in positions:
        s, n = pos.get("symbol", ""), pos.get("name", "")

        # ── 数据口径异常（不输出真实盈亏判断）────────────────────────────
        # cost_anomaly: 成本 <= 0
        avg_cost = pos.get("avg_cost", 0)
        if avg_cost <= 0:
            alerts.append({"type": "cost_anomaly", "symbol": s, "name": n,
                            "detail": "成本口径异常（≤0），数据仅供参考",
                            "severity": "high"})

        # pnl_anomaly: 盈亏比异常（超出合理范围）
        pr = pos.get("profit_ratio", 0)
        if pr < -1.0 or pr > 3.0:
            alerts.append({"type": "pnl_anomaly", "symbol": s, "name": n,
                            "detail": "盈亏口径异常，数据仅供参考",
                            "severity": "high"})

        # ── 常规风险检测（跳过数据异常持仓）──────────────────────────────
        # 高集中度 > 50%（持仓占比本身正常，但盈亏数据异常时市值也可能不准）
        mv = pos.get("market_value", 0)
        if total_mv > 0 and mv / total_mv > 0.5:
            # 数据异常时集中度指标也不可信，跳过
            if not (avg_cost <= 0 or pr < -1.0 or pr > 3.0):
                alerts.append({"type": "concentration", "symbol": s, "name": n,
                                "detail": f"持仓占比 {mv/total_mv:.1%} > 50%", "severity": "high"})

        # 高亏损 < -20%（数据异常时盈亏不可信，跳过）
        if pr < -0.2:
            if not (avg_cost <= 0 or pr < -1.0 or pr > 3.0):
                alerts.append({"type": "loss_high", "symbol": s, "name": n,
                                "detail": f"亏损 {pr:.1%} < -20%", "severity": "high"})

        # 锁定（持仓>0但无可用）
        if pos.get("volume", 0) > 0 and pos.get("avail_volume", 0) == 0:
            alerts.append({"type": "locked", "symbol": s, "name": n,
                            "detail": "持仓>0但无可用股数（停牌/跌停）", "severity": "medium"})

        # 退市风险
        if pos.get("delist", 0) == 1:
            alerts.append({"type": "delist", "symbol": s, "name": n,
                            "detail": "退市风险标记", "severity": "high"})

    return alerts

# =============================================================================
# 飞书 red_alert（仅异常时）
# =============================================================================
def send_red_alert(alerts: List[dict]) -> bool:
    if not alerts:
        return True
    try:
        lines = [f"【数据异常告警】{len(alerts)} 项"]
        for a in alerts:
            lines.append(f"⚠ {a['symbol']} {a['name']}: {a['detail']}")
        msg = "\n".join(lines)
        result = subprocess.run(
            ["lark-cli", "im", "+messages-send",
             "--chat-id", HERMES_GROUP_ID, "--text", msg],
            capture_output=True, text=True, timeout=30
        )
        ok = result.returncode == 0
        log(f"red_alert 发送: {'成功' if ok else '失败'}")
        return ok
    except Exception as e:
        log(f"red_alert 异常: {e}")
        return False

# =============================================================================
# 飞书通知（pre_market / daily_review）
# =============================================================================
def notify_feishu(notify_type: str, positions: List[dict], capital: dict, anomalies: List[dict]):
    if notify_type not in ALLOWED_NOTIFY:
        return
    cache_file = CACHE_DIR / f"{notify_type}.last"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if cache_file.exists():
        try:
            last = int(cache_file.read_text().strip())
            if datetime.now().timestamp() - last < 300:
                log(f"{notify_type} 冷却中，跳过通知")
                return
        except:
            pass

    try:
        ts = datetime.now().strftime("%H:%M")
        total_mv = capital.get("total_pos_value", 0)
        total_a  = capital.get("total_assets", 0)
        anomaly_symbols = {a["symbol"] for a in anomalies}

        lines = [f"【持仓报告】{ts} {notify_type.replace('_', ' ')}"]
        lines.append(f"持仓: {len(positions)} 只 | 总市值: {total_mv:,.0f} | 总资产: {total_a:,.0f}")

        for pos in positions[:8]:
            s = pos.get("symbol", "")
            if s in anomaly_symbols:
                # 数据异常仓位，不暴露盈亏数值
                lines.append(f"  ⚪ {s} {pos.get('name','')} 持仓:{pos.get('volume',0)}股 数据异常")
            else:
                pr = pos.get("profit_ratio", 0)
                flag = "🔴" if pr < -0.05 else "🟢" if pr > 0.05 else "⚪"
                lines.append(f"  {flag} {s} {pos.get('name','')} "
                             f"持仓:{pos.get('volume',0)}股 "
                             f"盈亏:{pr:+.1%}")

        if len(positions) > 8:
            lines.append(f"  ... 还有 {len(positions)-8} 只")

        msg = "\n".join(lines)
        result = subprocess.run(
            ["lark-cli", "im", "+messages-send",
             "--chat-id", HERMES_GROUP_ID, "--text", msg],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            cache_file.write_text(str(int(datetime.now().timestamp())))
            log(f"{notify_type} 飞书通知已发送")
    except Exception as e:
        log(f"飞书通知异常: {e}")

# =============================================================================
# 主逻辑
# =============================================================================
def main():
    notify_type = sys.argv[1] if len(sys.argv) > 1 else ""
    log(f"=== 开始执行 (notify={notify_type}) ===")

    # ---- 优先级读取 ----
    raw_positions, capital = [], {}
    source = "none"

    # 1. MX API
    raw_positions, capital = fetch_mx_api()
    if raw_positions:
        source = "mx_api"
        log(f"使用数据源: mx_api ({len(raw_positions)} 只)")

    # 2. MX skill 文件
    if not raw_positions:
        skill_data = fetch_mx_skill()
        if skill_data:
            raw_positions = skill_data
            source = "mx_skill"
            log(f"使用数据源: mx_skill ({len(raw_positions)} 只)")

    # 3. manual 兜底
    if not raw_positions:
        raw_positions = fetch_manual()
        source = "manual"
        log(f"使用数据源: manual ({len(raw_positions)} 只)")

    # ---- 统一 Schema 转换 ----
    normalizers = {"mx_api": normalize_mx_api, "mx_skill": normalize_mx_skill, "manual": normalize_manual}
    norm_fn = normalizers.get(source, normalize_manual)
    positions = [norm_fn(p) for p in raw_positions]

    # ---- 验证 ----
    validation = validate(positions)
    log(f"验证: count={validation['count']} valid={validation['valid']}")
    for issue in validation.get("issues", []):
        log(f"  验证问题: {issue}")

    # ---- 异常检测 ----
    anomalies = detect_anomalies(positions, capital)
    if anomalies:
        log(f"⚠️ 持仓异常 {len(anomalies)} 项，发送 red_alert")
        send_red_alert(anomalies)

    # ---- 写入统一 Schema ----
    unified = {
        "schema_version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "data_source": source,
        "data_sources_tried": ["mx_api", "mx_skill", "manual"],
        "data_sources": {
            "mx_api":  {"status": "available" if source=="mx_api" else "no_data"},
            "mx_skill": {"status": "available" if source=="mx_skill" else ("not_found" if source!="mx_api" else "skipped")},
            "manual":  {"status": "available" if source=="manual" else ("not_found" if source not in ["mx_api","mx_skill"] else "skipped")},
        },
        "capital": capital,
        "positions": positions,
        "validation": validation,
        "anomalies": anomalies,
        "trade_prohibited": True,
        "schema_prohibited": ["auto_trade", "auto_rebalance", "strategy_positions_write"],
    }

    UNIFIED_SCHEMA.parent.mkdir(parents=True, exist_ok=True)
    UNIFIED_SCHEMA.write_text(json.dumps(unified, ensure_ascii=False, indent=2))
    log(f"✓ 统一持仓已写入: {UNIFIED_SCHEMA}")
    log(f"   positions: {len(positions)} 只 | source: {source}")

    # ---- 盘前/盘后通知 ----
    if notify_type in ("pre_market", "daily_review"):
        notify_feishu(notify_type, positions, capital, anomalies)

    # Runtime Event
    try:
        sys.path.insert(0, str(BASE_DIR))
        from runtime_events.runtime_event_logger import log_event
        has_anomaly = len(anomalies) > 0
        log_event(
            module="position_adapter",
            layer="execution_layer",
            status="warning" if has_anomaly else "success",
            message=f"positions={len(positions)} source={source}" + (f" anomalies={len(anomalies)}" if has_anomaly else ""),
        )
    except ImportError:
        pass

    return unified

if __name__ == "__main__":
    main()
