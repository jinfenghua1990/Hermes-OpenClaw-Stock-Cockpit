#!/usr/bin/env python3
"""
Phase-2.8A Morning Feishu Pipeline

用途：
盘前生成/收口/推送飞书。

执行顺序：
1. Phase-2.7D governance tail
2. Feishu runtime push

仅允许：
PAPER_ONLY / OBSERVE_ONLY
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_FILE = BASE_DIR / "system_health" / "morning_feishu_pipeline_result.json"


def _run(label: str, script: Path, env=None):
    if not script.exists():
        return {
            "label": label,
            "status": "SKIPPED",
            "reason": f"missing: {script}",
        }

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=180,
        env=env or os.environ.copy(),
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
        "phase_2_7d_tail",
        BASE_DIR / "governance" / "run_phase_2_7d_tail.py",
    ))

    steps.append(_run(
        "feishu_runtime_push",
        BASE_DIR / "notification" / "feishu_runtime_push.py",
    ))

    overall = "SUCCESS"
    if any(s.get("status") == "ERROR" for s in steps):
        overall = "ERROR"
    elif any(s.get("status") == "SKIPPED" for s in steps):
        overall = "WARNING"

    report = {
        "phase": "Phase-2.8A",
        "pipeline": "morning_feishu_pipeline",
        "generated_at": datetime.now().isoformat(),
        "overall_status": overall,
        "paper_only_lock": True,
        "observe_only_lock": True,
        "steps": steps,
    }

    OUT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Morning Feishu Pipeline completed: {overall}")
    print(f"   output={OUT_FILE}")
    return 0 if overall == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
