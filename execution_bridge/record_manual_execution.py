#!/usr/bin/env python3
"""
Phase-2.7B Manual Execution Recorder
MAIN 人工执行东方财富模拟盘后，用此 CLI 回填成交结果。

用法：
python execution_bridge/record_manual_execution.py \
    --symbol 301282 \
    --name 金禄电子 \
    --side BUY \
    --executed-price 30.75 \
    --quantity 100 \
    --status manual_filled

python execution_bridge/record_manual_execution.py \
    --symbol 301282 \
    --name 金禄电子 \
    --side BUY \
    --status manual_cancelled

python execution_bridge/record_manual_execution.py \
    --symbol 301282 \
    --name 金禄电子 \
    --side SELL \
    --executed-price 31.20 \
    --quantity 100 \
    --status manual_filled
"""
import argparse, json, uuid
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
BRIDGE_DIR = Path(__file__).parent.resolve()
LOG_FILE = BRIDGE_DIR / "paper_execution_log.jsonl"


def _load_latest_snapshot():
    today = datetime.now().strftime("%Y-%m-%d")
    path = BASE / "replay_engine" / "snapshots" / f"{today}.json"
    try:
        return json.loads(path.read_text())
    except:
        return {}


def _load_decision_by_symbol(symbol: str):
    """从 paper_decision_log.json 找到对应 symbol 的 decision"""
    path = BASE / "reports" / "paper_decision_log.json"
    try:
        data = json.loads(path.read_text())
        for dec in data.get("decisions", []):
            if dec.get("股票代码") == symbol:
                return dec
    except:
        pass
    return None


def _load_latest_decision():
    """读取最近一条 decision（用于生成 execution_id 关联）"""
    path = BASE / "reports" / "paper_decision_log.json"
    try:
        data = json.loads(path.read_text())
        decisions = data.get("decisions", [])
        return decisions[-1] if decisions else None
    except:
        return None


def record_execution(args):
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    today = datetime.now().strftime("%Y-%m-%d")

    # 读取关联数据
    snapshot = _load_latest_snapshot()
    dec = _load_decision_by_symbol(args.symbol)

    # 构建执行记录
    execution_id = args.execution_id or str(uuid.uuid4())[:8]

    record = {
        "execution_id": execution_id,
        "runtime_cycle_id": today,
        "snapshot_uuid": snapshot.get("snapshot_uuid", ""),
        "symbol": args.symbol,
        "name": args.name,
        "side": args.side.upper(),
        "decision": dec.get("decision", "no_action") if dec else "unknown",
        "order_intent_price": args.executed_price or dec.get("paper_order_intent", {}).get("intent_price", 0.0) if dec else 0.0,
        "executed_price": args.executed_price or 0.0,
        "quantity": args.quantity or 0,
        "amount": round((args.executed_price or 0.0) * (args.quantity or 0), 2),
        "execution_status": args.status,
        "execution_time": now,
        "source": "eastmoney_paper_manual",
        "account_mode": "PAPER_ONLY",
        "risk_validation_passed": dec.get("risk_validation_passed", False) if dec else False,
        "structure_type": dec.get("structure_type", "unknown") if dec else "unknown",
        "structure_confidence": dec.get("structure_confidence", 0.0) if dec else 0.0,
        "agent_trace": [],
    }

    if args.notes:
        record["notes"] = args.notes

    # 追加到 jsonl
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✅ Execution recorded: {execution_id}")
    print(f"   Symbol: {args.symbol} {args.name}")
    print(f"   Side: {args.side} | Status: {args.status}")
    if args.executed_price:
        print(f"   Executed: {args.executed_price} × {args.quantity or 0} = {record['amount']}")
    print(f"   Log: {LOG_FILE}")

    return record


def main():
    parser = argparse.ArgumentParser(description="Phase-2.7B 人工执行记录回填工具")
    parser.add_argument("--symbol", required=True, help="股票代码")
    parser.add_argument("--name", required=True, help="股票名称")
    parser.add_argument("--side", required=True, choices=["BUY", "SELL", "NONE"], help="买卖方向")
    parser.add_argument("--executed-price", type=float, default=0.0, help="成交价格")
    parser.add_argument("--quantity", type=int, default=0, help="成交数量")
    parser.add_argument("--status", required=True,
                        choices=["manual_filled", "manual_cancelled", "skipped"],
                        help="执行状态")
    parser.add_argument("--execution-id", default="", help="指定 execution_id（可选，自动生成）")
    parser.add_argument("--notes", default="", help="备注信息")
    args = parser.parse_args()

    record_execution(args)


if __name__ == "__main__":
    main()
