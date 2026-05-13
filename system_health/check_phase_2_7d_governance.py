"""
Phase-2.7D Governance Scalability Health Checks
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _exists(path):
    return Path(path).exists()


def run_checks():
    checks = {}

    version_registry = BASE_DIR / "governance" / "registry" / "version_registry.json"
    strategy_registry = BASE_DIR / "governance" / "registry" / "strategy_registry.json"
    arbitration = BASE_DIR / "governance" / "arbitration" / "agent_arbitrator.py"
    reconciliation = BASE_DIR / "governance" / "reconciliation" / "execution_reconciliation.py"
    drift_monitor = BASE_DIR / "governance" / "baseline_drift_monitor.py"

    checks["version_registry_health"] = {
        "status": "SUCCESS" if _exists(version_registry) else "CRITICAL"
    }

    checks["strategy_registry_health"] = {
        "status": "SUCCESS" if _exists(strategy_registry) else "CRITICAL"
    }

    checks["agent_arbitration_health"] = {
        "status": "SUCCESS" if _exists(arbitration) else "WARNING"
    }

    checks["execution_reconciliation_health"] = {
        "status": "SUCCESS" if _exists(reconciliation) else "WARNING"
    }

    checks["baseline_drift_health"] = {
        "status": "SUCCESS" if _exists(drift_monitor) else "CRITICAL"
    }

    overall = "SUCCESS"
    if any(v["status"] == "CRITICAL" for v in checks.values()):
        overall = "CRITICAL"
    elif any(v["status"] == "WARNING" for v in checks.values()):
        overall = "WARNING"

    return {
        "phase": "Phase-2.7D",
        "overall": overall,
        "checks": checks,
    }


if __name__ == "__main__":
    print(json.dumps(run_checks(), ensure_ascii=False, indent=2))
