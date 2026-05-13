#!/usr/bin/env python3
"""
Runtime Event Retention
保留14天 jsonl，超过14天的 gzip 归档到 runtime_events/archive/
"""
import gzip
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = BASE_DIR / "runtime_events"
ARCHIVE_DIR = EVENTS_DIR / "archive"
RETAIN_DAYS = 14


def cleanup_runtime_events(retain_days: int = RETAIN_DAYS) -> dict:
    """归档超过 retain_days 的 jsonl 到 archive/*.jsonl.gz"""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=retain_days)).strftime("%Y-%m-%d")
    archived = []
    skipped = []

    for jsonl_path in sorted(EVENTS_DIR.glob("*.jsonl")):
        # 读取最新事件时间戳
        latest_ts = ""
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        evt = json.loads(line)
                        latest_ts = evt.get("timestamp", "")
                    except json.JSONDecodeError:
                        pass

        if not latest_ts:
            continue

        # 比较日期
        event_date = latest_ts[:10]  # "YYYY-MM-DD"
        if event_date < cutoff:
            # gzip 归档
            gz_path = ARCHIVE_DIR / f"{jsonl_path.name}.gz"
            with open(jsonl_path, "rb") as f_in:
                with gzip.open(gz_path, "ab") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            jsonl_path.unlink()
            archived.append(jsonl_path.name)
        else:
            skipped.append(jsonl_path.name)

    result = {
        "retain_days": retain_days,
        "cutoff_date": cutoff,
        "archived": archived,
        "archived_count": len(archived),
        "skipped": skipped,
        "skipped_count": len(skipped),
    }

    return result


if __name__ == "__main__":
    result = cleanup_runtime_events()
    print(f"Runtime Event Retention (保留{result['retain_days']}天)")
    print(f"  截止日期: {result['cutoff_date']}")
    print(f"  归档: {result['archived_count']} 个文件 → runtime_events/archive/")
    if result['archived']:
        for a in result['archived']:
            print(f"    📦 {a} → {a}.gz")
    print(f"  保留: {result['skipped_count']} 个文件")
