#!/usr/bin/env python3
"""
Phase-2.8C Morning Feishu Pipeline

用途：
盘前生成/收口/推送飞书。

执行顺序：
1. 刷新 candidate pool
2. 运行 Phase-2.7D governance tail
3. 生成 intraday market data runtime
4. 刷新 realtime structure runtime
5. Feishu runtime push

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
        "candidate_pool_refresh",
        BASE_DIR / "intraday_runtime" / "candidate_pool_refresh_runtime.py",
    ))

    steps.append(_run(
        "candidate_pool_freshness_guard",
        BASE_DIR / "intraday_runtime" / "candidate_pool_freshness_guard.py",
    ))

    steps.append(_run(
        "phase_2_7d_tail",
        BASE_DIR / "governance" / "run_phase_2_7d_tail.py",
    ))

    steps.append(_run(
        "intraday_market_data_runtime",
        BASE_DIR / "intraday_runtime" / "intraday_market_data_runtime.py",
    ))

    steps.append(_run(
        "realtime_structure_refresh",
        BASE_DIR / "intraday_runtime" / "realtime_structure_refresh.py",
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
        "phase": "Phase-2.8C",
        "pipeline": "morning_feishu_pipeline",
        "generated_at": datetime.now().isoformat(),
        "overall_status": overall,
        "candidate_pool_refresh_required": True,
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
