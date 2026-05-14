#!/usr/bin/env python3
"""
Phase-2.8C Intraday Runtime Engine

每15分钟执行：
- Candidate Pool Refresh Runtime
- Position Runtime
- Market Runtime
- Governance Runtime
- Intraday Risk Runtime
- Realtime Structure Runtime

仅允许：
PAPER_ONLY / OBSERVE_ONLY
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_FILE = BASE_DIR / "intraday_runtime" / "intraday_runtime_status.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def _run_runtime(script: Path):
    if not script.exists():
        return {
            "status": "SKIPPED",
            "script": str(script),
        }

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )

    return {
        "status": "SUCCESS" if result.returncode == 0 else "ERROR",
        "script": str(script),
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }


def run_intraday_runtime():
    runtime_steps = {
        "candidate_pool_refresh": _run_runtime(
            BASE_DIR / "intraday_runtime" / "candidate_pool_refresh_runtime.py"
        ),
        "intraday_market_data_runtime": _run_runtime(
            BASE_DIR / "intraday_runtime" / "intraday_market_data_runtime.py"
        ),
        "realtime_structure_refresh": _run_runtime(
            BASE_DIR / "intraday_runtime" / "realtime_structure_refresh.py"
        ),
    }

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

    candidate_pool = _load(
        BASE_DIR / "portfolio" / "candidate_rankings.json",
        {}
    )

    realtime_structure = _load(
        BASE_DIR / "intraday_runtime" / "realtime_structure_runtime.json",
        {}
    )

    runtime = {
        "phase": "Phase-2.8C",
        "generated_at": datetime.now().isoformat(),
        "runtime_type": "intraday_runtime",
        "frequency": "15m",
        "runtime_steps": runtime_steps,
        "candidate_pool_runtime": {
            "candidate_count": candidate_pool.get("candidate_count", 0),
            "runtime_fresh": candidate_pool.get("runtime_fresh", False),
        },
        "realtime_structure_runtime": {
            "total": realtime_structure.get("total", 0),
            "stale_count": realtime_structure.get("stale_count", 0),
            "status": realtime_structure.get("status", "UNKNOWN"),
        },
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
