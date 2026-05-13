#!/usr/bin/env python3
"""
Phase-2.7D Eastmoney Paper Execution Bridge

职责：
1. 从 paper_decision_engine 接收 paper_order_intent
2. 管理 execution_bridge/paper_execution_log.jsonl
3. 提供人工/自动模拟盘执行记录桥
4. 所有执行意图与执行日志必须带 source_trace
5. 仅允许 PAPER_ONLY，不做实盘
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
BRIDGE_DIR = Path(__file__).parent.resolve()
LOG_FILE = BRIDGE_DIR / "paper_execution_log.jsonl"


def _now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def _load_decision_log():
    return _load_json(BASE / "reports" / "paper_decision_log.json", {"decisions": []})


def _load_top_picks():
    return _load_json(BASE / "reports" / "top_picks.json", {"top_picks": []})


def _load_latest_snapshot_uuid():
    today = datetime.now().strftime("%Y-%m-%d")
    data = _load_json(BASE / "replay_engine" / "snapshots" / f"{today}.json", {})
    return data.get("snapshot_uuid", "")


def _build_source_trace(symbol: str, dec: dict, snapshot_uuid: str):
    source_trace = dec.get("source_trace", {}) if isinstance(dec, dict) else {}
    return {
        "symbol": symbol,
        "source_agent": dec.get("source_agent") or source_trace.get("source_agent") or "robot_5",
        "source_module": dec.get("source_module") or source_trace.get("source_module") or "eastmoney_paper_bridge",
        "data_source": dec.get("data_source") or source_trace.get("data_source") or "paper_decision_log",
        "data_as_of": dec.get("data_as_of") or source_trace.get("data_as_of") or dec.get("generated_at") or _now(),
        "trace_id": dec.get("trace_id") or source_trace.get("trace_id") or str(uuid.uuid4())[:8],
        "parent_trace_id": dec.get("parent_trace_id") or source_trace.get("parent_trace_id", ""),
        "replay_snapshot": snapshot_uuid,
        "schema": "phase_2_7d_execution_source_trace",
    }


def build_paper_order_intent(
    symbol: str,
    name: str,
    decision: str,
    price: float,
    quantity: int,
    risk_validation_passed: bool,
    structure_type: str,
    structure_confidence: float,
    max_amount: float = 0.0,
    side: str = "NONE",
    source_trace: dict | None = None,
) -> dict:
    if decision == "paper_skip":
        side = "NONE"
        quantity = 0
        max_amount = 0.0
        execution_status = "skipped"
    else:
        execution_status = "manual_pending"

    return {
        "symbol": symbol,
        "name": name,
        "side": side,
        "intent_price": price,
        "suggested_quantity": quantity,
        "max_amount": max_amount,
        "execution_mode": "MANUAL_CONFIRM_EXECUTION",
        "execution_target": "eastmoney_paper",
        "execution_status": execution_status,
        "risk_validation_passed": risk_validation_passed,
        "structure_type": structure_type,
        "structure_confidence": structure_confidence,
        "order_intent_price": price,
        "suggested_quantity_int": quantity,
        "account_mode": "PAPER_ONLY",
        "source_trace": source_trace or {},
        "source_agent": (source_trace or {}).get("source_agent", "robot_5"),
        "source_module": (source_trace or {}).get("source_module", "eastmoney_paper_bridge"),
        "data_source": (source_trace or {}).get("data_source", "paper_decision_log"),
        "data_as_of": (source_trace or {}).get("data_as_of", _now()),
        "trace_id": (source_trace or {}).get("trace_id", str(uuid.uuid4())[:8]),
    }


def inject_order_intents_to_decisions(decisions: list, top_picks: dict) -> list:
    snapshot_uuid = _load_latest_snapshot_uuid()
    price_map = {}
    for pick in top_picks.get("top_picks", []):
        sym = pick.get("股票代码", "")
        price_map[sym] = {
            "current_price": pick.get("最新价", pick.get("价格", 0.0)),
            "change_pct": pick.get("涨跌幅", 0.0),
            "ma20": pick.get("MA20", 0.0),
        }

    updated = []
    for dec in decisions:
        sym = dec.get("股票代码", dec.get("symbol", ""))
        name = dec.get("股票名称", dec.get("name", ""))
        decision = dec.get("decision", "no_action")
        current_price = price_map.get(sym, {}).get("current_price", dec.get("price", 0.0))
        source_trace = _build_source_trace(sym, dec, snapshot_uuid)

        if decision == "paper_buy":
            side = "BUY"
            quantity = dec.get("quantity", 0)
            max_amount = dec.get("max_amount", 0.0)
        elif decision == "paper_sell":
            side = "SELL"
            quantity = dec.get("quantity", 0)
            max_amount = 0.0
        else:
            side = "NONE"
            quantity = 0
            max_amount = 0.0

        order_intent = build_paper_order_intent(
            symbol=sym,
            name=name,
            decision=decision,
            price=current_price,
            quantity=quantity,
            risk_validation_passed=dec.get("risk_validation_passed", False),
            structure_type=dec.get("structure_type", "unknown"),
            structure_confidence=dec.get("structure_confidence", 0.0),
            max_amount=max_amount,
            side=side,
            source_trace=source_trace,
        )

        dec_copy = dict(dec)
        dec_copy["paper_order_intent"] = order_intent
        dec_copy["execution_status"] = order_intent.get("execution_status", "unknown")
        dec_copy["source_trace"] = source_trace
        dec_copy["source_agent"] = source_trace.get("source_agent")
        dec_copy["source_module"] = source_trace.get("source_module")
        dec_copy["data_source"] = source_trace.get("data_source")
        dec_copy["data_as_of"] = source_trace.get("data_as_of")
        dec_copy["trace_id"] = source_trace.get("trace_id")
        updated.append(dec_copy)

    return updated


def record_execution(execution_record: dict) -> str:
    execution_id = execution_record.get("execution_id") or str(uuid.uuid4())[:8]
    execution_record["execution_id"] = execution_id
    execution_record.setdefault("account_mode", "PAPER_ONLY")
    execution_record.setdefault("source", "eastmoney_paper_manual")
    execution_record.setdefault("execution_time", _now())

    source_trace = execution_record.get("source_trace") or {
        "symbol": execution_record.get("symbol", ""),
        "source_agent": execution_record.get("source_agent", "robot_5"),
        "source_module": "eastmoney_paper_bridge.record_execution",
        "data_source": "execution_bridge",
        "data_as_of": execution_record.get("execution_time", _now()),
        "trace_id": execution_record.get("trace_id", str(uuid.uuid4())[:8]),
        "replay_snapshot": execution_record.get("snapshot_uuid", ""),
        "schema": "phase_2_7d_execution_source_trace",
    }

    execution_record["source_trace"] = source_trace
    execution_record["source_agent"] = source_trace.get("source_agent")
    execution_record["source_module"] = source_trace.get("source_module")
    execution_record["data_source"] = source_trace.get("data_source")
    execution_record["data_as_of"] = source_trace.get("data_as_of")
    execution_record["trace_id"] = source_trace.get("trace_id")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(execution_record, ensure_ascii=False) + "\n")

    return execution_id


def update_decision_execution_status(
    symbol: str,
    execution_id: str,
    execution_status: str,
    executed_price: float = 0.0,
    quantity: int = 0,
    execution_time: str = "",
) -> bool:
    if not LOG_FILE.exists():
        return False

    records = []
    updated = False
    now = execution_time or _now()

    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("symbol") == symbol and rec.get("execution_id") == execution_id:
            rec["execution_status"] = execution_status
            if executed_price > 0:
                rec["executed_price"] = executed_price
            if quantity > 0:
                rec["quantity"] = quantity
            if execution_status == "manual_filled":
                rec["amount"] = round(executed_price * quantity, 2)
            rec["execution_time"] = now
            rec["data_as_of"] = now
            if rec.get("source_trace"):
                rec["source_trace"]["data_as_of"] = now
            updated = True
        records.append(rec)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return updated


def generate_execution_summary() -> dict:
    if not LOG_FILE.exists():
        return {
            "manual_pending_count": 0,
            "manual_filled_count": 0,
            "manual_cancelled_count": 0,
            "skipped_count": 0,
            "total_count": 0,
            "source_trace_enabled": True,
        }

    pending = filled = cancelled = skipped = missing_trace = 0
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        status = rec.get("execution_status", "")
        if status == "manual_pending":
            pending += 1
        elif status == "manual_filled":
            filled += 1
        elif status == "manual_cancelled":
            cancelled += 1
        elif status == "skipped":
            skipped += 1
        if not rec.get("source_trace"):
            missing_trace += 1

    return {
        "manual_pending_count": pending,
        "manual_filled_count": filled,
        "manual_cancelled_count": cancelled,
        "skipped_count": skipped,
        "total_count": pending + filled + cancelled + skipped,
        "missing_source_trace_count": missing_trace,
        "source_trace_enabled": True,
    }


def run_bridge() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    runtime_cycle_id = today
    snapshot_uuid = _load_latest_snapshot_uuid()

    decision_log = _load_decision_log()
    top_picks = _load_top_picks()

    updated_decisions = inject_order_intents_to_decisions(
        decision_log.get("decisions", []),
        top_picks,
    )

    out_path = BASE / "reports" / "paper_decision_log.json"
    decision_log["decisions"] = updated_decisions
    decision_log["execution_bridge_phase"] = "Phase-2.7D"
    decision_log["source_trace_required"] = True
    out_path.write_text(json.dumps(decision_log, ensure_ascii=False, indent=2), encoding="utf-8")

    exec_summary = generate_execution_summary()

    print(f"✅ Eastmoney Paper Bridge: {out_path}")
    print(f"   Decisions: {len(updated_decisions)} | Snapshot: {snapshot_uuid}")
    print(f"   Source Trace: ENABLED | Missing: {exec_summary.get('missing_source_trace_count', 0)}")

    return {
        "decisions": updated_decisions,
        "execution_summary": exec_summary,
        "runtime_cycle_id": runtime_cycle_id,
        "snapshot_uuid": snapshot_uuid,
    }


if __name__ == "__main__":
    run_bridge()
