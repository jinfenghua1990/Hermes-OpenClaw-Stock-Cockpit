#!/usr/bin/env python3
"""
Phase-2.7D Unified Governance Status Generator

生成 system_health/phase_2_7d_status.json，供 Cockpit / Replay / MAIN 快速读取。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

OUT_FILE = BASE_DIR / "system_health" / "phase_2_7d_status.json"


def _safe_call(fn, fallback):
    try:
        return fn()
    except Exception as exc:
        data = dict(fallback)
        data["error"] = str(exc)
        return data


def _check_governance_scalability():
    from system_health.check_phase_2_7d_governance import run_checks
    return run_checks()


def _check_source_trace():
    from system_health.check_source_trace_health import check_source_trace_health
    return check_source_trace_health()


def _check_baseline_drift():
    from governance.baseline_drift_monitor import check_baseline_drift
    return check_baseline_drift()


def _check_execution_reconciliation():
    from governance.reconciliation.execution_reconciliation import reconcile_execution
    return reconcile_execution()


def _check_governance_guard():
    from governance.governance_guard import run_governance_guard
    return run_governance_guard()


def _normalize_status(s):
    s = str(s or "UNKNOWN").upper()
    if s in ("PASS", "SUCCESS"):
        return "SUCCESS"
    if s in ("CRITICAL", "FAIL", "ERROR"):
        return "CRITICAL"
    return "WARNING"


def generate_status():
    governance = _safe_call(_check_governance_scalability, {"overall": "UNKNOWN", "checks": {}})
    source_trace = _safe_call(_check_source_trace, {"status": "UNKNOWN"})
    baseline_drift = _safe_call(_check_baseline_drift, {"status": "UNKNOWN", "baseline_drift_detected": False})
    reconciliation = _safe_call(_check_execution_reconciliation, {"status": "UNKNOWN"})
    guard = _safe_call(_check_governance_guard, {"status": "UNKNOWN", "governance_bypass_detected": False})

    statuses = [
        _normalize_status(governance.get("overall")),
        _normalize_status(source_trace.get("status")),
        _normalize_status(baseline_drift.get("status")),
        _normalize_status(reconciliation.get("status")),
        _normalize_status(guard.get("status")),
    ]

    overall = "SUCCESS"
    if "CRITICAL" in statuses:
        overall = "CRITICAL"
    elif "WARNING" in statuses:
        overall = "WARNING"

    status = {
        "phase": "Phase-2.7D",
        "generated_at": datetime.now().isoformat(),
        "overall_status": overall,
        "paper_only_lock": True,
        "source_trace_required": True,
        "baseline_frozen": True,
        "robot_6_10_status": "RESERVED_ONLY",
        "governance_bypass_detected": guard.get("governance_bypass_detected", False),
        "checks": {
            "governance_guard": guard,
            "governance_scalability": governance,
            "source_trace": source_trace,
            "baseline_drift": baseline_drift,
            "execution_reconciliation": reconciliation,
        }
    }

    OUT_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Phase-2.7D status written: {OUT_FILE}")
    print(f"   overall_status={overall}")
    return status


if __name__ == "__main__":
    generate_status()
