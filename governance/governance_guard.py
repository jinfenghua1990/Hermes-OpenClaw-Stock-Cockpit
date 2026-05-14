#!/usr/bin/env python3
"""
Phase-2.7D Governance Guard

用于检查关键治理锁是否被绕过。
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

REQUIRED_LOCKS = {
    "SOUL_MODE": "OBSERVE_ONLY",
    "account_mode": "PAPER_ONLY",
    "baseline_frozen": True,
    "robot_6_10_status": "RESERVED_ONLY",
}


def _safe_load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def run_governance_guard():
    version_registry = _safe_load(
        BASE_DIR / "governance" / "registry" / "version_registry.json",
        {}
    )

    checks = {}
    violations = []

    actual = {
        "SOUL_MODE": version_registry.get("soul_mode"),
        "account_mode": version_registry.get("account_mode"),
        "baseline_frozen": version_registry.get("baseline_frozen"),
        "robot_6_10_status": version_registry.get("robot_6_10_status"),
    }

    for key, expected in REQUIRED_LOCKS.items():
        value = actual.get(key)
        passed = value == expected

        checks[key] = {
            "expected": expected,
            "actual": value,
            "passed": passed,
        }

        if not passed:
            violations.append({
                "field": key,
                "expected": expected,
                "actual": value,
            })

    status = "PASS" if not violations else "CRITICAL"

    report = {
        "phase": "Phase-2.7D",
        "generated_at": datetime.now().isoformat(),
        "status": status,
        "checks": checks,
        "violations": violations,
        "governance_bypass_detected": bool(violations),
    }

    out_path = BASE_DIR / "system_health" / "governance_guard_status.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Governance Guard: {status}")
    if violations:
        print(f"   violations={len(violations)}")

    return report


if __name__ == "__main__":
    run_governance_guard()
