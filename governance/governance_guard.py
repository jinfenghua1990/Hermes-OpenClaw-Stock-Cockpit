#!/usr/bin/env python3
"""
Phase-2.7D Governance Guard

检查关键治理锁是否被绕过。
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

REQUIRED_LOCKS = {
    "soul_mode": "OBSERVE_ONLY",
    "account_mode": "PAPER_ONLY",
    "baseline_frozen": True,
    "robot_6_10_status": "RESERVED_ONLY",
}


def _safe_load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def _get_lock_value(registry: dict, key: str):
    # 兼容历史大小写字段：SOUL_MODE / soul_mode
    return registry.get(key, registry.get(key.upper()))


def run_governance_guard():
    version_registry = _safe_load(
        BASE_DIR / "governance" / "registry" / "version_registry.json",
        {}
    )

    checks = {}
    violations = []

    for key, expected in REQUIRED_LOCKS.items():
        value = _get_lock_value(version_registry, key)
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
