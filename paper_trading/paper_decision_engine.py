#!/usr/bin/env python3
"""
Phase-2.6B Paper Decision Engine
读取 top_picks.json，生成 paper_decision_log.json
paper_trade_executor 读取 decision_log 执行，不再直接读 top_picks
"""
import json, os, sys
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any

# =============================================================================
# 配置
# =============================================================================
BASE = Path.home() / "project_ai_trading"
TOP_PICKS   = BASE / "reports/top_picks.json"
WATCHLIST   = BASE / "paper_trading/watchlist.json"
UNIFIED_POS = BASE / "portfolio/unified_positions.json"
DECISION_LOG= BASE / "reports/paper_decision_log.json"
PAPER_ENABLED = BASE / "config/paper_trade_enabled.json"

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

# =============================================================================
# 读取数据
# =============================================================================
def load_top_picks() -> dict:
    return load_json(TOP_PICKS)

def load_watchlist() -> dict:
    return load_json(WATCHLIST)

def load_positions() -> dict:
    return load_json(UNIFIED_POS)

def load_paper_enabled() -> dict:
    return load_json(PAPER_ENABLED)

# =============================================================================
# 决策规则
# =============================================================================

def decide_action(pick: dict, held_syms: set, watchlist: dict,
                 total_assets: float, total_pos_value: float,
                 today_decisions: List[dict]) -> tuple[str, str, str]:
    """
    返回 (decision, action, reason)
    decision: paper_buy | paper_skip | paper_hold | no_action
    action:   buy | skip | hold | —
    reason:   原因说明
    """
    sym   = pick.get("股票代码", "")
    name  = pick.get("股票名称", "")
    score = pick.get("AI评分", 0)
    rsi   = pick.get("RSI", 50)
    price = pick.get("价格", 0)
    action_rec = pick.get("操作建议", "")
    risk_notes = pick.get("风险点", [])

    # ── 0. watchlist override ────────────────────────────────────────────
    wl_entry = watchlist.get("stocks", {}).get(sym, {})
    wl_action = wl_entry.get("action", "")
    if wl_action == "avoid":
        return "paper_skip", "skip", f"watchlist标记avoid，跳过"

    # ── 1. 已有持仓 → hold ─────────────────────────────────────────────
    if sym in held_syms:
        return "paper_hold", "hold", "已有持仓，继续持有"

    # ── 2. 今日已达 paper_buy 上限(≤1只/日) ─────────────────────────────
    today_buys = [d for d in today_decisions if d.get("decision") == "paper_buy"]
    if len(today_buys) >= 1:
        return "paper_skip", "skip", f"今日已决策买入{today_buys[0]['股票名称']}，每日最多1笔"

    # ── 3. 动作建议不是买入 ───────────────────────────────────────────
    if not any(k in action_rec for k in ["低吸", "买入", "参与", "机会"]):
        return "paper_skip", "skip", f"操作建议={action_rec}，非买入信号"

    # ── 4. AI评分 < 75 ────────────────────────────────────────────────
    if score < 75:
        return "paper_skip", "skip", f"AI评分={score}<75"

    # ── 5. RSI > 75 ───────────────────────────────────────────────────
    if rsi > 75:
        return "paper_skip", "skip", f"RSI={rsi:.1f}>75，超买风险"

    # ── 6. 风险状态 error ─────────────────────────────────────────────
    if any("error" in str(r).lower() for r in risk_notes):
        return "paper_skip", "skip", f"风险状态error: {risk_notes}"

    # ── 7. 仓位超限(总仓位>80%) ────────────────────────────────────────
    if total_assets > 0:
        pos_pct = total_pos_value / total_assets
        if pos_pct >= 0.80:
            return "paper_skip", "skip", f"总仓位{int(pos_pct*100)}%≥80%，仓位已满"

    # ── 8. 股价>300 禁止 ──────────────────────────────────────────────
    if price > 300:
        return "paper_skip", "skip", f"股价{price}元>300，禁止交易"

    # ── 9. 高开追涨检测(RSI>70且今日涨幅>3%) ───────────────────────────
    pct_today = abs(pick.get("涨跌幅", 0))
    if rsi > 70 and pct_today > 3:
        return "paper_skip", "skip", f"RSI={rsi:.1f}>70且今日涨幅{pct_today:.1f}%，高开追涨禁止"

    # ── 10. PASS ALL → paper_buy ───────────────────────────────────────
    # 计算建议仓位
    if price > 0 and total_assets > 0:
        if price > 200:
            max_pct = 0.20   # 200~300: 20%
        elif price > 100:
            max_pct = 0.30   # 100~200: 30%
        else:
            max_pct = 0.50   # <100: 50%
        suggest_vol = min(
            int(total_assets * max_pct / price / 100) * 100,
            1000
        )
    else:
        max_pct, suggest_vol = 0, 0

    return "paper_buy", "buy", (
        f"AI评分{score}≥75 RSI={rsi:.1f}<75 风险通过 "
        f"建议仓位{int(max_pct*100)}% {suggest_vol}股"
    )


def decide_sell(unified: dict, trade_log: dict) -> List[dict]:
    """
    检查持仓是否需要止损/止盈
    返回需要卖出的决策列表
    """
    positions = unified.get("positions", [])
    decisions = []
    today = date.today().isoformat()

    # 读取持仓成本
    positions_cost = trade_log.get("positions_cost", {})

    for pos in positions:
        sym  = pos.get("symbol", "")
        name = pos.get("name", "")
        vol  = pos.get("volume", 0)
        cost = pos.get("avg_cost", 0)
        cur_px = pos.get("current_price", 0)
        rsi   = pos.get("rsi", 50)
        profit_ratio = pos.get("profit_ratio", 0)

        if vol <= 0 or cost <= 0 or cur_px <= 0:
            continue

        loss_pct = (cur_px - cost) / cost
        reasons = []

        # 规则1: 跌破止损(-5%)
        if loss_pct <= -0.05:
            reasons.append(f"亏损{loss_pct:.1%}<=-5%止损")

        # 规则2: RSI>80且盈利
        if rsi > 80 and profit_ratio > 0:
            reasons.append(f"RSI={rsi:.0f}>80且盈利{profit_ratio:.1%}，止盈")

        # 规则3: 成本异常(利通电子历史持仓)
        cost_entry = positions_cost.get(sym, {})
        if not cost_entry and sym in {"603629"}:
            reasons.append(f"成本数据异常({cost})，需清理")

        if reasons:
            decisions.append({
                "股票代码": sym,
                "股票名称": name,
                "decision": "paper_sell",
                "action": "sell",
                "reason": "; ".join(reasons),
                "当前价": cur_px,
                "成本价": cost,
                "盈亏": f"{profit_ratio:.1%}",
                "suggest_vol": vol,
            })

    return decisions


# =============================================================================
# 主逻辑
# =============================================================================
def run():
    print(f"=== Paper Decision Engine Phase-2.6B === {datetime.now().strftime('%H:%M:%S')}")

    # 读取前置
    top_picks_data = load_top_picks()
    watchlist_data  = load_watchlist()
    unified         = load_positions()
    paper_enabled   = load_paper_enabled()
    trade_log_path  = BASE / "portfolio/trade_log.json"
    trade_log       = load_json(trade_log_path)

    picks = top_picks_data.get("top_picks", [])
    print(f"Top Picks: {len(picks)} 只")

    if not picks:
        save_json(DECISION_LOG, {
            "schema_version": "2.6B",
            "phase": "Phase-2.6B Paper Auto Decision",
            "generated_at": datetime.now().isoformat(),
            "decisions": [],
            "summary": "无 Top Picks",
        })
        print("✅ 无 Top Picks，生成空 decision log")
        return

    # 检查 paper_trade 是否启用
    if not paper_enabled.get("enabled", False):
        print("⚠️ paper_trade_enabled=false，跳过决策")

    # 持仓信息
    positions = unified.get("positions", [])
    held_syms = {p["symbol"] for p in positions if p.get("volume", 0) > 0}
    capital   = unified.get("capital", {})
    total_assets  = capital.get("total_assets", 0)
    total_pos_val = capital.get("total_pos_value", 0)

    print(f"持仓: {len(held_syms)} 只 | 总资产: {total_assets:,.0f} | 仓位: {total_pos_val/total_assets:.0%}" if total_assets else "持仓: 0")

    # 已有今日决策
    existing_log = load_json(DECISION_LOG)
    today_str    = date.today().isoformat()
    today_decisions = [
        d for d in existing_log.get("decisions", [])
        if d.get("date") == today_str
    ]

    # ── 买入决策 ──────────────────────────────────────────────────────────
    buy_decisions  = []
    skip_decisions = []
    hold_decisions = []

    for pick in picks:
        sym = pick.get("股票代码", "")
        decision, action, reason = decide_action(
            pick, held_syms, watchlist_data.get("stocks", {}),
            total_assets, total_pos_val, today_decisions
        )
        entry = {
            "date":         today_str,
            "股票代码":     sym,
            "股票名称":     pick.get("股票名称", ""),
            "decision":     decision,
            "action":       action,
            "reason":       reason,
            "AI评分":       pick.get("AI评分", 0),
            "RSI":          pick.get("RSI", 0),
            "操作建议":     pick.get("操作建议", ""),
            "所属模式":     pick.get("所属模式", ""),
            "建议股数":     pick.get("建议股数", 0),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if decision == "paper_buy":
            buy_decisions.append(entry)
        elif decision == "paper_skip":
            skip_decisions.append(entry)
        else:
            hold_decisions.append(entry)

    # ── 卖出决策 ──────────────────────────────────────────────────────────
    sell_decisions = decide_sell(unified, trade_log)

    all_decisions = buy_decisions + skip_decisions + hold_decisions + sell_decisions

    # ── 构建输出 ──────────────────────────────────────────────────────────
    paper_decisions = {
        "schema_version":   "2.6B",
        "phase":            "Phase-2.6B Paper Auto Decision",
        "generated_at":     datetime.now().isoformat(),
        "date":            today_str,
        "paper_only":       True,
        "real_trade_prohibited": True,
        "killswitch_check": os.environ.get("KILL_SWITCH", "").lower() != "true",
        "decisions":       all_decisions,
        "summary": {
            "total_picks":      len(picks),
            "paper_buy":        len(buy_decisions),
            "paper_skip":       len(skip_decisions),
            "paper_hold":       len(hold_decisions),
            "paper_sell":       len(sell_decisions),
            "buy_symbols":      [d["股票代码"] for d in buy_decisions],
            "sell_symbols":    [d["股票代码"] for d in sell_decisions],
            "skip_symbols":     [d["股票代码"] for d in skip_decisions],
        }
    }

    save_json(DECISION_LOG, paper_decisions)
    print(f"✅ 决策完成:")
    print(f"   买入: {len(buy_decisions)} 只 → {[d['股票名称'] for d in buy_decisions]}")
    print(f"   卖出: {len(sell_decisions)} 只 → {[d['股票名称'] for d in sell_decisions]}")
    print(f"   跳过: {len(skip_decisions)} 只 → {[d['股票名称'] for d in skip_decisions]}")
    print(f"   持有: {len(hold_decisions)} 只")
    print(f"   写入: {DECISION_LOG}")

    # ── Runtime Event ─────────────────────────────────────────────────────
    try:
        sys.path.insert(0, str(BASE))
        from runtime_events.runtime_event_logger import log_event
        log_event(
            module="paper_decision_engine",
            layer="execution_layer",
            status="success",
            message=f"decisions: buy={len(buy_decisions)} sell={len(sell_decisions)} skip={len(skip_decisions)}",
        )
    except ImportError:
        pass

    return paper_decisions


if __name__ == "__main__":
    run()
