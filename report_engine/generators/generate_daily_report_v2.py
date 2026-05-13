#!/usr/bin/env python3
"""
Phase-2.7D 日报生成器
- Top Picks 完整溯源
- Risk Validation
- Market Structure
- Source Trace: source_agent / source_module / data_source / data_as_of / trace_id
"""

import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[2]
TOP_PICKS_FILE = BASE / "reports/top_picks.json"
AI_SUMMARY_FILE = BASE / "reports/ai_market_summary.md"
EMOTION_FILE = BASE / "emotion_engine/cache/market_emotion_snapshot.json"
PAPER_POSITIONS = BASE / "portfolio/unified_positions.json"
DECISION_LOG = BASE / "reports/paper_decision_log.json"
REPORTS_DIR = BASE / "reports/history"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def load_text(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _fmt_pct(v):
    try:
        v = float(v)
        return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"
    except Exception:
        return "—"


def _decision_label(decision):
    return {
        "paper_buy": "📗 买入",
        "paper_skip": "🚫 跳过",
        "paper_hold": "📋 持有",
        "paper_sell": "📕 卖出",
        "await_capital_confirm": "⏳ 待资金确认",
        "await_price_confirm": "⏳ 待价格确认",
    }.get(decision, decision or "—")


def _source_line(d, p):
    source_trace = d.get("source_trace", {}) if isinstance(d, dict) else {}
    source_agent = d.get("source_agent") or source_trace.get("source_agent") or "unknown_agent"
    source_module = d.get("source_module") or source_trace.get("source_module") or "unknown_module"
    data_source = d.get("data_source") or source_trace.get("data_source") or p.get("data_source") or "unknown_source"
    data_as_of = d.get("data_as_of") or source_trace.get("data_as_of") or d.get("generated_at") or "unknown_time"
    trace_id = d.get("trace_id") or source_trace.get("trace_id") or "unknown_trace"
    replay_snapshot = source_trace.get("replay_snapshot") or d.get("replay_snapshot") or "latest"

    return (
        f"   - 来源：agent={source_agent} | module={source_module} | "
        f"data_source={data_source} | data_as_of={data_as_of} | "
        f"trace_id={trace_id} | replay={replay_snapshot}"
    )


def render_top_picks(picks, decisions):
    if not picks:
        return "**暂无精选个股，建议观望。**"

    dec_map = {d.get("股票代码", d.get("symbol", "")): d for d in decisions or []}
    lines = []

    for i, p in enumerate(picks, 1):
        sym = p.get("股票代码", p.get("symbol", ""))
        name = p.get("股票名称", p.get("name", "未知股票"))
        dec = dec_map.get(sym, {})
        decision = dec.get("decision", "no_action")
        pct = _fmt_pct(p.get("涨跌幅", p.get("change_pct", 0)))
        mode = p.get("所属模式", p.get("mode", "—"))
        score = p.get("AI评分", p.get("ai_score", "—"))
        reason = p.get("入选原因", "—")

        structure_type = dec.get("structure_type", p.get("structure_type", "unknown"))
        structure_conf = dec.get("structure_confidence", p.get("structure_confidence", "—"))
        support_price = dec.get("support_price", p.get("support_price", "—"))
        pressure_price = dec.get("pressure_price", p.get("pressure_price", "—"))

        rv_passed = dec.get("risk_validation_passed")
        rv_reason = dec.get("validation_reason", "")
        rv_errors = dec.get("validation_errors", [])

        lines.append(f"**{i}. {name} ({sym})**  {pct} | {_decision_label(decision)}")
        lines.append(f"   - 模式：{mode} | AI评分：{score}")
        lines.append(f"   - 入选原因：{reason}")
        lines.append(f"   - 市场结构：{structure_type} | 置信度：{structure_conf} | 支撑/压力：{support_price}/{pressure_price}")

        if rv_passed is False:
            lines.append(f"   - 风险校验：❌ FAIL | reason={rv_reason or 'invalid_price_structure'}")
            for e in rv_errors:
                lines.append(f"     - {e}")
        elif rv_passed is True:
            lines.append("   - 风险校验：✅ PASS")
        else:
            lines.append("   - 风险校验：⚠️ 未提供")

        lines.append(_source_line(dec, p))
        lines.append("")

    return "\n".join(lines).strip()


def render_paper_decisions_summary(decisions):
    if not decisions:
        return "**暂无系统决策。**"

    counts = {}
    for d in decisions:
        k = d.get("decision", "unknown")
        counts[k] = counts.get(k, 0) + 1

    lines = ["| Decision | Count |", "|---|---:|"]
    for k, v in sorted(counts.items()):
        lines.append(f"| {k} | {v} |")
    return "\n".join(lines)


def render_risk_validation_summary(decision_data):
    vr_list = decision_data.get("validation_results", [])
    if not vr_list:
        return "**暂无校验数据。**"

    pass_cnt = sum(1 for r in vr_list if r.get("is_valid"))
    fail_cnt = len(vr_list) - pass_cnt
    lines = [f"**风险价格校验**: {pass_cnt}✅ | {fail_cnt}❌"]

    for r in vr_list:
        if not r.get("is_valid"):
            lines.append(f"- **{r.get('name','?')}** ({r.get('symbol','?')}): ❌ invalid_price_structure")
            for e in r.get("errors", []):
                lines.append(f"  - 错误: {e}")
    return "\n".join(lines)


def render_paper_trade(positions):
    capital = positions.get("capital", {}) if isinstance(positions, dict) else {}
    pos_list = positions.get("positions", []) if isinstance(positions, dict) else []
    total = capital.get("total_assets", 0)
    avail = capital.get("avail_balance", 0)
    lines = [f"- 持仓：{len(pos_list)} 只 | 总资产：¥{total:,.0f} | 可用：¥{avail:,.0f}"]
    if not pos_list:
        lines.append("- 当前空仓或暂无持仓快照。")
    return "\n".join(lines)


def main():
    top_picks_data = load_json(TOP_PICKS_FILE, {})
    decision_data = load_json(DECISION_LOG, {})
    ai_summary = load_text(AI_SUMMARY_FILE)
    emotion = load_json(EMOTION_FILE, {})
    positions = load_json(PAPER_POSITIONS, {})

    picks = top_picks_data.get("top_picks", [])
    decisions = decision_data.get("decisions", [])
    emotion_data = emotion.get("emotion_analysis", {})

    emotion_score = emotion_data.get("emotion_score", "—")
    market_phase = emotion_data.get("market_phase", "unknown")
    risk_level = emotion_data.get("market_risk_level", "unknown")

    report_lines = [
        f"# 📊 今日市场复盘 — {TODAY}",
        "",
        "## 🔝 Top Picks 精选（含机器人来源与数据源）",
        "",
        render_top_picks(picks, decisions),
        "",
        "---",
        "",
        "## 🤖 Paper Decision 决策汇总",
        "",
        render_paper_decisions_summary(decisions),
        "",
        "---",
        "",
        "## 🧠 AI 市场总结",
        "",
        ai_summary or f"情绪评分 {emotion_score}/100，市场阶段 {market_phase}，风险等级 {risk_level}。",
        "",
        "---",
        "",
        "## 📋 模拟账户状态",
        "",
        render_paper_trade(positions),
        "",
        "---",
        "",
        "## 🛡️ Risk Validation 风险价格校验",
        "",
        render_risk_validation_summary(decision_data),
        "",
        "---",
        "",
        "## 🧾 Source Trace Policy",
        "",
        "每条数据类分析必须包含：source_agent / source_module / data_source / data_as_of / trace_id。",
        "",
        "*来源：Hermes AI Research Governance Cockpit | Phase-2.7D Source Trace Governance*",
    ]

    report_content = "\n".join(report_lines)
    output_file = REPORTS_DIR / f"{TODAY}.md"
    output_file.write_text(report_content, encoding="utf-8")

    index_file = REPORTS_DIR / "index.json"
    index = load_json(index_file, {"reports": []})
    reports = index.get("reports", [])
    if TODAY not in {r.get("date") for r in reports}:
        reports.insert(0, {"date": TODAY, "file": f"{TODAY}.md", "top_picks_count": len(picks)})
    index["reports"] = reports
    index["last_updated"] = datetime.now().isoformat()
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 日报生成完成: {output_file}")
    print(f"   Top Picks: {len(picks)}")
    print("   Source Trace: ENABLED")
    return report_content


if __name__ == "__main__":
    main()
