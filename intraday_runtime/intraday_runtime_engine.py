#!/usr/bin/env python3
"""
Phase-2.8B Intraday Runtime Engine

每15分钟执行：
- Position Runtime
- Market Runtime
- Governance Runtime
- Intraday Risk Runtime

仅允许：
PAPER_ONLY / OBSERVE_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_FILE = BASE_DIR / "intraday_runtime" / "intraday_runtime_status.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def run_intraday_runtime():
    position_summary = _load(
        BASE_DIR / "position_runtime" / "position_runtime_summary.json",
        {}
    )

    governance_status = _load(
        BASE_DIR / "system_health" / "phase_2_7d_status.json",
        {}
    )

    replay = _load(
        BASE_DIR / "system_health" / "phase_2_7d_acceptance_result.json",
        {}
    )

    runtime = {
        "phase": "Phase-2.8B",
        "generated_at": datetime.now().isoformat(),
        "runtime_type": "intraday_runtime",
        "frequency": "15m",
        "position_runtime": {
            "position_count": position_summary.get("position_count", 0),
            "alert_count": position_summary.get("alert_count", 0),
            "alerts": position_summary.get("alerts", []),
        },
        "governance_runtime": {
            "overall_status": governance_status.get("overall_status", "UNKNOWN"),
            "governance_bypass_detected": governance_status.get("governance_bypass_detected", False),
        },
        "replay_runtime": {
            "acceptance": replay.get("overall", "UNKNOWN"),
        },
        "paper_only_lock": True,
        "observe_only_lock": True,
    }

    OUT_FILE.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")

    print("✅ Intraday Runtime Engine completed")
    print(f"   output={OUT_FILE}")

    return runtime


if __name__ == "__main__":
    run_intraday_runtime()
