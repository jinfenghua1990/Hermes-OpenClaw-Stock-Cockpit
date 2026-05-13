#!/usr/bin/env python3
"""
paper_trade_executor.py - Phase-2.2 AI Stock Cockpit (SAFE_OBSERVE)
Broker: eastmoney_mock | Mode: paper_only | real_trade_prohibited = true
不读取、不操作国信证券接口

熔断机制:
  - 连续3笔亏损 → 暂停新开仓半天
  - 同一股票最多加仓2次
  - 单日最大10笔
价格分层仓位:
  - >300元: 禁止交易
  - 200~300元: 最大30%，建议100~300股
  - 100~200元: 最大50%，建议100~500股
  - <100元: 最大70%，建议100~1000股
"""
import os, sys, json, subprocess, time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# =============================================================================
# 配置
# =============================================================================
CRON_BASE        = Path.home() / "project_ai_trading"
MX_OUT_DIR       = Path.home() / "mx_data_output"
UNIFIED_POS      = CRON_BASE / "portfolio" / "unified_positions.json"
EVENTS_FILE      = CRON_BASE / "portfolio" / "events.json"
CANDIDATE_FILE   = CRON_BASE / "configs" / "candidate_stocks.json"
CAND_RANKINGS    = CRON_BASE / "portfolio" / "candidate_rankings.json"
SHADOW_PORTFOLIO = CRON_BASE / "portfolio" / "shadow_portfolio.json"
TRADE_LOG        = CRON_BASE / "portfolio" / "trade_log.json"
DECISION_LOG     = CRON_BASE / "reports"  / "paper_decision_log.json"
REGIME_JSON      = CRON_BASE / "market" / "market_regime.json"
KILL_SWITCH_J    = CRON_BASE / "config" / "paper_trade_enabled.json"
LOG_FILE         = CRON_BASE / "cron" / "logs" / "paper_trade.log"
HERMES_GROUP_ID  = "oc_174834d2967c4dfbdd692464f85398e0"

# ── Phase-1.9B 核心参数 ────────────────────────────────────────────────
MX_APIKEY = os.environ.get("MX_APIKEY", "")
MX_API_URL = os.environ.get("MX_API_URL", "https://mkapi2.dfcfs.com/finskillshub")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 日志
# =============================================================================
def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [{level}] {msg}"
    print(line)
    LOG_FILE.open("a").write(line + "\n")

# =============================================================================
# 工具
# =============================================================================
def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except:
        return {}

def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def load_json_safe(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except:
        return None

def mx_post(endpoint: str, body: dict) -> dict:
    import requests
    url = f"{MX_API_URL}{endpoint}"
    headers = {"apikey": MX_APIKEY}
    try:
        r = requests.post(url, headers=headers, json=body, timeout=20)
        return r.json()
    except Exception as e:
        return {"success": False, "message": str(e)}

# =============================================================================
# 1. kill_switch 检查
# =============================================================================
def check_kill_switch() -> bool:
    env_val = os.environ.get("KILL_SWITCH", "").strip().lower()
    if env_val != "true":
        return False
    # JSON 文件作为二级保障
    if KILL_SWITCH_J.exists():
        cfg = load_json(KILL_SWITCH_J)
        if not cfg.get("enabled", False):
            return False
    return True

# =============================================================================
# 2. 前置条件
# =============================================================================
def check_prerequisites() -> tuple[bool, str]:
    missing = []
    for f, name in [(UNIFIED_POS, "unified_positions.json"),
                     (EVENTS_FILE, "events.json")]:
        if not f.exists():
            missing.append(name)
    if missing:
        return False, f"前置文件缺失: {missing}"
    return True, "OK"

# =============================================================================
# 3. 价格分层仓位
# =============================================================================
PRICE_TIER = [
    (300, 99999, {"max_pct": 0.00, "suggest": []}),   # >300 禁止
    (200, 300,   {"max_pct": 0.30, "suggest": [100, 200, 300]}),
    (100, 200,   {"max_pct": 0.50, "suggest": [100, 200, 300, 500]}),
    (0,   100,   {"max_pct": 0.70, "suggest": [100, 200, 300, 500, 1000]}),
]

def get_price_tier(price: float) -> dict:
    for lo, hi, tier in PRICE_TIER:
        if lo < price <= hi:
            return tier
    return {"max_pct": 0.0, "suggest": []}   # 价格异常

def calc_position(price: float, total_assets: float,
                  cur_pct: float, avail_cash: float,
                  aggressive: bool = False) -> tuple[int, str]:
    """计算建议仓位，返回 (手数, 说明)"""
    tier = get_price_tier(price)
    max_pct = tier["max_pct"]
    if max_pct <= 0:
        return 0, "股价>300元，禁止交易"

    max_pct_eff = max_pct * (1.5 if aggressive else 1.0)  # 强信号可激进
    max_pct_eff = min(max_pct_eff, 0.70)   # 上限70%

    max_cost   = avail_cash * 0.95
    max_by_pct = total_assets * max_pct_eff
    max_by_cur = total_assets * max_pct_eff - cur_pct * total_assets

    budget = min(max_cost, max_by_pct, max_by_cur)
    if budget <= 0:
        return 0, f"资金不足(可用{avail_cash:.0f}元)"

    vol = int(budget / price / 100) * 100
    if vol < 100:
        return 0, f"可用资金不足（{avail_cash:.0f}元）"

    # 选取建议档位中最接近但≥1手的
    suggest = tier["suggest"]
    if aggressive:
        # 激进：选最大可用档位
        chosen = max([v for v in suggest if v <= vol], default=suggest[0] if suggest else 100)
    else:
        # 正常：选最小可用档位
        chosen = min([v for v in suggest if v <= vol], default=100)

    return chosen, f"建议{int(chosen*price)}元/{chosen}股({max_pct_eff:.0%}仓位)"

# =============================================================================
# 4. 读取数据
# =============================================================================
def load_portfolio() -> dict:
    return load_json(UNIFIED_POS)

def load_events() -> dict:
    return load_json(EVENTS_FILE)

def load_trade_log() -> dict:
    if TRADE_LOG.exists():
        return load_json(TRADE_LOG)
    return {"trades": [], "rejects": [], "consecutive_loss": 0,
            "fuse_triggered_at": None, "add_positions": {}}

def get_today_trades(log: dict) -> List[dict]:
    today = date.today().isoformat()
    return [t for t in log.get("trades", []) if t.get("trade_date") == today]

# =============================================================================
# 5. 熔断检查
# =============================================================================
def check_circuit_break(log: dict) -> tuple[bool, str]:
    """检查是否触发熔断"""
    today = date.today().isoformat()

    # 1. 连续3笔亏损 → 暂停半天
    cl = log.get("consecutive_loss", 0)
    fuse_ts = log.get("fuse_triggered_at")
    if cl >= 3 and fuse_ts:
        # 暂停半天
        fuse_date = datetime.fromisoformat(fuse_ts).date()
        if (date.today() - fuse_date) < timedelta(hours=4):
            return False, f"熔断: 连续{cl}笔亏损，暂停至{(fuse_date+timedelta(hours=4))}"
        else:
            # 熔断已过，重置
            log["consecutive_loss"] = 0
            log["fuse_triggered_at"] = None

    # 2. 单日最大10笔
    today_trades = get_today_trades(log)
    if len(today_trades) >= 10:
        return False, f"熔断: 今日{len(today_trades)}/10笔已达上限"

    return True, "OK"

# =============================================================================
# 5b. 防重复买入（SAFE_OBSERVE 核心保护）
# =============================================================================
def get_today_buy_count(symbol: str, log: dict) -> int:
    """返回该股今日买入次数（含首次+加仓）"""
    today = date.today().isoformat()
    return sum(
        1 for t in log.get("trades", [])
        if t.get("trade_date") == today
        and t.get("action") == "buy"
        and t.get("symbol") == symbol
    )

def check_repeat_buy(symbol: str, action: str, log: dict,
                     pos_count: int, new_signal: bool = False) -> tuple[bool, str]:
    """
    防重复买入核心检查（SAFE_OBSERVE 规则）：
    - 同一股票同一信号不能重复买
    - 已有持仓时，只有 new_signal=True 才允许加仓
    - 每只股票当天最多：首次买入1次 + 逻辑加仓最多2次
    - 金禄电子/沪电股份/利通电子今日已达上限
    """
    if action != "buy":
        return True, "OK"

    today_buys = get_today_buy_count(symbol, log)

    # 今日已买过的股票，禁止再次买入（无论什么信号）
    if today_buys > 0 and not new_signal:
        return False, f"今日已买{today_buys}次，禁止重复买入"

    # 今日已买次数超限（首次1+加仓2=最多3次）
    if today_buys >= 3:
        return False, f"今日已买{today_buys}次，超过上限3次"

    # 已有持仓时，必须是由新信号触发的加仓
    if pos_count > 0 and not new_signal:
        return False, "已有持仓，无新信号禁止加仓"

    # 硬性禁止股票名单（今日已达上限）
    PROHIBITED_TODAY = {"301282", "002463", "603629"}
    if symbol in PROHIBITED_TODAY:
        return False, f"{symbol} 今日已达买入上限，禁止继续买入"

    return True, "OK"

def check_add_position_limit(symbol: str, log: dict) -> tuple[bool, int]:
    """检查加仓次数限制，返回 (可加仓, 已加仓次数)"""
    adds = log.get("add_positions", {}).get(symbol, 0)
    return adds < 2, adds

# =============================================================================
# 6. 读取持仓股最新价
# =============================================================================
def get_stock_price(symbol: str, name: str = "") -> Optional[float]:
    for pat in [
        f"mx_data_*{symbol}*最新价*raw.json",
        f"mx_data_{name}*{symbol}*raw.json",
    ]:
        hits = list(MX_OUT_DIR.glob(pat))
        if not hits:
            continue
        latest = max(hits, key=lambda f: f.stat().st_mtime)
        raw = load_json(latest)
        try:
            dtl = (raw.get("data", {}).get("data", {})
                   .get("searchDataResultDTO", {})
                   .get("dataTableDTOList", []))
            if dtl:
                f2 = dtl[0].get("rawTable", {}).get("f2", [])
                if f2:
                    return float(f2[0])
        except:
            pass
    return None

# =============================================================================
# 7. 策略 baseline
# =============================================================================
BASELINE = {
    "mode_1": {"name": "放量突破MA5",    "signal": "buy",  "aggressive": False},
    "mode_2": {"name": "指数共振跟涨",    "signal": "buy",  "aggressive": True},
    "mode_3": {"name": "超跌反弹",        "signal": "buy",  "aggressive": False},
    "mode_4": {"name": "止损/换仓",       "signal": "sell", "aggressive": False},
    "phase2_candidate": {"name": "AI选股候选",  "signal": "buy",  "aggressive": True},
    "phase2_decision": {"name": "Paper决策层", "signal": "buy",  "aggressive": True},
}

# =============================================================================
# 8. 生成候选信号
# =============================================================================
def load_cand_rankings() -> dict:
    if CAND_RANKINGS.exists():
        return load_json(CAND_RANKINGS)
    return {}

def load_decision_log() -> dict:
    return load_json(DECISION_LOG)

def generate_candidates_from_decision(unified: dict, events: dict) -> List[dict]:
    """Phase-2.6B: 从 paper_decision_log.json 读取决策，不再直接读 top_picks"""
    decision_data = load_decision_log()
    decisions = decision_data.get("decisions", [])

    # 过滤出 paper_buy / paper_sell
    candidates = []
    for d in decisions:
        if d.get("decision") not in ("paper_buy", "paper_sell"):
            continue
        sym = d.get("股票代码", "")
        name = d.get("股票名称", "")
        action = "buy" if d.get("action") == "buy" else "sell"
        reason = d.get("reason", "")
        mode = "phase2_decision"

        candidates.append({
            "mode":       mode,
            "action":     action,
            "symbol":     sym,
            "name":       name,
            "reason":     reason,
            "price":      None,          # 需要另外查
            "shares":     d.get("建议股数", 0),
            "pattern":    d.get("所属模式", ""),
            "score":      d.get("AI评分", 0),
            "event":      None,
            "aggressive": d.get("AI评分", 0) >= 90,
            "rsi":        d.get("RSI", 50),
            "position_mult": 1.0,
            "sector_notes": "",
        })
    return candidates
    """Phase-2.0: 从 candidate_rankings.json 读取候选信号
    同时保留持仓止损的 event-driven 逻辑"""
    candidates = []
    positions   = unified.get("positions", [])
    all_events  = events.get("events", [])
    anomaly_syms = {a["symbol"] for a in unified.get("anomalies", [])}
    held_syms   = {pos["symbol"] for pos in positions
                   if pos.get("volume", 0) > 0}

    # ── 1. 持仓止损检查（保留 event-driven）─────────────────────────
    for pos in positions:
        sym = pos.get("symbol", "")
        if sym in anomaly_syms:
            continue
        for ev in all_events:
            if ev.get("symbol") == sym and ev.get("type") == "ma5_breakdown":
                candidates.append({
                    "mode": "mode_4", "action": "sell",
                    "symbol": sym, "name": pos.get("name",""),
                    "reason": f"MA5止损: {ev['detail']}",
                    "event": ev,
                })

    # ── 2. Phase-2.0: 从 candidate_rankings.json 读取候选买入信号 ──
    cand_data = load_cand_rankings()
    for c in cand_data.get("candidates", []):
        sym  = c.get("股票代码", "")
        name = c.get("股票名称", "")
        if not c.get("允许模拟买入", False):
            continue
        if sym in anomaly_syms:
            continue
        # 已有持仓不重复买入（允许加仓由 add_positions 控制）
        if sym in held_syms:
            # 检查加仓次数
            trade_log = load_trade_log()
            ok_add, add_cnt = check_add_position_limit(sym, trade_log)
            if not ok_add:
                continue
            action = "buy"   # 加仓
        else:
            action = "buy"   # 新开仓

        candidates.append({
            "mode":       "phase2_candidate",
            "action":     action,
            "symbol":     sym,
            "name":       name,
            "reason":     c.get("AI理由", ""),
            "price":      c.get("最新价"),
            "shares":     c.get("建议股数", 0),
            "pattern":    c.get("模式", ""),
            "score":      c.get("综合评分", 0),
            "event":      None,
            "aggressive": c.get("综合评分", 0) >= 90,
            # Phase-2.1 新增
            "rsi":         c.get("RSI"),
            "position_mult": c.get("position_multiplier", 1.0),
            "sector_notes": c.get("板块/市场联动说明", ""),
        })

    # ── 3. 去重（同一股票只保留最高评分）───────────────────────────
    seen = {}
    for c in candidates:
        key = (c["symbol"], c["action"])
        if key not in seen or c.get("score", 0) > seen[key].get("score", 0):
            seen[key] = c
    return list(seen.values())

# =============================================================================
# 9. 风控总检查
# =============================================================================
def check_risk_full(symbol: str, action: str, price: float,
                     unified: dict, trade_log: dict) -> tuple[bool, str, dict]:
    tier = get_price_tier(price)
    if tier["max_pct"] <= 0:
        return False, "股价>300元禁止交易", {}

    # 数据异常
    anomaly_syms = {a["symbol"] for a in unified.get("anomalies", [])}
    if symbol in anomaly_syms:
        return False, "数据异常禁止交易", {}

    # Event Engine 异常
    events_data = load_events()
    error_events = [e for e in events_data.get("events",[])
                    if e.get("type") == "system_error"]
    if error_events:
        return False, f"Event Engine异常: {error_events[0].get('detail')}", {}

    positions   = unified.get("positions", [])
    capital     = unified.get("capital", {})
    total_assets= capital.get("total_assets", 1)
    avail_cash  = capital.get("avail_balance", 0)
    total_mv    = capital.get("total_pos_value", 0)

    # 当前仓位
    cur_pct = 0.0
    for pos in positions:
        if pos.get("symbol") == symbol:
            cur_pct = pos.get("market_value", 0) / total_mv if total_mv > 0 else 0
            break

    # 熔断
    ok, msg = check_circuit_break(trade_log)
    if not ok:
        return False, msg, {}

    # 加仓次数
    if action == "buy":
        ok_add, add_cnt = check_add_position_limit(symbol, trade_log)
        if not ok_add:
            return False, f"该股已加仓{add_cnt}次(上限2次)", {}

    # 卖出检查
    if action == "sell":
        for pos in positions:
            if pos.get("symbol") == symbol:
                avail = pos.get("avail_volume", 0)
                if avail < 100:
                    return False, f"无可卖仓位({avail}股)", {}
                return True, "OK", {
                    "avail_volume": avail, "cur_pct": cur_pct,
                    "max_pct": tier["max_pct"],
                }

    # 买入计算
    vol, pos_note = calc_position(
        price, total_assets, cur_pct, avail_cash,
        aggressive=action == "buy"
    )
    if vol <= 0:
        return False, pos_note, {}

    return True, "OK", {
        "suggest_vol":  vol,
        "cur_pct":      cur_pct,
        "max_pct":      tier["max_pct"],
        "pos_note":     pos_note,
        "avail_cash":   avail_cash,
        "total_assets": total_assets,
    }

# =============================================================================
# 10. MX 模拟交易 API
# =============================================================================
def mx_trade(action: str, symbol: str, price: float,
             quantity: int, order_id: str) -> dict:
    body = {
        "type": action,   # "buy" or "sell"
        "stockCode": symbol,
        "price": price,
        "quantity": quantity,
    }
    result = mx_post("/api/claw/mockTrading/trade", body)
    # 东方财富 MX API 返回结构：
    #   code="200" + message="成功" → 成功
    #   data.result.status=0        → 成交成功
    #   data.orderID                → 真实委托单号
    #   注意：模拟盘不返回真实成交数量，以提交数量为准
    code    = str(result.get("code", ""))
    msg_txt = result.get("message", "")
    data    = result.get("data", {}) or {}
    inner   = data.get("result", {}) if isinstance(data, dict) else {}
    orderid = data.get("orderID", "") or order_id

    # 东方财富 MX API 成功条件：code="200" 且有 orderID
    ok = (code == "200" and bool(orderid))

    return {
        "order_id":     orderid,
        "success":      ok,
        "message":      msg_txt or result.get("message", ""),
        "filled_qty":   quantity if ok else 0,   # 模拟盘以提交数计
        "filled_price": price,
    }

# =============================================================================
# 11. 飞书通知
# =============================================================================
def feishu(msg: str):
    try:
        subprocess.run(
            ["lark-cli", "im", "+messages-send",
             "--chat-id", HERMES_GROUP_ID, "--text", msg],
            capture_output=True, timeout=30
        )
    except Exception as e:
        log(f"飞书通知失败: {e}", "WARN")

NOTIFY_COOLDOWN = {}   # 去重追踪

def feishu_notify(msg: str, key: str = "", cooldown: int = 300):
    """带去重的飞书通知，cooldown秒内同key不重复推送"""
    now = time.time()
    if key:
        last = NOTIFY_COOLDOWN.get(key, 0)
        if now - last < cooldown:
            log(f"[去重] {key} ({cooldown}s冷却中，跳过)", "WARN")
            return
        NOTIFY_COOLDOWN[key] = now
    feishu(msg)

def feishu_buy(symbol: str, name: str, price: float, vol: int,
               mode: str, reason: str,
               submitted_vol: int = 0,
               reject_reason: str = "",
               cap_reason: str = ""):
    if reject_reason:
        # ── 拒单 ──────────────────────────────────────────────────────
        lines = [
            f"🚫 【模拟买入失败】",
            f"股票：{symbol} {name}",
            f"失败原因：{reject_reason}",
            f"触发模式：{BASELINE[mode]['name']}",
            f"触发原因：{reason}",
        ]
        if submitted_vol > 0:
            lines.append(f"拟买入数量：{submitted_vol}股（被拒）")
        if cap_reason:
            lines.append(f"截断原因：{cap_reason}")
        lines.append(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        feishu_notify("\n".join(lines), key=f"reject_{symbol}", cooldown=60)
        return

    if vol < submitted_vol:
        # ── 部分成交 ─────────────────────────────────────────────────
        amount = vol * price
        lines = [
            f"🟡 【模拟买入部分成交】",
            f"股票：{symbol} {name}",
            f"成交数量：{vol}股",
            f"成交价格：{price}",
            f"成交金额：{amount:,.0f}",
            f"触发模式：{BASELINE[mode]['name']}",
            f"触发原因：{reason}",
            f"原建议数量：{submitted_vol}股",
            f"截断原因：{cap_reason or '部分成交（实际数量<建议数量）'}",
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        feishu_notify("\n".join(lines), key=f"buy_part_{symbol}", cooldown=60)
    else:
        # ── 全部成交 ──────────────────────────────────────────────────
        amount = vol * price
        lines = [
            f"📗 【模拟买入成功】",
            f"股票：{symbol} {name}",
            f"成交数量：{vol}股",
            f"成交价格：{price}",
            f"成交金额：{amount:,.0f}",
            f"触发模式：{BASELINE[mode]['name']}",
            f"触发原因：{reason}",
        ]
        if submitted_vol > 0 and submitted_vol != vol:
            lines.append(f"原建议数量：{submitted_vol}股")
            if cap_reason:
                lines.append(f"截断原因：{cap_reason}")
        lines.append(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        feishu_notify("\n".join(lines), key=f"buy_{symbol}", cooldown=60)

def feishu_sell(symbol: str, name: str, price: float, vol: int,
                mode: str, reason: str,
                submitted_vol: int = 0,
                reject_reason: str = "",
                cap_reason: str = ""):
    if reject_reason:
        lines = [
            f"🚫 【模拟卖出失败】",
            f"股票：{symbol} {name}",
            f"失败原因：{reject_reason}",
            f"触发模式：{BASELINE[mode]['name']}",
            f"触发原因：{reason}",
        ]
        if submitted_vol > 0:
            lines.append(f"拟卖出数量：{submitted_vol}股（被拒）")
        lines.append(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        feishu_notify("\n".join(lines), key=f"reject_sell_{symbol}", cooldown=60)
        return

    if vol < submitted_vol:
        amount = vol * price
        lines = [
            f"🟡 【模拟卖出部分成交】",
            f"股票：{symbol} {name}",
            f"成交数量：{vol}股",
            f"成交价格：{price}",
            f"成交金额：{amount:,.0f}",
            f"触发模式：{BASELINE[mode]['name']}",
            f"触发原因：{reason}",
            f"原建议数量：{submitted_vol}股",
            f"截断原因：{cap_reason or '部分成交'}",
            f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        feishu_notify("\n".join(lines), key=f"sell_part_{symbol}", cooldown=60)
    else:
        amount = vol * price
        lines = [
            f"📕 【模拟卖出成功】",
            f"股票：{symbol} {name}",
            f"成交数量：{vol}股",
            f"成交价格：{price}",
            f"成交金额：{amount:,.0f}",
            f"触发模式：{BASELINE[mode]['name']}",
            f"触发原因：{reason}",
        ]
        if submitted_vol > 0 and submitted_vol != vol:
            lines.append(f"原建议数量：{submitted_vol}股")
        lines.append(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        feishu_notify("\n".join(lines), key=f"sell_{symbol}", cooldown=60)

def feishu_fuse(reason: str):
    feishu_notify(
        f"🔴 【熔断触发】\n{reason}",
        key="fuse_event",
        cooldown=600,
    )

def feishu_reject(symbol: str, reason: str,
                  submitted_vol: int = 0,
                  cap_reason: str = ""):
    lines = [
        f"🚫 【交易拒绝】\n"
        f"{symbol}: {reason}"
    ]
    if submitted_vol > 0:
        lines.append(f"拟交易数量：{submitted_vol}股（被拒）")
    if cap_reason:
        lines.append(f"截断原因：{cap_reason}")
    feishu_notify("\n".join(lines), key=f"reject_{symbol}", cooldown=60)

def feishu_daily_summary(trades: List[dict], rejects: List[dict]):
    today = date.today().isoformat()
    total_pnl = sum(t.get("profit", 0) for t in trades)
    lines = [
        f"📊 【收盘交易汇总】{today}",
        f"成交: {len(trades)} 笔 | 拒绝: {len(rejects)} 笔",
        f"浮动盈亏: {total_pnl:+.2f}元",
    ]
    for t in trades:
        pnl = t.get("profit", 0)
        icon = "📗" if t["action"] == "buy" else "📕"
        lines.append(
            f"{icon} {t['action'].upper()} {t['symbol']} "
            f"{t['quantity']}股@{t['price']} "
            f"(策略:{BASELINE[t['mode']]['name']}) "
            f"{pnl:+.2f}元"
        )
    if rejects:
        lines.append("---")
        for r in rejects:
            lines.append(f"🚫 拒绝 {r['symbol']}: {r['reason']}")
    feishu_notify("\n".join(lines), key="daily_summary", cooldown=3600)

# =============================================================================
# 12. 更新 trade_log
# =============================================================================
def append_trade(record: dict):
    log_data = load_trade_log()
    log_data["trades"].append(record)
    save_json(TRADE_LOG, log_data)

def append_reject(record: dict):
    log_data = load_trade_log()
    log_data["rejects"].append(record)
    save_json(TRADE_LOG, log_data)

def record_trade_outcome(symbol: str, action: str, success: bool,
                         filled_price: float, cost_basis: float):
    """记录交易结果，用于计算连续亏损"""
    log_data = load_trade_log()
    today = date.today().isoformat()

    if action == "buy" and success:
        # 记录成本，后续止损判断
        log_data.setdefault("positions_cost", {})
        log_data["positions_cost"][symbol] = {
            "cost": cost_basis,
            "buy_price": filled_price,
            "buy_date": today,
        }

    if action == "sell" and success:
        cost_entry = log_data.get("positions_cost", {}).get(symbol)
        if cost_entry:
            pnl = (filled_price - cost_entry["buy_price"]) * 100
            # 亏损则计数
            if pnl < 0:
                log_data["consecutive_loss"] = log_data.get("consecutive_loss", 0) + 1
                if log_data["consecutive_loss"] == 3:
                    log_data["fuse_triggered_at"] = datetime.now().isoformat()
                    feishu_fuse(f"连续3笔亏损，暂停新开仓半天")
            else:
                log_data["consecutive_loss"] = 0
            del log_data["positions_cost"][symbol]

    save_json(TRADE_LOG, log_data)

# =============================================================================
# 13. 更新 shadow_portfolio
# =============================================================================
def update_shadow(trades: List[dict], rejects: List[dict], unified: dict):
    # 读取已有 shadow
    existing = {}
    if SHADOW_PORTFOLIO.exists():
        try:
            existing = json.loads(SHADOW_PORTFOLIO.read_text())
        except:
            existing = {}
    shadow_pos = existing.get("positions", {})

    # 更新实际成交
    for t in trades:
        sym = t["symbol"]
        action = t["action"]
        filled = t.get("filled_shares", t.get("quantity", 0))
        if filled <= 0:
            continue
        if action == "buy":
            shadow_pos[sym] = shadow_pos.get(sym, 0) + filled
        elif action == "sell":
            shadow_pos[sym] = max(0, shadow_pos.get(sym, 0) - filled)

    save_json(SHADOW_PORTFOLIO, {
        "schema_version": "2.0",
        "timestamp": datetime.now().isoformat(),
        "phase": "Phase-2.2 AI Stock Cockpit (SAFE_OBSERVE)",
        "broker": "eastmoney_mock",
        "mode": "aggressive_paper",
        "real_trade_prohibited": True,
        "today_trades":  trades,
        "today_rejects":  rejects,
        "positions": shadow_pos,
        "source": {
            "positions_count": len(unified.get("positions", [])),
            "capital": unified.get("capital", {}),
        },
    })

# =============================================================================
# 14. 主执行
# =============================================================================
def execute():
    log("=" * 60)
    log("Phase-2.2 AI Stock Cockpit (SAFE_OBSERVE) 开始")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    # ── kill_switch ────────────────────────────────────────────────────
    if not check_kill_switch():
        log("kill_switch=false，退出", "WARN")
        return

    # ── SAFE_OBSERVE 检查 ──────────────────────────────────────────────
    cfg = load_json_safe(PAPER_ENABLED_J)
    if cfg and not cfg.get("enabled", True):
        log("paper_trade_enabled=false（SAFE_OBSERVE模式），退出", "WARN")
        feishu("[自动买入暂停] 原因：SAFE_OBSERVE模式开启")
        return

    # ── 前置条件 ───────────────────────────────────────────────────────
    ok, msg = check_prerequisites()
    if not ok:
        log(f"前置条件不满足: {msg}", "WARN")
        return

    # ── 读取数据 ───────────────────────────────────────────────────────
    unified   = load_portfolio()
    events    = load_events()
    trade_log = load_trade_log()
    regime    = load_json_safe(REGIME_JSON) or {}
    reg       = regime.get("regime", "neutral")

    positions = unified.get("positions", [])
    capital   = unified.get("capital", {})
    log(f"持仓: {len(positions)}只 | 总资产: {capital.get('total_assets',0):.0f}")
    log(f"市场状态: {reg} | 仓位上限: {regime.get('position_limit',1.0)*100:.0f}%")

    # ── 市场状态检查 ────────────────────────────────────────────────
    if reg == "panic":
        log("【市场状态=panic】禁止所有新开仓，退出", "WARN")
        feishu_status = f"🔴 【Panic】禁止所有新开仓\n指数：{regime.get('signals',['急跌'])[0]}"
        feishu(feishu_status)
        return
    if reg == "risk_off":
        log("【市场状态=risk_off】只做观察不开新仓", "WARN")
        feishu_status = f"⚠️ 【Risk_off】降低仓位，只观察不开新仓\n{regime.get('signals',[])[0] if regime.get('signals') else ''}"
        feishu(feishu_status)

    # ── Phase-2.6B: 从 decision_log 读取信号 ─────────────────────────────
    decision_candidates = generate_candidates_from_decision(unified, events)
    log(f"Decision Layer 候选: {len(decision_candidates)}个")

    # ── 持仓止损检查（event-driven，保留）───────────────────────────────
    event_driven = []
    for pos in positions:
        sym = pos.get("symbol", "")
        if sym in anomaly_syms:
            continue
        for ev in all_events:
            if ev.get("symbol") == sym and ev.get("type") == "ma5_breakdown":
                event_driven.append({
                    "mode": "mode_4", "action": "sell",
                    "symbol": sym, "name": pos.get("name", ""),
                    "reason": f"MA5止损: {ev['detail']}",
                    "event": ev,
                })

    # 合并：decision_log 优先，event-driven 兜底
    candidates = decision_candidates + event_driven

    if not candidates:
        log("无候选信号，退出")
        return

    # ── 执行 ───────────────────────────────────────────────────────────
    executed = []
    rejected = []

    for cand in candidates:
        sym    = cand["symbol"]
        action = cand["action"]
        mode   = cand["mode"]
        name   = cand.get("name", "")
        reason = cand["reason"]
        ev_src = cand.get("event", {})

        price = get_stock_price(sym, name)
        if not price or price <= 0:
            rejected.append({"symbol": sym, "action": action,
                            "reason": "无有效行情", "mode": mode})
            continue

        ok, risk_msg, info = check_risk_full(sym, action, price,
                                              unified, trade_log)
        if not ok:
            rejected.append({"symbol": sym, "action": action,
                            "reason": risk_msg, "mode": mode})
            feishu_reject(sym, risk_msg)
            continue

        # ── Phase-2.1 市场状态额外检查 ─────────────────────────────────
        rsi_raw = cand.get("rsi") or 0
        pos_mult = cand.get("position_mult", 1.0)

        # overheat + 高RSI → 拒绝
        if reg == "overheat" and rsi_raw > 75 and action == "buy":
            submitted_vol = cand.get("shares", 0)
            rejected.append({"symbol": sym, "action": action,
                            "reason": f"overheat+RSI{rsi_raw:.0f}>75 禁止追高",
                            "mode": mode, "submitted_vol": submitted_vol})
            feishu_reject(sym, f"市场过热 RSI={rsi_raw:.0f}>75 禁止追高",
                         submitted_vol=submitted_vol, cap_reason="overheat高RSI")
            continue

        # 弱势板块 position_mult 极低 → 拒绝
        if action == "buy" and pos_mult < 0.4:
            submitted_vol = cand.get("shares", 0)
            rejected.append({"symbol": sym, "action": action,
                            "reason": f"弱势板块 position_mult={pos_mult:.2f}<0.4",
                            "mode": mode, "submitted_vol": submitted_vol})
            feishu_reject(sym, f"弱势板块 position_mult={pos_mult:.2f}<0.4 降低仓位",
                         submitted_vol=submitted_vol, cap_reason="弱势板块")
            continue

        # ── 成交数量确定 ───────────────────────────────────────────────
        # 原建议数量（来自候选股）
        submitted_vol = cand.get("shares", 0)

        if action == "sell":
            vol = info.get("avail_volume", 0)
        else:
            # 仓位上限 cap（regime 或风控）
            regime_limit = regime.get("position_limit", 1.0)
            vol = min(
                submitted_vol,
                int(submitted_vol * regime_limit),
                info.get("suggest_vol", submitted_vol),
            )

        if vol <= 0:
            rejected.append({"symbol": sym, "action": action,
                            "reason": "仓位计算为0",
                            "mode": mode, "submitted_vol": submitted_vol})
            feishu_reject(sym, "仓位计算为0", submitted_vol=submitted_vol)
            continue

        # cap_reason 说明截断原因
        cap_reason = ""
        if submitted_vol > vol:
            if regime_limit < 1.0:
                cap_reason = f"regime仓位上限{int(regime_limit*100)}%"
            elif info.get("suggest_vol", submitted_vol) < submitted_vol:
                cap_reason = "风控资金限制"
            else:
                cap_reason = "部分成交"

        # ── SAFE_OBSERVE 防重复买入检查 ─────────────────────────────────
        # 判断是否已有持仓
        pos_count = 0
        for pos in unified.get("positions", []):
            if pos.get("symbol") == sym:
                pos_count = pos.get("volume", 0)
                break
        # 判断是否是新信号（event engine 触发才算新信号）
        new_signal = bool(ev_src.get("type") in ("break_ma5", "volume_surge", "index_surge"))
        ok_repeat, repeat_msg = check_repeat_buy(
            sym, action, trade_log, pos_count, new_signal)
        if not ok_repeat:
            submitted_vol = cand.get("shares", 0)
            rejected.append({"symbol": sym, "action": action,
                            "reason": repeat_msg, "mode": mode,
                            "submitted_vol": submitted_vol})
            feishu_reject(sym, repeat_msg,
                         submitted_vol=submitted_vol, cap_reason="防重复买入")
            continue

        # ── 资金/仓位上限检查 ──────────────────────────────────────────
        # 可用资金低于总资产10% → 禁止新开仓
        avail_cash = unified.get("capital", {}).get("avail_balance", 0)
        total_assets = unified.get("capital", {}).get("total_assets", 1)
        if action == "buy" and avail_cash / total_assets < 0.10:
            submitted_vol = cand.get("shares", 0)
            rejected.append({"symbol": sym, "action": action,
                            "reason": f"可用资金不足10%({avail_cash/total_assets:.1%})，禁止新开仓",
                            "mode": mode, "submitted_vol": submitted_vol})
            feishu_reject(sym, f"可用资金{avail_cash/total_assets:.1%}<10%，禁止新开仓",
                         submitted_vol=submitted_vol, cap_reason="资金不足")
            continue

        # ── 发送模拟单 ────────────────────────────────────────────────
        order_id = f"PTB_{datetime.now().strftime('%Y%m%d%H%M%S')}_{sym}"
        result = mx_trade(action, sym, price, vol, order_id)
        filled_qty = result.get("filled_qty", vol if result["success"] else 0)
        filled_px  = result.get("filled_price", price if result["success"] else 0)

        # ── 记录 trade_log ─────────────────────────────────────────────
        reject_reason_val = "" if result["success"] else result.get("message", "模拟单失败")
        record = {
            "trade_date":      date.today().isoformat(),
            "trade_time":      datetime.now().strftime("%H:%M:%S"),
            "symbol":          sym,
            "name":            name,
            "action":          action,
            "mode":            mode,
            "submitted_price": price,
            "submitted_vol":   submitted_vol,
            "filled_price":    filled_px,
            "filled_shares":   filled_qty,
            "order_id":        order_id,
            "success":         result["success"],
            "order_status":    ("filled" if result["success"] else
                                "partial" if 0 < filled_qty < vol else
                                "rejected"),
            "reject_reason":   reject_reason_val,
            "cap_reason":      cap_reason,
            "trigger":         reason,
            "strategy":        BASELINE[mode]["name"],
            "position_mult":   pos_mult,
            "market_regime":   reg,
            "event":           ev_src,
        }
        append_trade(record)
        executed.append(record)

        # ── 更新加仓计数 ──────────────────────────────────────────────
        if action == "buy" and result["success"]:
            log_data = load_trade_log()
            log_data.setdefault("add_positions", {})
            log_data["add_positions"][sym] = log_data["add_positions"].get(sym, 0) + 1
            save_json(TRADE_LOG, log_data)

        # ── 记录结果（用于亏损追踪）──────────────────────────────────
        record_trade_outcome(sym, action, result["success"],
                           filled_px, filled_px * filled_qty)

        # ── 飞书通知（全部走新格式）───────────────────────────────────
        if not result["success"] and filled_qty == 0:
            feishu_reject(sym, reject_reason_val,
                         submitted_vol=submitted_vol, cap_reason=cap_reason)
        elif action == "buy":
            feishu_buy(sym, name, filled_px, filled_qty, mode, reason,
                      submitted_vol=submitted_vol,
                      cap_reason=cap_reason)
        else:
            feishu_sell(sym, name, filled_px, filled_qty, mode, reason,
                       submitted_vol=submitted_vol,
                       cap_reason=cap_reason)

        log(f"{'✅' if result['success'] else '❌'} "
            f"{action.upper()} {sym} 建议{submitted_vol}股→成交{filled_qty}股@{filled_px} "
            f"[{BASELINE[mode]['name']}] "
            f"{'成功' if result['success'] else '失败: '+reject_reason_val}")

    # ── 日终汇总 ───────────────────────────────────────────────────────
    update_shadow(executed, rejected, unified)

    # 下午3点收盘后发汇总
    now = datetime.now()
    if now.hour >= 15 and now.hour < 16:
        feishu_daily_summary(executed, rejected)

    log(f"✅ 完成: 成交{len(executed)}笔 | 拒绝{len(rejected)}笔")

# =============================================================================
# 入口
# =============================================================================
if __name__ == "__main__":
    execute()

    # Runtime Event
    try:
        from runtime_events.runtime_event_logger import log_event
        log_event(
            module="paper_trade_executor",
            layer="execution_layer",
            status="success",
            message="paper trade cycle completed",
        )
    except ImportError:
        pass
