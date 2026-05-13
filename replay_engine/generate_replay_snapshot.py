#!/usr/bin/env python3
"""
Phase-2.7D Replay Snapshot Persistence

Includes:
- Phase-2.6D Risk Price Validation summary
- Phase-2.7A Market Structure summary
- Phase-2.7B Paper Execution summary
- Phase-2.7D Governance Scalability extension
- Phase-2.7D Source Trace Governance
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
SELF_DIR = Path(__file__).parent.resolve()


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def _load_execution_summary() -> dict:
    log_file = BASE / "execution_bridge" / "paper_execution_log.jsonl"
    if not log_file.exists():
        return {
            "manual_pending_count": 0,
            "manual_filled_count": 0,
            "manual_cancelled_count": 0,
            "skipped_count": 0,
            "total_count": 0,
        }

    pending = filled = cancelled = skipped = 0
    try:
        for line in log_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            status = rec.get("execution_status") or rec.get("status", "")
            if status == "manual_pending":
                pending += 1
            elif status in ("manual_filled", "filled"):
                filled += 1
            elif status in ("manual_cancelled", "cancelled"):
                cancelled += 1
            elif status == "skipped":
                skipped += 1
    except Exception:
        pass

    return {
        "manual_pending_count": pending,
        "manual_filled_count": filled,
        "manual_cancelled_count": cancelled,
        "skipped_count": skipped,
        "total_count": pending + filled + cancelled + skipped,
    }


def _load_phase_2_7d_extension() -> dict:
    try:
        from phase_2_7d_snapshot_extension import build_phase_2_7d_extension
        ext = build_phase_2_7d_extension()
    except Exception:
        ext = {
            "phase": "Phase-2.7D",
            "version_registry": load_json(BASE / "governance" / "registry" / "version_registry.json", {}),
            "strategy_registry_ref": {},
            "arbitration_result": {"enabled": False},
            "execution_reconciliation": {"enabled": False, "status": "UNKNOWN"},
            "baseline_drift_detected": False,
            "split_snapshot_ready": False,
        }

    try:
        from governance.baseline_drift_monitor import check_baseline_drift
        drift = check_baseline_drift()
        ext["baseline_drift_detected"] = drift.get("baseline_drift_detected", False)
        ext["baseline_drift_result"] = drift
    except Exception:
        pass

    try:
        from governance.reconciliation.execution_reconciliation import reconcile_execution
        reconciliation = reconcile_execution()
        ext["execution_reconciliation"] = reconciliation
    except Exception:
        pass

    return ext


def _default_source_trace(d: dict, symbol: str, snapshot_uuid: str, now: str):
    source_agent = d.get("source_agent") or d.get("agent_id") or "robot_1"
    source_module = d.get("source_module") or "paper_decision_engine"
    data_source = d.get("data_source") or d.get("source") or "paper_decision_log"
    data_as_of = d.get("data_as_of") or d.get("risk_data_as_of") or d.get("generated_at") or now
    trace_id = d.get("trace_id") or str(uuid.uuid4())[:8]

    return {
        "symbol": symbol,
        "source_agent": source_agent,
        "source_module": source_module,
        "data_source": data_source,
        "data_as_of": data_as_of,
        "trace_id": trace_id,
        "parent_trace_id": d.get("parent_trace_id", ""),
        "replay_snapshot": snapshot_uuid,
        "confidence": d.get("confidence", d.get("structure_confidence", 0.0)),
        "schema": "phase_2_7d_source_trace",
    }


def _build_decisions(paper_decisions, snapshot_uuid: str, now: str):
    decisions_out = []
    for d in paper_decisions:
        symbol = d.get("股票代码", d.get("symbol", ""))
        source_trace = d.get("source_trace") or _default_source_trace(d, symbol, snapshot_uuid, now)

        decisions_out.append({
            "股票代码": symbol,
            "股票名称": d.get("股票名称", d.get("name", "")),
            "decision": d.get("decision", "no_action"),
            "action": d.get("action", ""),
            "reason": d.get("reason", ""),
            "skip_reason": d.get("skip_reason", ""),
            "quantity": d.get("quantity", 0),
            "price": d.get("price", 0.0),
            "structure_type": d.get("structure_type", "unknown"),
            "structure_confidence": d.get("structure_confidence", 0.0),
            "structure_source": d.get("structure_source", "unknown"),
            "structure_version": d.get("structure_version", "2.7a"),
            "swing_low": d.get("swing_low", 0.0),
            "swing_high": d.get("swing_high", 0.0),
            "support_price": d.get("support_price", 0.0),
            "pressure_price": d.get("pressure_price", 0.0),
            "paper_order_intent": d.get("paper_order_intent", {}),
            "execution_status": d.get("execution_status", "unknown"),
            "execution_id": d.get("execution_id", ""),
            "agent_trace": d.get("agent_trace", []),
            "arbitration_result": d.get("arbitration_result", {}),
            "source_agent": source_trace.get("source_agent"),
            "source_module": source_trace.get("source_module"),
            "data_source": source_trace.get("data_source"),
            "data_as_of": source_trace.get("data_as_of"),
            "trace_id": source_trace.get("trace_id"),
            "source_trace": source_trace,
        })
    return decisions_out


def _source_trace_summary(decisions_out):
    total = len(decisions_out)
    missing_source_agent = sum(1 for d in decisions_out if not d.get("source_agent"))
    missing_data_source = sum(1 for d in decisions_out if not d.get("data_source"))
    missing_data_as_of = sum(1 for d in decisions_out if not d.get("data_as_of"))
    missing_trace_id = sum(1 for d in decisions_out if not d.get("trace_id"))

    status = "PASS"
    if missing_data_as_of > 0:
        status = "CRITICAL"
    elif missing_source_agent > 0 or missing_data_source > 0 or missing_trace_id > 0:
        status = "WARNING"

    return {
        "status": status,
        "total": total,
        "missing_source_agent": missing_source_agent,
        "missing_data_source": missing_data_source,
        "missing_data_as_of": missing_data_as_of,
        "missing_trace_id": missing_trace_id,
        "source_trace_required": True,
    }


def generate_replay_snapshot():
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    snapshot_uuid = str(uuid.uuid4())[:8]
    snap_dir = SELF_DIR / "snapshots"
    snap_dir.mkdir(exist_ok=True)

    gov_snap = load_json(BASE / "governance" / "snapshots" / f"{today}.json")
    top_picks = load_json(BASE / "reports" / "top_picks.json", {})
    decision_log = load_json(BASE / "reports" / "paper_decision_log.json", {})

    validation_results = decision_log.get("validation_results", [])
    paper_decisions = decision_log.get("decisions", [])
    decisions_out = _build_decisions(paper_decisions, snapshot_uuid, now)

    paper_skip_count = sum(
        1 for d in paper_decisions
        if d.get("decision") in ("paper_skip", "no_action")
    )
    invalid_count = sum(1 for r in validation_results if r.get("is_valid") is False)
    invalid_struct_count = sum(1 for d in decisions_out if d.get("structure_type") == "invalid")
    fallback_struct_count = sum(1 for d in decisions_out if d.get("structure_type") == "fallback_ma20")

    phase_2_7d_extension = _load_phase_2_7d_extension()
    source_trace_summary = _source_trace_summary(decisions_out)

    snapshot = {
        "snapshot_date": today,
        "generated_at": now,
        "phase": "Phase-2.7D",
        "soul_mode": "OBSERVE_ONLY",
        "account_mode": "PAPER_ONLY",
        "observation_freeze": True,
        "risk_validation_enabled": True,
        "source_trace_required": True,
        "governance_snapshot_path": str(BASE / "governance" / "snapshots" / f"{today}.json"),
        "daily_report_path": str(BASE / "reports" / "history" / f"{today}.md"),
        "health_check_status": gov_snap.get("health_check_status", "WARNING"),
        "risk_validation_summary": {
            "total": len(validation_results),
            "invalid_count": invalid_count,
            "pass_count": sum(1 for r in validation_results if r.get("is_valid") is True),
        },
        "market_structure_summary": {
            "total": len(decisions_out),
            "invalid_count": invalid_struct_count,
            "fallback_ma20_count": fallback_struct_count,
            "valid_count": len(decisions_out) - invalid_struct_count,
            "valid_rate": round((len(decisions_out) - invalid_struct_count) / len(decisions_out), 3) if decisions_out else 0,
        },
        "source_trace_summary": source_trace_summary,
        "top_picks_count": len(top_picks.get("top_picks", [])),
        "paper_decision_count": len(paper_decisions),
        "paper_skip_count": paper_skip_count,
        "invalid_price_structure_count": invalid_count,
        "decisions": decisions_out,
        "execution_summary": _load_execution_summary(),
        "phase_2_7d_extension": phase_2_7d_extension,
        "version_registry": phase_2_7d_extension.get("version_registry"),
        "strategy_registry_ref": phase_2_7d_extension.get("strategy_registry_ref"),
        "execution_reconciliation": phase_2_7d_extension.get("execution_reconciliation"),
        "baseline_drift_detected": phase_2_7d_extension.get("baseline_drift_detected", False),
        "runtime_cycle_id": today,
        "snapshot_uuid": snapshot_uuid,
    }

    out_path = snap_dir / f"{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"✅ Replay Snapshot: {out_path}")
    print(f"   Date: {today} | UUID: {snapshot['snapshot_uuid']}")
    print(f"   TopPicks: {snapshot['top_picks_count']} | Decisions: {snapshot['paper_decision_count']}")
    print(f"   Invalid price structure: {invalid_count} | Paper skip: {paper_skip_count}")
    print(f"   Source Trace: {source_trace_summary['status']}")
    print(f"   Phase: {snapshot['phase']}")
    return snapshot


if __name__ == "__main__":
    generate_replay_snapshot()
