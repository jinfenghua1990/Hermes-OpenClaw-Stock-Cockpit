#!/usr/bin/env python3
"""
event_engine.py - Phase-1.8 Event Engine 盘中事件提醒层
监控: 指数异动 | 持仓异动 | 跌破 MA5 | 放量异常
输出: portfolio/events.json
飞书: 仅推送 red_alert / important_event（10分钟同类去重）
"""
import os, sys, json, subprocess, glob
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# =============================================================================
# 配置
# =============================================================================
CRON_BASE       = Path.home() / "project_ai_trading"
MX_OUT_DIR      = Path.home() / "mx_data_output"
EVENTS_FILE     = CRON_BASE / "portfolio" / "events.json"
UNIFIED_POS     = CRON_BASE / "portfolio" / "unified_positions.json"
CACHE_DIR       = CRON_BASE / "cron" / ".event_cache"
LOG_FILE        = CRON_BASE / "cron" / "logs" / "event_engine.log"
HERMES_GROUP_ID = "oc_174834d2967c4dfbdd692464f85398e0"

# 指数代码（东方财富格式）
INDEX_CODES = [
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
    ("000688.SH", "科创50"),
    ("000300.SH", "沪深300"),
]

# MA5 数据文件 key（不同股票文件名略有差异）
MA5_FILE_PATTERNS = [
    "mx_data_{name}_{code}_MA5_MA20_RSI_量比_raw.json",
    "mx_data_{code}_MA5_MA20_RSI_量比_raw.json",
]

RULE = {
    "index_move_threshold":  1.0,    # 指数涨跌幅 > ±1% → red_alert
    "volume_ratio_high":     2.0,    # 量比 > 2x → important_event
    "volume_ratio_low":       0.5,    # 量比 < 0.5x → important_event（缩量）
    "ma5_breakdown_pct":    -1.0,    # 现价 < MA5 × (1 - threshold) → important_event
    "ma5_breakup_pct":       1.0,    # 现价 > MA5 × (1 + threshold) → important_event
    "circuit_break":          9.7,    # 涨跌幅 > ±9.7% → red_alert（涨跌停）
}

CACHE_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 日志
# =============================================================================
def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [event_engine] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.open("a").write(line + "\n")

# =============================================================================
# 工具函数
# =============================================================================
def pct_to_float(s: str) -> float:
    """'3.88%' → 3.88, '-0.29%' → -0.29"""
    try:
        return float(s.strip().replace("%", ""))
    except:
        return 0.0

def latest_value(raw_arr: list) -> float:
    """取数组最后一位（最新交易日）"""
    try:
        return float(raw_arr[-1])
    except:
        return 0.0

def prev_value(raw_arr: list, offset: int = 1) -> float:
    try:
        return float(raw_arr[-(offset + 1)])
    except:
        return 0.0

# =============================================================================
# MX 数据文件解析
# =============================================================================
def load_raw_json(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        return json.loads(text)
    except Exception:
        return {}

def parse_mx_table(raw: dict) -> Dict[str, list]:
    """从 mx raw.json 提取 dataTableDTOList[0].rawTable
    注意：数据路径是 data → data → searchDataResultDTO（双重嵌套）"""
    try:
        # 双重 data 嵌套
        d = raw.get("data", {})
        dd = d.get("data", d)  # 兼容单层或双层
        sds = dd.get("searchDataResultDTO", {})
        dtl = sds.get("dataTableDTOList", [])
        if not dtl:
            return {}
        return dtl[0].get("rawTable", {})
    except:
        return {}

# =============================================================================
# 数据读取
# =============================================================================
def read_index_data() -> List[dict]:
    """读取最新指数数据，同一指数取文件修改时间最新的那份数据"""
    results = {}  # code -> (data, mtime)

    all_files = list(MX_OUT_DIR.glob("*.json"))
    index_files = [
        f for f in all_files
        if f.name.endswith("_raw.json")
        and "指数" in f.name
        and ("最新价" in f.name or "涨跌幅" in f.name)
    ]

    for f in index_files:
        raw = load_raw_json(f)
        table = parse_mx_table(raw)
        if not table:
            continue

        f2_vals = table.get("f2", [])
        f3_vals = table.get("f3", [])
        head_names = table.get("headName", [])

        for i, name in enumerate(head_names):
            if not name or i >= len(f2_vals):
                continue

            price = float(f2_vals[i]) if f2_vals and i < len(f2_vals) else 0
            pct   = pct_to_float(f3_vals[i]) if f3_vals and i < len(f3_vals) else 0.0

            matched = None
            for code, label in INDEX_CODES:
                if label in name or code in name:
                    matched = (code, label)
                    break
            if not matched:
                continue

            code, label = matched
            mtime = f.stat().st_mtime

            if code not in results or mtime > results[code][1]:
                results[code] = ({"code": code, "name": label, "price": price, "pct": pct}, mtime)

    return [v[0] for v in results.values()]

def read_stock_ma5_data(code: str, name: str = "") -> Dict[str, float]:
    """读取单只股票的 MA5 / MA20 / 量比 / 最新价"""
    row = {"ma5": None, "ma20": None, "vol_ratio": None, "current_price": None, "pct_change": None}

    # 尝试多个文件名模式
    patterns = [
        f"mx_data_{name}_{code}_MA5_MA20_RSI_量比_raw.json",
        f"mx_data_{code}_MA5_MA20_RSI_量比_raw.json",
        f"mx_data_{name}_*_MA5_MA20_RSI_量比_raw.json",
        f"mx_data_*_{code}_*RSI*量比*_raw.json",
    ]

    for pattern in patterns:
        hits = list(MX_OUT_DIR.glob(pattern))
        if not hits:
            continue
        raw = load_raw_json(hits[0])
        table = parse_mx_table(raw)
        if not table:
            continue

        # 找到字段映射
        name_map = {}
        try:
            # 双重 data 嵌套
            d = raw.get("data", {})
            dd = d.get("data", d)
            dtl = dd.get("searchDataResultDTO", {}).get("dataTableDTOList", [])
            if dtl:
                name_map = dtl[0].get("nameMap", {})
        except:
            pass

        # rawTable 的 key 是原始字段名，value 是 [val_today, val_yesterday, ...]
        for field_key, values in table.items():
            if not isinstance(values, list) or len(values) == 0:
                continue
            label = name_map.get(field_key, "")

            if "5日MA" in label or "MA5" in label.upper():
                row["ma5"] = latest_value(values)
            elif "20日MA" in label or "MA20" in label.upper():
                row["ma20"] = latest_value(values)
            elif "量比" in label:
                row["vol_ratio"] = latest_value(values)
            elif "RSI" in label.upper():
                pass  # 暂不用于事件检测

        # 尝试读最新价（涨跌停用）
        price_files = list(MX_OUT_DIR.glob(f"mx_data_*{name}*{code}*最新价*raw.json")) + \
                      list(MX_OUT_DIR.glob(f"mx_data_{code}*最新价*raw.json"))
        for pf in price_files:
            raw2 = load_raw_json(pf)
            t2 = parse_mx_table(raw2)
            if "f2" in t2 and t2["f2"]:
                row["current_price"] = float(t2["f2"][0])
                break

        # 尝试读涨跌幅
        pct_files = list(MX_OUT_DIR.glob(f"mx_data_*{name}*涨跌幅*raw.json"))
        for pf in pct_files:
            raw2 = load_raw_json(pf)
            t2 = parse_mx_table(raw2)
            if "f3" in t2 and t2["f3"]:
                row["pct_change"] = pct_to_float(t2["f3"][0])
                break

        break  # 找到即返回

    return row

# =============================================================================
# 事件检测
# =============================================================================
def detect_index_events(indices: List[dict]) -> List[dict]:
    events = []
    for idx in indices:
        pct = idx["pct"]
        abs_pct = abs(pct)
        if abs_pct >= RULE["circuit_break"]:
            events.append({
                "type": "index_circuit_break",
                "level": "red_alert",
                "index": idx["name"],
                "detail": f"指数异动 {pct:+.2f}%（涨跌停区域）",
            })
        elif abs_pct >= RULE["index_move_threshold"]:
            events.append({
                "type": "index_move",
                "level": "red_alert",
                "index": idx["name"],
                "detail": f"指数异动 {pct:+.2f}%（阈值 ±{RULE['index_move_threshold']}%）",
            })
    return events

def detect_position_events(positions: List[dict], market_data: Dict[str, dict]) -> List[dict]:
    """
    持仓股票事件检测：
    - 跌破 MA5（重要信号）
    - 放量异常（量比 > 2 或 < 0.5）
    - 涨跌停
    注意：不输出盈亏数字，口径异常仓位跳过
    """
    events = []
    anomaly_symbols = set()
    # 从 unified_positions 已知异常的仓位
    try:
        if UNIFIED_POS.exists():
            unified = json.loads(UNIFIED_POS.read_text())
            anomaly_symbols = {a["symbol"] for a in unified.get("anomalies", [])}
    except:
        pass

    for pos in positions:
        s = pos.get("symbol", "")
        n = pos.get("name", "")

        # 跳过数据异常仓位
        if s in anomaly_symbols:
            continue

        # 跳过没有 market_data 的股票
        if s not in market_data:
            continue

        m = market_data[s]
        price   = m.get("current_price") or m.get("price") or 0
        ma5     = m.get("ma5")
        vol_r   = m.get("vol_ratio")
        pct     = m.get("pct_change")

        # 涨跌停
        if pct is not None and abs(pct) >= RULE["circuit_break"]:
            events.append({
                "type": "stock_circuit_break",
                "level": "red_alert",
                "symbol": s,
                "name": n,
                "detail": f"涨跌幅 {pct:+.2f}%（涨跌停区域）",
            })
            continue

        # 跌破 MA5
        if ma5 is not None and price and price > 0 and ma5 > 0:
            if price < ma5 * (1 - RULE["ma5_breakdown_pct"] / 100):
                events.append({
                    "type": "ma5_breakdown",
                    "level": "important_event",
                    "symbol": s,
                    "name": n,
                    "detail": f"现价 {price:.2f} < MA5 {ma5:.2f}（跌破 {RULE['ma5_breakdown_pct']}%）",
                })
            elif price > ma5 * (1 + RULE["ma5_breakup_pct"] / 100):
                events.append({
                    "type": "ma5_breakup",
                    "level": "important_event",
                    "symbol": s,
                    "name": n,
                    "detail": f"现价 {price:.2f} > MA5 {ma5:.2f}（突破 +{RULE['ma5_breakup_pct']}%）",
                })

        # 放量/缩量异常
        if vol_r is not None:
            if vol_r >= RULE["volume_ratio_high"]:
                events.append({
                    "type": "volume_surge",
                    "level": "important_event",
                    "symbol": s,
                    "name": n,
                    "detail": f"量比 {vol_r:.2f}x > {RULE['volume_ratio_high']}x（放量）",
                })
            elif vol_r <= RULE["volume_ratio_low"]:
                events.append({
                    "type": "volume_shrink",
                    "level": "important_event",
                    "symbol": s,
                    "name": n,
                    "detail": f"量比 {vol_r:.2f}x < {RULE['volume_ratio_low']}x（缩量）",
                })

    return events

# =============================================================================
# 飞书推送（同类10分钟去重）
# =============================================================================
def feishu_notify(events: List[dict]):
    for ev in events:
        if ev["level"] not in ("red_alert", "important_event"):
            continue

        cache_file = CACHE_DIR / f"{ev['type']}_{ev.get('symbol', ev.get('index', ''))}.last"
        now = int(datetime.now().timestamp())

        if cache_file.exists():
            try:
                last = int(cache_file.read_text().strip())
                if now - last < 600:  # 10分钟
                    log(f"去重跳过: {ev['type']} {ev.get('symbol','')}")
                    continue
            except:
                pass

        # 发送
        icon = "🚨" if ev["level"] == "red_alert" else "📋"
        if "index" in ev:
            msg = f"{icon}【{ev['level'].replace('_',' ')}】{ev['index']}: {ev['detail']}"
        else:
            msg = f"{icon}【{ev['level'].replace('_',' ')}】{ev['symbol']} {ev.get('name','')}: {ev['detail']}"

        try:
            result = subprocess.run(
                ["lark-cli", "im", "+messages-send",
                 "--chat-id", HERMES_GROUP_ID, "--text", msg],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                cache_file.write_text(str(now))
                log(f"飞书推送成功: {ev['type']} {ev.get('symbol','')}")
            else:
                log(f"飞书推送失败: {result.stderr[:100]}")
        except Exception as e:
            log(f"飞书异常: {e}")

# =============================================================================
# 主逻辑
# =============================================================================
def main():
    log("=== Phase-1.8 Event Engine 开始 ===")

    # 1. 读取持仓
    positions = []
    try:
        if UNIFIED_POS.exists():
            unified = json.loads(UNIFIED_POS.read_text())
            positions = unified.get("positions", [])
            log(f"持仓读取: {len(positions)} 只")
    except Exception as e:
        log(f"读取 unified_positions 失败: {e}")

    # 2. 读取指数数据
    indices = read_index_data()
    log(f"指数数据: {[x['name'] for x in indices]}")

    # 3. 读取持仓股票的市场数据
    market_data = {}
    for pos in positions:
        s = pos.get("symbol", "")
        n = pos.get("name", "")
        if s:
            data = read_stock_ma5_data(s, n)
            if data.get("ma5") is not None or data.get("vol_ratio") is not None:
                market_data[s] = data
                log(f"  {s} {n}: ma5={data.get('ma5')}, vol={data.get('vol_ratio')}, price={data.get('current_price')}")

    # 4. 检测事件
    idx_events  = detect_index_events(indices)
    pos_events = detect_position_events(positions, market_data)
    all_events = idx_events + pos_events

    log(f"事件检测: 指数={len(idx_events)} 持仓={len(pos_events)}")

    # 5. 输出 events.json
    output = {
        "schema_version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "phase": "Phase-1.8 OBSERVE_ONLY",
        "trade_prohibited": True,
        "events": all_events,
        "event_counts": {
            "total": len(all_events),
            "red_alert": sum(1 for e in all_events if e["level"] == "red_alert"),
            "important_event": sum(1 for e in all_events if e["level"] == "important_event"),
        },
        "indices_snapshot": indices,
        "market_data_keys": list(market_data.keys()),
    }

    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    EVENTS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    log(f"✓ events.json 已写入: {EVENTS_FILE}")

    # 6. 飞书推送（去重）
    feishu_notify(all_events)

    # Runtime Event
    try:
        sys.path.insert(0, str(CRON_BASE))
        from runtime_events.runtime_event_logger import log_event
        ec = output["event_counts"]
        status = "success"
        if ec["red_alert"] > 0:
            status = "warning"
        log_event(
            module="event_engine",
            layer="governance_layer",
            status=status,
            message=f"{ec['total']} events: {ec['red_alert']} red_alert, {ec['important_event']} important",
        )
    except ImportError:
        pass

    return output

if __name__ == "__main__":
    main()
