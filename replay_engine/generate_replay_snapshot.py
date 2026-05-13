#!/usr/bin/env python3
"""
Phase-2.6E Replay Snapshot Persistence + Phase-2.7A structure fields
在每日 pipeline 运行后生成当天 replay snapshot，填补治理审计链路断点。
Phase-2.7A: decisions 数组包含 structure 字段。
"""
import json, os, uuid
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()
SELF_DIR = Path(__file__).parent.resolve()

def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except:
        return default or {}

def generate_replay_snapshot():
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    snap_dir = SELF_DIR / "snapshots"
    snap_dir.mkdir(exist_ok=True)

    # 读取各数据源
    gov_snap = load_json(
        BASE / "governance" / "snapshots" / f"{today}.json"
    )
    top_picks = load_json(BASE / "reports" / "top_picks.json", {})
    decision_log = load_json(BASE / "reports" / "paper_decision_log.json", {})
    hc_hist = load_json(
        BASE / "system_health" / "history" / f"{today}.json"
    )

    validation_results = decision_log.get("validation_results", [])
    paper_decisions = decision_log.get("decisions", [])
    paper_skip_count = sum(
        1 for d in paper_decisions
        if d.get("decision") in ("paper_skip", "no_action")
    )
    invalid_count = sum(
        1 for r in validation_results
        if r.get("is_valid") is False
    )

    # Phase-2.7A: 构建 decisions 数组（含 structure 字段）
    decisions_out = []
    for d in paper_decisions:
        decisions_out.append({
            "股票代码": d.get("股票代码", ""),
            "股票名称": d.get("股票名称", ""),
            "decision": d.get("decision", "no_action"),
            "action": d.get("action", ""),
            "reason": d.get("reason", ""),
            "skip_reason": d.get("skip_reason", ""),
            "quantity": d.get("quantity", 0),
            "price": d.get("price", 0.0),
            # Phase-2.7A: 市场结构字段
            "structure_type": d.get("structure_type", "unknown"),
            "structure_confidence": d.get("structure_confidence", 0.0),
            "structure_source": d.get("structure_source", "unknown"),
            "structure_version": d.get("structure_version", "2.7a"),
            "swing_low": d.get("swing_low", 0.0),
            "swing_high": d.get("swing_high", 0.0),
            "support_price": d.get("support_price", 0.0),
            "pressure_price": d.get("pressure_price", 0.0),
        })

    # Phase-2.7A: Market Structure 统计
    invalid_struct_count = sum(
        1 for d in decisions_out
        if d.get("structure_type") == "invalid"
    )
    fallback_struct_count = sum(
        1 for d in decisions_out
        if d.get("structure_type") == "fallback_ma20"
    )

    snapshot = {
        "snapshot_date": today,
        "generated_at": now,
        "phase": "Phase-2.7A",
        "soul_mode": "OBSERVE_ONLY",
        "account_mode": "PAPER_ONLY",
        "observation_freeze": True,
        "risk_validation_enabled": True,
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
            "valid_rate": round(
                (len(decisions_out) - invalid_struct_count) / len(decisions_out), 3
            ) if decisions_out else 0,
        },
        "top_picks_count": len(top_picks.get("top_picks", [])),
        "paper_decision_count": len(paper_decisions),
        "paper_skip_count": paper_skip_count,
        "invalid_price_structure_count": invalid_count,
        "decisions": decisions_out,
        "runtime_cycle_id": today,
        "snapshot_uuid": str(uuid.uuid4())[:8],
    }

    out_path = snap_dir / f"{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    print(f"✅ Replay Snapshot: {out_path}")
    print(f"   Date: {today} | UUID: {snapshot['snapshot_uuid']}")
    print(f"   TopPicks: {snapshot['top_picks_count']} | Decisions: {snapshot['paper_decision_count']}")
    print(f"   Invalid price structure: {invalid_count} | Paper skip: {paper_skip_count}")
    print(f"   Phase: {snapshot['phase']}")
    return snapshot

if __name__ == "__main__":
    generate_replay_snapshot()
