"""
Phase-2.7D Replay Snapshot Extension
为 replay snapshot 注入治理扩展字段。
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _safe_load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def build_phase_2_7d_extension():
    version_registry = _safe_load(BASE_DIR / "governance" / "registry" / "version_registry.json")
    strategy_registry = _safe_load(BASE_DIR / "governance" / "registry" / "strategy_registry.json")

    extension = {
        "phase": "Phase-2.7D",
        "version_registry": version_registry,
        "strategy_registry_ref": {
            "baseline": strategy_registry.get("baseline") if strategy_registry else None,
            "shadow_strategy_count": len(strategy_registry.get("shadow_strategies", [])) if strategy_registry else 0
        },
        "arbitration_result": {
            "enabled": True,
            "source": "governance/arbitration/agent_arbitrator.py"
        },
        "execution_reconciliation": {
            "enabled": True,
            "source": "governance/reconciliation/execution_reconciliation.py"
        },
        "baseline_drift_detected": False,
        "split_snapshot_ready": True
    }

    return extension


if __name__ == "__main__":
    print(json.dumps(build_phase_2_7d_extension(), ensure_ascii=False, indent=2))
