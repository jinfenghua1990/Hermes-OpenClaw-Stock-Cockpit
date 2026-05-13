#!/usr/bin/env python3
"""
# Phase-2.6C 重构日报生成器
# 第一页：Top Picks（含完整溯源）+ 核心观点 + 风险提醒 + 次日策略
# 后面才放：runtime / health / governance
"""
import json, sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[2]
TOP_PICKS_FILE = BASE / "reports/top_picks.json"
AI_SUMMARY_FILE = BASE / "reports/ai_market_summary.md"
EMOTION_FILE = BASE / "emotion_engine/cache/market_emotion_snapshot.json"
PAPER_POSITIONS = BASE / "portfolio/unified_positions.json"
SYSTEM_SNAP = BASE / "system_monitor/system_snapshot.json"
HEALTH_FILE = BASE / "system_health/runtime_event_health_check.py"
DECISION_LOG  = BASE / "reports/paper_decision_log.json"
TRACE_LOG     = BASE / "reports/decision_trace_log.json"
OUTPUT_PATH = BASE / "reports/history/{date}.md"
REPORTS_DIR = BASE / "reports/history"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}


def load_text(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except:
        return ""


def render_top_picks(picks, decisions=None):
    """渲染 Top Picks，含 Paper Decision"""
    if not picks:
        return "**暂无精选个股，建议观望。**"

    # 构建决策字典 {代码: decision}
    dec_map = {}
    if decisions:
        for d in decisions:
            sym = d.get("股票代码", "")
            dec_map[sym] = d

    lines = []
    for i, p in enumerate(picks, 1):
        pct = p.get('涨跌幅', 0)
        pct_str = f"+{pct:.2f}%" if pct >= 0 else f"{pct:.2f}%"
        risks = p.get('风险点', [])
        risks_str = " / ".join(risks) if risks else "无"
        obs = p.get('建议观察位', {})
        action = p.get('操作建议', '观察')
        score = p.get('AI评分', 0)

        sym = p.get('股票代码', '')
        dec = dec_map.get(sym, {})
        decision = dec.get('decision', 'no_action')
        reason   = dec.get('reason', '')

        # 决策标签
        emoji = {'paper_buy': '📗', 'paper_skip': '🚫', 'paper_hold': '📋', 'paper_sell': '📕'}.get(decision, '⚪')
        decision_label = {'paper_buy': '✅买入', 'paper_skip': '🚫跳过', 'paper_hold': '📋持有', 'paper_sell': '📕卖出'}.get(decision, '—')

        lines.append(
            f"{i}. **{p['股票名称']}** ({p['股票代码']})  {pct_str}\n"
            f"   - 模式：{p['所属模式']}｜AI评分：{score}｜{action}\n"
            f"   - 入选原因：{p.get('入选原因', '—')}\n"
            f"   - 风险点：{risks_str}\n"
            f"   - 观察位：支撑 {obs.get('支撑位', '-')} / 压力 {obs.get('压力位', '-')}\n"
            f"   - 🔔 **系统决策：{decision_label}** {emoji}\n"
            f"     原因：{reason}"
        )
    return "\n\n".join(lines)


def render_paper_decisions_summary(decisions):
    """渲染 Paper Decision 汇总"""
    if not decisions:
        return "**暂无系统决策。**"

    buys  = [d for d in decisions if d.get('decision') == 'paper_buy']
    sells = [d for d in decisions if d.get('decision') == 'paper_sell']
    skips = [d for d in decisions if d.get('decision') in ('paper_skip', 'await_price_confirm', 'await_capital_confirm')]
    holds = [d for d in decisions if d.get('decision') == 'paper_hold']
    await_caps = [d for d in decisions if d.get('decision') == 'await_capital_confirm']

    lines = []
    if buys:
        names = [f"**{d['股票名称']}**({d['股票代码']})" for d in buys]
        lines.append(f"📗 **买入**：{', '.join(names)}")
        for d in buys:
            zone = f"{d.get('entry_zone_min','?')}~{d.get('entry_zone_max','?')}"
            sl = d.get('stop_loss', '?')
            lines.append(f"   {d['股票名称']}：买入区间{zone} | 止损{sl} | {d['quantity']}股")
    if await_caps:
        names = [f"**{d['股票名称']}**({d['股票代码']})" for d in await_caps]
        lines.append(f"⏳ **待资金确认**：{', '.join(names)}")
        for d in await_caps:
            zone = f"{d.get('entry_zone_min','?')}~{d.get('entry_zone_max','?')}"
            lines.append(f"   {d['股票名称']}：{zone} | 需确认可用资金后操作")
    if sells:
        names = [f"**{d['股票名称']}**({d['股票代码']})" for d in sells]
        lines.append(f"📕 **卖出**：{', '.join(names)}")
    if skips:
        lines.append(f"🚫 **跳过**（{len(skips)}只）：{', '.join(d['股票名称'] for d in skips)}")
    if not lines:
        return "**暂无交易决策。**"
    return "\n".join(lines)


def render_trace_picks(picks, decisions):
    """Phase-2.6C 渲染每只 Top Pick 的完整溯源信息"""
    if not picks:
        return "**暂无精选个股。**"

    dec_map = {}
    for d in (decisions or []):
        dec_map[d.get('股票代码', '')] = d

    lines = []
    for i, p in enumerate(picks, 1):
        sym = p.get('股票代码', '')
        name = p.get('股票名称', '')
        price = p.get('价格') or p.get('last_price', '?')
        chg = p.get('涨跌幅', 0)
        rsi = p.get('RSI', '?')
        mode = p.get('所属模式', '?')
        score = p.get('AI评分', 0)
        obs = p.get('建议观察位', {})
        support = obs.get('支撑位', obs.get('support_price', '?'))
        pressure = obs.get('压力位', obs.get('pressure_price', '?'))
        action = p.get('操作建议', '?')
        reasons = p.get('入选原因', '?')
        dec = dec_map.get(sym, {})

        decision = dec.get('decision', 'no_action')
        buy_timing = dec.get('buy_timing', '?')
        zone_min = dec.get('entry_zone_min', '?')
        zone_max = dec.get('entry_zone_max', '?')
        max_chase = dec.get('max_chase_price', '?')
        stop_loss = dec.get('stop_loss', '?')
        tp_watch = dec.get('take_profit_watch', '?')
        qty = dec.get('quantity', 0)
        pos_pct = dec.get('position_size_pct', 0)
        skip_r = dec.get('skip_reason', '?')

        # 决策标签
        dec_map_emoji = {
            'paper_buy': '📗', 'paper_skip': '🚫', 'paper_hold': '📋',
            'paper_sell': '📕', 'await_capital_confirm': '⏳', 'await_price_confirm': '⏳'
        }
        dec_map_label = {
            'paper_buy': '✅买入', 'paper_skip': '🚫跳过', 'paper_hold': '📋持有',
            'paper_sell': '📕卖出', 'await_capital_confirm': '⏳待资金确认', 'await_price_confirm': '⏳待价格确认'
        }
        emoji = dec_map_emoji.get(decision, '⚪')
        label = dec_map_label.get(decision, decision)

        chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
        zone_str = f"{zone_min}~{zone_max}" if zone_min and zone_max else '?'
        qty_str = f"{qty}股" if qty else "待确认"

        lines.append(f"**{i}. {name} ({sym})**  {chg_str} {emoji} {label}")
        lines.append(f"   - 数据时间：{dec.get('generated_at', '?')}")
        lines.append(f"   - 现价：{price} | 涨跌幅：{chg_str} | RSI：{rsi}")
        lines.append(f"   - MA20：{p.get('MA20', p.get('ma20', '?'))} | 支撑/压力：{support}/{pressure}")
        lines.append(f"   - 建议：{action}（{mode} | AI评分 {score}）")
        if decision in ('paper_buy',):
            lines.append(f"   - 买入时机：{buy_timing}")
            lines.append(f"   - 买入区间：{zone_str}")
            lines.append(f"   - 不追高价：>{max_chase} 放弃")
            lines.append(f"   - 止损位：{stop_loss} | 止盈观察：{tp_watch}")
            lines.append(f"   - 建议仓位：{pos_pct:.1f}% | 建议数量：{qty_str}")
        elif decision in ('await_capital_confirm', 'await_price_confirm'):
            lines.append(f"   - 买入区间：{zone_str}")
            lines.append(f"   - 原因：{skip_r}")
        else:
            lines.append(f"   - 跳过原因：{skip_r}")
        # 数据来源简表
        lines.append(f"   - 数据链路：OpenClaw → robot_3(因子) → robot_4(模式) → action_engine → paper_decision_engine → paper_risk_controller")
        if i < len(picks):
            lines.append("")

    return "\n".join(lines)


def render_paper_trade(positions, trade_log):
    """渲染模拟账户"""
    try:
        capital = positions.get('capital', {})
        total = capital.get('total_assets', 0)
        avail = capital.get('avail_balance', 0)
        pos_list = positions.get('positions', [])
        
        lines = [f"- **持仓**：{len(pos_list)} 只  |  **总资产**：¥{total:,.0f}  |  **可用**：¥{avail:,.0f}"]
        
        if pos_list:
            for pos in pos_list[:5]:
                profit = pos.get('profit_ratio', 0)
                profit_str = f"+{profit:.1f}%" if profit >= 0 else f"{profit:.1f}%"
                lines.append(
                    f"  • {pos.get('name','?')} ({pos.get('symbol','?')}) "
                    f"{pos.get('volume',0)}股｜盈亏 {profit_str}"
                )
        else:
            lines.append("  暂无持仓（空仓观望）")
        
        # 交易统计
        trades = trade_log.get('trades', [])
        today_trades = [t for t in trades if str(t.get('time','')).startswith(TODAY)]
        if today_trades:
            buys = sum(1 for t in today_trades if t.get('action') == 'buy')
            sells = sum(1 for t in today_trades if t.get('action') == 'sell')
            lines.append(f"- **今日交易**：{buys}笔买入 / {sells}笔卖出")
        else:
            lines.append("- **今日交易**：无操作")
        
        return "\n".join(lines)
    except Exception as e:
        return f"- 模拟账户数据获取失败: {e}"


def render_runtime_summary():
    """渲染运行时状态（一句话版）"""
    health = load_json(BASE / "reports/runtime_event_health.json")
    freeze_file = BASE / "reports/freeze_integrity.json"
    freeze = load_json(freeze_file)
    
    modules_active = health.get('active_today', 0)
    modules_total = health.get('total_modules', 21)
    runtime_status = health.get('status', 'unknown')
    freeze_status = freeze.get('status', 'unknown') if freeze else 'unknown'
    
    return (
        f"- Runtime：{modules_active}/{modules_total} 活跃｜{runtime_status}\n"
        f"- Freeze Integrity：{freeze_status}\n"
        f"- Phase-2.6C Decision Traceability"
    )


def render_daily_review_old():
    """从旧版日报提取关键数据"""
    old_report = BASE / "report_engine/outputs/2026-05-13.md"
    if not old_report.exists():
        return None
    with open(old_report) as f:
        content = f.read()
    return content


def main():
    print("=== Phase-2.6A 日报生成器 ===")
    
    # 加载数据
    top_picks_data = load_json(TOP_PICKS_FILE)
    ai_summary = load_text(AI_SUMMARY_FILE)
    emotion = load_json(EMOTION_FILE)
    positions = load_json(PAPER_POSITIONS)
    trade_log = load_json(BASE / "portfolio/trade_log.json")
    decision_data = load_json(DECISION_LOG)
    decisions = decision_data.get("decisions", [])
    
    picks = top_picks_data.get('top_picks', [])
    emotion_data = emotion.get('emotion_analysis', {})
    market_metrics = emotion.get('market_metrics', {})
    
    # 提取关键数据
    emotion_score = emotion_data.get('emotion_score', 40)
    market_phase = emotion_data.get('market_phase', 'unknown')
    risk_level = emotion_data.get('market_risk_level', 'high')
    strongest = emotion_data.get('strongest_mode', '未知')
    weakest = emotion_data.get('weakest_mode', '未知')
    
    phase_map = {
        'recovery_phase': '复苏阶段',
        'breakout_phase': '突破阶段',
        'defensive_phase': '防御阶段',
        'trend_phase': '趋势阶段',
        'consolidation_phase': '震荡阶段',
    }
    risk_emoji = {'low': '🟢', 'medium': '🟡', 'medium_high': '🟠', 'high': '🔴'}.get(risk_level, '⚪')
    phase_cn = phase_map.get(market_phase, market_phase)
    
    # ========== 构建新版日报 ==========
    report_lines = [
        f"# 📊 今日市场复盘 — {TODAY}",
        "",
        "---",
        "",
        "## 🔝 Top Picks 精选（含完整溯源）",
        "",
        render_trace_picks(picks, decisions),
        "",
        "---",
        "",
        "## 🤖 Paper Decision 决策层",
        "",
        render_paper_decisions_summary(decisions),
        "",
        "---",
        "",
        "## 🧠 AI 市场总结",
        "",
        ai_summary or f"情绪评分 {emotion_score}/100，当前市场 {phase_cn}，{risk_emoji} {risk_level}。",
        "",
        "---",
        "",
        "## 📋 模拟账户状态",
        "",
        render_paper_trade(positions, trade_log),
        "",
        "---",
        "",
        "## 🏥 系统状态",
        "",
        render_runtime_summary(),
        "",
        "---",
        "",
        "*来源：Cockpit AI 量化系统 | Phase-2.6C Decision Traceability | Hermes-股票*",
    ]
    
    report_content = "\n".join(report_lines)
    
    # 写入历史
    output_file = REPORTS_DIR / f"{TODAY}.md"
    with open(output_file, 'w') as f:
        f.write(report_content)
    print(f"写入: {output_file}")
    
    # 同步更新 index
    index_file = REPORTS_DIR / "index.json"
    index = load_json(index_file) if index_file.exists() else {"reports": []}
    reports = index.get("reports", [])
    entry = {"date": TODAY, "file": f"{TODAY}.md", "top_picks_count": len(picks)}
    # 去重
    dates = {r['date'] for r in reports}
    if TODAY not in dates:
        reports.insert(0, entry)
    index['reports'] = reports
    index['last_updated'] = datetime.now().isoformat()
    with open(index_file, 'w') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"更新: {index_file}")
    
    print(f"\n✅ 日报生成完成")
    print(f"   Top Picks: {len(picks)} 只")
    print(f"   情绪: {emotion_score}/100 | {phase_cn} | {risk_emoji} {risk_level}")
    
    # 打印报告内容预览
    print("\n" + "="*50)
    print(report_content[:2000])
    print("="*50)
    
    return report_content


if __name__ == '__main__':
    main()
