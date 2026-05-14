#!/usr/bin/env python3
"""
Phase-2.8B Intraday Feishu Push

每15分钟推送：
- Position Runtime
- 风险警报
- Governance Runtime

仅允许：
PAPER_ONLY
"""

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent.parent
WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def build_message():
    runtime = _load(
        BASE_DIR / "intraday_runtime" / "intraday_runtime_status.json",
        {}
    )

    lines = []

    lines.append(f"【{datetime.now().strftime('%H:%M')} Intraday Runtime】")
    lines.append("")

    pos = runtime.get("position_runtime", {})
    gov = runtime.get("governance_runtime", {})
    replay = runtime.get("replay_runtime", {})

    lines.append("【持仓 Runtime】")
    lines.append(f"持仓数量: {pos.get('position_count',0)}")
    lines.append(f"风险警报: {pos.get('alert_count',0)}")

    alerts = pos.get("alerts", [])[:5]

    if alerts:
        for a in alerts:
            lines.append(
                f"- {a.get('name')}({a.get('symbol')}) | {a.get('type')}"
            )
    else:
        lines.append("暂无风险警报")

    lines.append("")
    lines.append("【Governance】")
    lines.append(f"状态: {gov.get('overall_status','UNKNOWN')}")
    lines.append(
        f"Governance Bypass: {gov.get('governance_bypass_detected', False)}"
    )

    lines.append("")
    lines.append("【Replay】")
    lines.append(f"Acceptance: {replay.get('acceptance','UNKNOWN')}")

    lines.append("")
    lines.append("PAPER_ONLY ✅ | OBSERVE_ONLY ✅")

    return "\n".join(lines)


def push_feishu(text: str):
    if not WEBHOOK:
        raise RuntimeError("FEISHU_WEBHOOK not configured")

    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }

    req = Request(
        WEBHOOK,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


if __name__ == "__main__":
    msg = build_message()
    print(msg)

    try:
        result = push_feishu(msg)
        print("✅ Intraday Feishu push success")
        print(result)
    except Exception as e:
        print(f"❌ Intraday Feishu push failed: {e}")
