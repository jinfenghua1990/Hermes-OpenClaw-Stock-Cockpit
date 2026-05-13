"""
Phase-2.7D Agent Trace Layer
统一 robot_1~5 trace schema。
"""

from datetime import datetime
import uuid


def build_agent_trace(agent_id, decision, confidence=0.0, reason="", runtime_cycle_id=None, parent_trace_id=None):
    return {
        "trace_id": str(uuid.uuid4())[:8],
        "parent_trace_id": parent_trace_id,
        "runtime_cycle_id": runtime_cycle_id,
        "agent_id": agent_id,
        "decision": decision,
        "confidence": round(float(confidence), 4),
        "reason": reason,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
