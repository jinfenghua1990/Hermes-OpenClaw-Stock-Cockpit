"""
Phase-2.7D Source Trace Health
检查 reports/replay 是否存在来源可追踪字段。
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

REQUIRED = [
    "source_agent",
    "source_module",
    "data_source",
    "data_as_of",
    "trace_id",
]


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def check_source_trace_health():
    report = _load(BASE_DIR / "reports" / "paper_decision_log.json")
    decisions = report.get("decisions", [])

    missing_total = 0
    critical_total = 0

    for d in decisions:
        for field in REQUIRED:
            if not d.get(field):
                missing_total += 1
                if field == "data_as_of":
                    critical_total += 1

    status = "SUCCESS"

    if critical_total > 0:
        status = "CRITICAL"
    elif missing_total > 0:
        status = "WARNING"

    return {
        "status": status,
        "checked_decisions": len(decisions),
        "missing_fields": missing_total,
        "critical_missing": critical_total,
        "phase": "Phase-2.7D",
        "source_trace_required": True,
    }


if __name__ == "__main__":
    print(json.dumps(check_source_trace_health(), ensure_ascii=False, indent=2))
