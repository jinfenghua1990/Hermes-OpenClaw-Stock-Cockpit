"""
Phase-2.7D Source Trace Schema
统一所有研究/决策/报告的数据来源与机器人来源。
"""

from datetime import datetime


def build_source_trace(
    *,
    symbol="",
    source_agent="unknown_agent",
    source_module="unknown_module",
    data_source="unknown_source",
    data_as_of="",
    trace_id="",
    parent_trace_id="",
    replay_snapshot="",
    confidence=0.0,
):
    return {
        "symbol": symbol,
        "source_agent": source_agent,
        "source_module": source_module,
        "data_source": data_source,
        "data_as_of": data_as_of,
        "trace_id": trace_id,
        "parent_trace_id": parent_trace_id,
        "replay_snapshot": replay_snapshot,
        "confidence": round(float(confidence), 4),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "schema": "phase_2_7d_source_trace"
    }
