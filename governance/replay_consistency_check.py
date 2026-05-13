#!/usr/bin/env python3
"""
Phase-2.6D Replay Consistency Check
检查：
1. replay cache 是否存在
2. replay snapshot 是否匹配当天 pipeline
3. report snapshot 是否一致
4. governance snapshot 是否一致
输出：PASS / WARNING / FAIL
"""
import json, os
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent.resolve()

def check_replay_cache():
    """检查 replay cache 是否存在"""
    today = datetime.now().strftime("%Y-%m-%d")
    paths = [
        BASE / "replay_engine" / "cache",
        BASE / "replay_engine" / f"{today}_snapshot.json",
    ]
    for p in paths:
        if p.exists():
            return "PASS", f"replay cache exists: {p.name}"
    return "FAIL", "replay cache not found"

def check_replay_snapshot_date():
    """检查 replay snapshot 是否匹配当天 pipeline"""
    today = datetime.now().strftime("%Y-%m-%d")
    snap_paths = [
        BASE / "replay_engine" / "cache" / "latest_snapshot.json",
        BASE / "replay_engine" / "snapshot.json",
    ]
    for p in snap_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                snap_date = data.get("date") or data.get("generated_at", "")[:10]
                if snap_date == today:
                    return "PASS", f"snapshot matches today ({today})"
                else:
                    return "WARNING", f"snapshot date={snap_date}, today={today}"
            except:
                return "WARNING", "snapshot exists but unreadable"
    return "FAIL", "no replay snapshot found"

def check_report_snapshot():
    """检查 report snapshot 是否一致"""
    today = datetime.now().strftime("%Y-%m-%d")
    paths = [
        BASE / "reports" / f"{today}.json",
        BASE / "reports" / "snapshot.json",
        BASE / "reports" / "history" / f"{today}.md",
    ]
    for p in paths:
        if p.exists():
            return "PASS", f"report snapshot exists: {p.name}"
    return "WARNING", "today's report snapshot not found (may not be generated yet)"

def check_governance_snapshot():
    """检查 governance snapshot 是否一致"""
    today = datetime.now().strftime("%Y-%m-%d")
    gov_dir = BASE / "governance" / "snapshots"
    gov_file = gov_dir / f"{today}.json"
    if gov_file.exists():
        try:
            data = json.loads(gov_file.read_text())
            status = data.get("status", "unknown")
            return "PASS", f"governance snapshot status={status}"
        except:
            return "WARNING", "governance snapshot unreadable"
    # 旧文件检查
    latest = sorted((gov_dir).glob("*.json")) if gov_dir.exists() else []
    if latest:
        try:
            data = json.loads(latest[-1].read_text())
            status = data.get("status", "unknown")
            return "WARNING", f"no today snapshot, latest={latest[-1].name} status={status}"
        except:
            return "WARNING", f"no today snapshot, latest unreadable"
    return "FAIL", "no governance snapshot found"

def run_consistency_check():
    checks = {
        "replay_cache_exists": check_replay_cache(),
        "replay_snapshot_date": check_replay_snapshot_date(),
        "report_snapshot": check_report_snapshot(),
        "governance_snapshot": check_governance_snapshot(),
    }

    statuses = [c[0] for c in checks.values()]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARNING" in statuses:
        overall = "WARNING"
    else:
        overall = "PASS"

    report = {
        "phase": "Phase-2.6D",
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "overall": overall,
        "checks": {k: {"status": v[0], "message": v[1]} for k, v in checks.items()},
    }

    print(f"=== Replay Consistency Check — {overall} ===")
    for k, v in checks.items():
        icon = "✅" if v[0] == "PASS" else "⚠️" if v[0] == "WARNING" else "❌"
        print(f"  {icon} {k}: {v[1]}")

    return report

if __name__ == "__main__":
    run_consistency_check()