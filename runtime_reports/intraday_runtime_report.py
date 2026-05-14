#!/usr/bin/env python3
"""
Phase-2.8C Intraday Runtime Report

生成每15分钟盘中深度报告。
飞书只推提醒，完整内容进入 runtime_reports。
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "runtime_reports" / "intraday"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def generate_intraday_runtime_report():
    now = datetime.now()
    slot = now.strftime("%H%M")
    today = now.strftime("%Y-%m-%d")

    position = _load(BASE_DIR / "position_runtime" / "position_runtime_summary.json", {})
    intraday = _load(BASE_DIR / "intraday_runtime" / "intraday_runtime_status.json", {})
    governance = _load(BASE_DIR / "system_health" / "phase_2_7d_status.json", {})
    decision_log = _load(BASE_DIR / "reports" / "paper_decision_log.json", {})
    top_picks = _load(BASE_DIR / "reports" / "top_picks.json", {})

    report = {
        "phase": "Phase-2.8C",
        "report_type": "intraday_runtime_report",
        "date": today,
        "slot": slot,
        "generated_at": now.isoformat(),
        "account_mode": "PAPER_ONLY",
        "observe_only": True,
        "position_runtime": {
            "position_count": position.get("position_count", 0),
            "alert_count": position.get("alert_count", 0),
            "alerts": position.get("alerts", []),
            "positions": position.get("positions", []),
        },
        "intraday_runtime": intraday,
        "paper_runtime": {
            "decision_count": len(decision_log.get("decisions", [])),
            "decisions": decision_log.get("decisions", [])[:20],
        },
        "top_picks_runtime": {
            "top_picks_count": len(top_picks.get("top_picks", [])),
            "top_picks": top_picks.get("top_picks", [])[:20],
        },
        "governance_runtime": {
            "overall_status": governance.get("overall_status", "UNKNOWN"),
            "governance_bypass_detected": governance.get("governance_bypass_detected", False),
            "checks": governance.get("checks", {}),
        },
        "runtime_priority": "position > risk > governance > top_picks",
    }

    out = OUT_DIR / f"{today}_{slot}_intraday_runtime_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = OUT_DIR / "latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Intraday Runtime Report: {out}")
    return report


if __name__ == "__main__":
    generate_intraday_runtime_report()
