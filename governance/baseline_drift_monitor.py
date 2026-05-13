"""
Phase-2.7D Baseline Drift Monitor
检测 shadow strategy / sandbox 参数是否软污染 baseline runtime。
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SHADOW_HINTS = [
    "shadow_strategy",
    "shadow_strategy_id",
    "sandbox_strategy",
    "experimental_strategy",
    "auto_tuned",
    "auto_learned",
]

BASELINE_RUNTIME_FILES = [
    BASE_DIR / "reports" / "paper_decision_log.json",
    BASE_DIR / "reports" / "top_picks.json",
]


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _contains_shadow_hint(obj):
    text = json.dumps(obj, ensure_ascii=False).lower()
    return any(h.lower() in text for h in SHADOW_HINTS)


def check_baseline_drift():
    findings = []

    for path in BASELINE_RUNTIME_FILES:
        if not path.exists():
            continue
        data = _load_json(path)
        if data is None:
            continue
        if _contains_shadow_hint(data):
            findings.append({
                "file": str(path.relative_to(BASE_DIR)),
                "reason": "shadow_or_experimental_strategy_marker_detected_in_baseline_runtime"
            })

    drift = len(findings) > 0
    return {
        "baseline_drift_detected": drift,
        "status": "CRITICAL" if drift else "PASS",
        "findings": findings,
        "baseline_mutation_allowed": False,
        "monitor": "baseline_drift_monitor",
        "version": "phase_2_7d"
    }


if __name__ == "__main__":
    print(json.dumps(check_baseline_drift(), ensure_ascii=False, indent=2))
