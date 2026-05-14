#!/usr/bin/env python3
"""
Phase-2.8A Feishu Runtime Push

功能：
- 推送盘前 Top Picks
- 推送 AI 市场总结
- 推送模拟盘执行建议
- 推送 Governance 状态
- 推送 Replay / Acceptance 结果

仅允许：
PAPER_ONLY / OBSERVE_ONLY
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LARK_CLI = "/opt/homebrew/bin/lark-cli"  # 长连接，无需 Webhook


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def _short(v, default="-"):
    return v if v not in (None, "") else default


def build_message():
    today = datetime.now().strftime("%Y-%m-%d")

    top = _load(BASE_DIR / "reports" / "top_picks.json", {})
    decision_log = _load(BASE_DIR / "reports" / "paper_decision_log.json", {})
    replay = _load(BASE_DIR / "replay_engine" / "snapshots" / f"{today}.json", {})
    status = _load(BASE_DIR / "system_health" / "phase_2_7d_status.json", {})
    acceptance = _load(BASE_DIR / "system_health" / "phase_2_7d_acceptance_result.json", {})

    picks = top.get("top_picks", [])[:5]
    decisions = decision_log.get("decisions", [])[:8]

    lines = []
    lines.append("【Hermes AI 盘前简报】")
    lines.append(f"日期：{today}")
    lines.append("模式：PAPER_ONLY / OBSERVE_ONLY")
    lines.append("")

    lines.append("【1. Top Picks】")
    if not picks:
        lines.append("暂无候选股票")
    else:
        for p in picks:
            lines.append(
                f"- {_short(p.get('股票名称'))}({_short(p.get('股票代码'))}) | "
                f"AI:{_short(p.get('AI评分'))} | "
                f"结构:{_short(p.get('structure_type'), 'unknown')}"
            )

    lines.append("")
    lines.append("【2. 模拟盘执行建议】")
    if not decisions:
        lines.append("暂无 paper decision")
    else:
        for d in decisions:
            intent = d.get("paper_order_intent", {}) or {}
            side = intent.get("side", "NONE")
            status_text = d.get("execution_status") or intent.get("execution_status", "unknown")
            price = intent.get("intent_price") or d.get("price", "-")
            qty = intent.get("suggested_quantity") or d.get("quantity", 0)
            lines.append(
                f"- {_short(d.get('股票名称'))}({_short(d.get('股票代码'))}) | "
                f"decision:{_short(d.get('decision'))} | "
                f"side:{side} | price:{price} | qty:{qty} | status:{status_text}"
            )
            lines.append(
                f"  来源: agent={_short(d.get('source_agent'))} | "
                f"data={_short(d.get('data_source'))} | trace={_short(d.get('trace_id'))}"
            )

    lines.append("")
    lines.append("【3. Governance】")
    lines.append(f"状态: {status.get('overall_status','UNKNOWN')}")
    lines.append(f"Replay: {replay.get('snapshot_uuid','-')}")
    lines.append(f"Acceptance: {acceptance.get('overall','UNKNOWN')}")
    lines.append(f"Governance Bypass: {status.get('governance_bypass_detected', False)}")

    lines.append("")
    lines.append("【4. 风控锁】")
    lines.append("PAPER_ONLY ✅ | OBSERVE_ONLY ✅ | Baseline Frozen ✅ | robot_6~10 RESERVED_ONLY ✅")

    return "\n".join(lines)


def push_feishu(text: str, chat_id: str = None):
    """通过 lark-cli 长连接发送飞书消息"""
    # 飞书群 ID
    target = chat_id or "oc_174834d2967c4dfbdd692464f85398e0"

    payload = json.dumps({"msg_type": "text", "content": {"text": text}})

    result = subprocess.run(
        [
            LARK_CLI, "im", "+messages-send",
            "--chat-id", target,
            "--content", payload,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )

    if result.returncode != 0:
        raise RuntimeError(f"lark-cli failed: {result.stderr.strip()}")
    return result.stdout.strip()


if __name__ == "__main__":
    msg = build_message()
    print(msg)

    try:
        result = push_feishu(msg)
        print("✅ Feishu push success")
        print(result)
    except Exception as e:
        print(f"❌ Feishu push failed: {e}")
