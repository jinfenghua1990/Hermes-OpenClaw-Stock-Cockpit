"""
Phase-2.7D Replay Source Trace Runtime
为 replay snapshot / paper decision / cockpit 注入来源链路。
"""

from datetime import datetime
import uuid


def build_runtime_source_trace(
    symbol="",
    source_agent="robot_1",
    source_module="runtime_engine",
    data_source="runtime_cache",
    replay_snapshot="",
    confidence=0.0,
):
    return {
        "symbol": symbol,
        "source_agent": source_agent,
        "source_module": source_module,
        "data_source": data_source,
        "data_as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trace_id": str(uuid.uuid4())[:8],
        "replay_snapshot": replay_snapshot,
        "confidence": round(float(confidence), 4),
        "runtime_phase": "Phase-2.7D",
    }
