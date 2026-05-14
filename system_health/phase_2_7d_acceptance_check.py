#!/usr/bin/env python3
"""
Phase-2.7D Acceptance Check

一键验收：
- Replay 2.7D
- Source Trace
- Governance Guard
- Baseline Drift
- Execution Reconciliation
- Cockpit Entry
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TODAY = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = BASE_DIR / "system_health" / "phase_2_7d_acceptance_result.json"


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""


def check_replay_snapshot():
    snap = _load(BASE_DIR / "replay_engine" / "snapshots" / f"{TODAY}.json")
    required = [
        "phase",
        "source_trace_summary",
        "phase_2_7d_extension",
        "version_registry",
        "strategy_registry_ref",
        "execution_reconciliation",
        "baseline_drift_detected",
    ]
    missing = [k for k in required if k not in snap]
    return {
        "status": "PASS" if not missing and snap.get("phase") == "Phase-2.7D" else "FAIL",
        "missing": missing,
        "phase": snap.get("phase"),
        "snapshot_uuid": snap.get("snapshot_uuid"),
    }


def check_decision_source_trace():
    snap = _load(BASE_DIR / "replay_engine" / "snapshots" / f"{TODAY}.json")
    decisions = snap.get("decisions", [])
    required = ["source_agent", "source_module", "data_source", "data_as_of", "trace_id", "source_trace"]
    missing_records = []
    for d in decisions:
        missing = [k for k in required if not d.get(k)]
        if missing:
            missing_records.append({"symbol": d.get("股票代码"), "missing": missing})
    return {
        "status": "PASS" if not missing_records else "FAIL",
        "checked": len(decisions),
        "missing_records": missing_records[:20],
    }


def check_governance_guard():
    guard = _load(BASE_DIR / "system_health" / "governance_guard_status.json")
    return {
        "status": "PASS" if guard.get("status") == "PASS" and not guard.get("governance_bypass_detected") else "FAIL",
        "guard_status": guard.get("status"),
        "governance_bypass_detected": guard.get("governance_bypass_detected"),
        "violations": guard.get("violations", []),
    }


def check_phase_2_7d_status():
    status = _load(BASE_DIR / "system_health" / "phase_2_7d_status.json")
    required_checks = ["governance_guard", "governance_scalability", "source_trace", "baseline_drift", "execution_reconciliation"]
    checks = status.get("checks", {})
    missing = [k for k in required_checks if k not in checks]
    return {
        "status": "PASS" if not missing and status.get("overall_status") in ("SUCCESS", "WARNING") else "FAIL",
        "overall_status": status.get("overall_status"),
        "missing_checks": missing,
    }


def check_cockpit_entry():
    main = _read(BASE_DIR / "frontend" / "main.jsx")
    app = _read(BASE_DIR / "frontend" / "src" / "App2_7D.jsx")
    return {
        "status": "PASS" if "App2_7D" in main and "GovernanceScalabilityPanel" in app else "FAIL",
        "entry_uses_app2_7d": "App2_7D" in main,
        "panel_present": "GovernanceScalabilityPanel" in app,
    }


def run_acceptance():
    checks = {
        "replay_snapshot": check_replay_snapshot(),
        "decision_source_trace": check_decision_source_trace(),
        "governance_guard": check_governance_guard(),
        "phase_2_7d_status": check_phase_2_7d_status(),
        "cockpit_entry": check_cockpit_entry(),
    }

    overall = "PASS" if all(v.get("status") == "PASS" for v in checks.values()) else "FAIL"
    result = {
        "phase": "Phase-2.7D",
        "generated_at": datetime.now().isoformat(),
        "overall": overall,
        "checks": checks,
    }
    OUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Phase-2.7D Acceptance: {overall}")
    print(f"   output={OUT_FILE}")
    return result


if __name__ == "__main__":
    run_acceptance()
