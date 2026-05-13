#!/usr/bin/env python3
"""
Phase-2.7B Eastmoney Paper Execution Bridge
职责：
1. 从 paper_decision_engine 接收 paper_order_intent
2. 管理 execution_bridge/paper_execution_log.jsonl
3. 提供人工回填成交结果的接口
4. 不做自动下单，只做执行记录桥
"""
import json, os, uuid
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
BRIDGE_DIR = Path(__file__).parent.resolve()
LOG_FILE = BRIDGE_DIR / "paper_execution_log.jsonl"


def _load_decision_log():
    """读取 paper_decision_log.json"""
    path = BASE / "reports" / "paper_decision_log.json"
    try:
        return json.loads(path.read_text())
    except:
        return {"decisions": []}


def _load_top_picks():
    """读取 top_picks.json"""
    path = BASE / "reports" / "top_picks.json"
    try:
        return json.loads(path.read_text())
    except:
        return {"top_picks": []}


def _load_latest_snapshot_uuid():
    """读取当日 replay snapshot UUID"""
    today = datetime.now().strftime("%Y-%m-%d")
    path = BASE / "replay_engine" / "snapshots" / f"{today}.json"
    try:
        data = json.loads(path.read_text())
        return data.get("snapshot_uuid", "")
    except:
        return ""


def _load_latest_replay_snapshot():
    """读取当日 replay snapshot"""
    today = datetime.now().strftime("%Y-%m-%d")
    path = BASE / "replay_engine" / "snapshots" / f"{today}.json"
    try:
        return json.loads(path.read_text())
    except:
        return None


def build_paper_order_intent(symbol: str, name: str, decision: str,
                              price: float, quantity: int,
                              risk_validation_passed: bool,
                              structure_type: str, structure_confidence: float,
                              max_amount: float = 0.0,
                              side: str = "NONE") -> dict:
    """
    Phase-2.7B: 构建 paper_order_intent。
    如果 decision = paper_skip → side = NONE，execution_status = skipped。
    否则生成待人工确认的买入/卖出意图。
    """
    if decision == "paper_skip":
        return {
            "symbol": symbol,
            "name": name,
            "side": "NONE",
            "intent_price": price,
            "suggested_quantity": 0,
            "max_amount": 0.0,
            "execution_mode": "MANUAL_CONFIRM_EXECUTION",
            "execution_target": "eastmoney_paper",
            "execution_status": "skipped",
            "risk_validation_passed": risk_validation_passed,
            "structure_type": structure_type,
            "structure_confidence": structure_confidence,
            "order_intent_price": price,
            "suggested_quantity_int": 0,
        }

    # BUY / SELL / HOLD
    return {
        "symbol": symbol,
        "name": name,
        "side": side,
        "intent_price": price,
        "suggested_quantity": quantity,
        "max_amount": max_amount,
        "execution_mode": "MANUAL_CONFIRM_EXECUTION",
        "execution_target": "eastmoney_paper",
        "execution_status": "manual_pending",
        "risk_validation_passed": risk_validation_passed,
        "structure_type": structure_type,
        "structure_confidence": structure_confidence,
        "order_intent_price": price,
        "suggested_quantity_int": quantity,
    }


def inject_order_intents_to_decisions(decisions: list, top_picks: list) -> list:
    """
    Phase-2.7B: 遍历 paper_decisions，为每只股票注入 paper_order_intent。
    从 top_picks 找到对应股票的行情数据（现价、涨跌幅）。
    """
    # 构建股票代码→行情映射
    price_map = {}
    for pick in top_picks.get("top_picks", []):
        sym = pick.get("股票代码", "")
        price_map[sym] = {
            "current_price": pick.get("最新价", 0.0),
            "change_pct": pick.get("涨跌幅", 0.0),
            "ma20": pick.get("MA20", 0.0),
        }

    updated = []
    for dec in decisions:
        sym = dec.get("股票代码", "")
        name = dec.get("股票名称", "")
        decision = dec.get("decision", "no_action")
        price_info = price_map.get(sym, {})
        current_price = price_info.get("current_price", 0.0)

        # 决定 side
        if decision in ("paper_buy",):
            side = "BUY"
            intent_price = current_price
            quantity = dec.get("quantity", 0)
            max_amount = dec.get("max_amount", 0.0)
        elif decision in ("paper_sell",):
            side = "SELL"
            intent_price = current_price
            quantity = dec.get("quantity", 0)
            max_amount = 0.0
        else:
            side = "NONE"
            intent_price = current_price
            quantity = 0
            max_amount = 0.0

        order_intent = build_paper_order_intent(
            symbol=sym,
            name=name,
            decision=decision,
            price=intent_price,
            quantity=quantity,
            risk_validation_passed=dec.get("risk_validation_passed", False),
            structure_type=dec.get("structure_type", "unknown"),
            structure_confidence=dec.get("structure_confidence", 0.0),
            max_amount=max_amount,
            side=side,
        )

        # 合并到 decision
        dec_copy = dict(dec)
        dec_copy["paper_order_intent"] = order_intent
        dec_copy["execution_status"] = order_intent.get("execution_status", "unknown")
        updated.append(dec_copy)

    return updated


def record_execution(execution_record: dict) -> str:
    """
    Phase-2.7B: 将一条执行记录追加到 paper_execution_log.jsonl。
    返回 execution_id。
    """
    execution_id = execution_record.get("execution_id") or str(uuid.uuid4())[:8]
    execution_record["execution_id"] = execution_id

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(execution_record, ensure_ascii=False) + "\n")

    return execution_id


def update_decision_execution_status(symbol: str, execution_id: str,
                                      execution_status: str,
                                      executed_price: float = 0.0,
                                      quantity: int = 0,
                                      execution_time: str = "") -> bool:
    """
    Phase-2.7B: 根据 execution_status 更新 paper_execution_log.jsonl 中对应记录的 execution_status。
    状态流转：manual_pending → manual_filled / manual_cancelled / skipped
    """
    if not LOG_FILE.exists():
        return False

    records = []
    updated = False
    now = execution_time or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
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
                updated = True
            records.append(rec)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return updated


def generate_execution_summary() -> dict:
    """
    Phase-2.7B: 从 paper_execution_log.jsonl 统计执行汇总。
    """
    if not LOG_FILE.exists():
        return {
            "manual_pending_count": 0,
            "manual_filled_count": 0,
            "manual_cancelled_count": 0,
            "skipped_count": 0,
            "total_count": 0,
        }

    pending = filled = cancelled = skipped = 0
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
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

    return {
        "manual_pending_count": pending,
        "manual_filled_count": filled,
        "manual_cancelled_count": cancelled,
        "skipped_count": skipped,
        "total_count": pending + filled + cancelled + skipped,
    }


def run_bridge() -> dict:
    """
    Phase-2.7B 主入口：读取 paper_decision_log，注入 paper_order_intent，写回文件。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    runtime_cycle_id = today
    snapshot_uuid = _load_latest_snapshot_uuid()

    # 读取数据
    decision_log = _load_decision_log()
    top_picks = _load_top_picks()

    # 注入 order_intent
    updated_decisions = inject_order_intents_to_decisions(
        decision_log.get("decisions", []),
        top_picks
    )

    # 写回 paper_decision_log.json
    out_path = BASE / "reports" / "paper_decision_log.json"
    decision_log["decisions"] = updated_decisions
    decision_log["execution_bridge_phase"] = "Phase-2.7B"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(decision_log, f, ensure_ascii=False, indent=2)

    # 生成 execution_summary
    exec_summary = generate_execution_summary()

    print(f"✅ Eastmoney Paper Bridge: {out_path}")
    print(f"   Decisions: {len(updated_decisions)} | Snapshot: {snapshot_uuid}")
    print(f"   Manual Pending: {exec_summary['manual_pending_count']} | Filled: {exec_summary['manual_filled_count']} | Cancelled: {exec_summary['manual_cancelled_count']} | Skipped: {exec_summary['skipped_count']}")

    return {
        "decisions": updated_decisions,
        "execution_summary": exec_summary,
        "runtime_cycle_id": runtime_cycle_id,
        "snapshot_uuid": snapshot_uuid,
    }


if __name__ == "__main__":
    run_bridge()
