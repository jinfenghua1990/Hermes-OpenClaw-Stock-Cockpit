#!/usr/bin/env python3
"""
Phase-2.7D Daily Pipeline Tail

每日 pipeline 最后运行：
1. Governance Guard
2. 生成 replay snapshot
3. 生成 Phase-2.7D unified governance status
4. 输出收口结果

不修改 baseline，不改变 account_mode，不触碰 robot_6~10。
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _run(label, script_path):
    if not Path(script_path).exists():
        return {
            "label": label,
            "status": "SKIPPED",
            "reason": f"missing: {script_path}"
        }

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "label": label,
        "status": "SUCCESS" if result.returncode == 0 else "ERROR",
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def main():
    steps = []

    steps.append(_run(
        "governance_guard",
        BASE_DIR / "governance" / "governance_guard.py",
    ))

    steps.append(_run(
        "replay_snapshot_phase_2_7d",
        BASE_DIR / "replay_engine" / "generate_replay_snapshot.py",
    ))

    steps.append(_run(
        "phase_2_7d_status",
        BASE_DIR / "system_health" / "generate_phase_2_7d_status.py",
    ))

    overall = "SUCCESS"
    if any(s.get("status") == "ERROR" for s in steps):
        overall = "ERROR"
    elif any(s.get("status") == "SKIPPED" for s in steps):
        overall = "WARNING"

    report = {
        "phase": "Phase-2.7D",
        "generated_at": datetime.now().isoformat(),
        "overall_status": overall,
        "paper_only_lock": True,
        "baseline_frozen": True,
        "robot_6_10_status": "RESERVED_ONLY",
        "steps": steps,
    }

    out_path = BASE_DIR / "system_health" / "phase_2_7d_tail_result.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Phase-2.7D Tail completed: {overall}")
    print(f"   output={out_path}")
    return 0 if overall == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
