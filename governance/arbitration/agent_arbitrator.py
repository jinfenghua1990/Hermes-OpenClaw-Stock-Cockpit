"""
Phase-2.7D Agent Arbitration Layer
用于处理 robot_1~5 冲突。
"""

from collections import Counter


def arbitrate(agent_votes):
    """
    agent_votes:
    [
      {
        "agent_id": "robot_1",
        "decision": "BUY",
        "confidence": 0.72
      }
    ]
    """

    if not agent_votes:
        return {
            "final_decision": "SKIP",
            "decision_source": "no_votes",
            "agent_votes": [],
            "conflict_detected": False,
            "conflict_level": "low",
            "arbitration_reason": "empty_votes"
        }

    decisions = [v.get("decision", "SKIP") for v in agent_votes]
    counter = Counter(decisions)

    final_decision = counter.most_common(1)[0][0]
    conflict_detected = len(counter) > 1

    if len(counter) >= 3:
        conflict_level = "high"
    elif len(counter) == 2:
        conflict_level = "medium"
    else:
        conflict_level = "low"

    return {
        "final_decision": final_decision,
        "decision_source": "agent_arbitrator",
        "agent_votes": agent_votes,
        "conflict_detected": conflict_detected,
        "conflict_level": conflict_level,
        "arbitration_reason": "majority_vote"
    }
