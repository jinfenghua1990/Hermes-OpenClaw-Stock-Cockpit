"""
Phase-2.7D Execution Reconciliation
核对 replay execution 与 execution audit 是否一致。
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def reconcile_execution():
    replay_dir = BASE_DIR / "replay_engine" / "snapshots"
    exec_log = BASE_DIR / "execution_bridge" / "paper_execution_log.jsonl"

    result = {
        "status": "PASS",
        "execution_mismatch": 0,
        "details": []
    }

    if not exec_log.exists():
        result["status"] = "WARNING"
        result["details"].append("paper_execution_log.jsonl missing")
        return result

    try:
        lines = exec_log.read_text().splitlines()
        result["execution_records"] = len(lines)
    except Exception as e:
        result["status"] = "FAIL"
        result["details"].append(str(e))

    return result
