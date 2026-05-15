#!/usr/bin/env python3
"""
Scan robot-{1..8}/logs/ directories and output robot_log_stats.json
with: last_run_time, runs_7d, error_count, warning_count per robot.
Uses glob, json, and pathlib.
"""

import json
import re
import glob
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Configuration
BASE_DIR = Path.home() / ".hermes"
ROBOT_RANGE = range(1, 9)  # robot-1 through robot-8
OUTPUT_FILE = BASE_DIR / "governance" / "robot_usage_audit" / "robot_log_stats.json"

# Log files to scan per robot
LOG_FILES = ["agent.log", "errors.log", "gateway.log", "gateway.error.log"]

# Timestamp regex: 2026-05-07 16:00:45,559
TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

# Gateway start pattern (indicates a new run)
GATEWAY_START_RE = re.compile(r"Starting Hermes Gateway|Gateway started|Restart=on-failure")

# 7 days ago
SEVEN_DAYS_AGO = datetime.now(timezone.utc) - timedelta(days=7)


def parse_timestamp(ts_str: str) -> datetime:
    """Parse timestamp string to datetime object."""
    # Handle both , and . as microsecond separator
    ts_str = ts_str.replace(",", ".")
    return datetime.fromisoformat(ts_str)


def scan_robot_logs(robot_id: int) -> dict:
    """Scan logs for a single robot and return stats."""
    robot_path = BASE_DIR / f"robot-{robot_id}" / "logs"
    
    if not robot_path.exists():
        return {
            "robot_id": robot_id,
            "last_run_time": None,
            "runs_7d": 0,
            "error_count": 0,
            "warning_count": 0,
            "error": "logs directory not found"
        }
    
    last_run_time = None
    runs_7d = 0
    error_count = 0
    warning_count = 0
    
    # Scan all log files in the logs directory
    log_patterns = [
        robot_path / "*.log",
        robot_path / "**" / "*.log"
    ]
    
    all_log_files = set()
    for pattern in log_patterns:
        all_log_files.update(glob.glob(str(pattern), recursive=True))
    
    # Also check the main log files directly
    for log_file in LOG_FILES:
        full_path = robot_path / log_file
        if full_path.exists():
            all_log_files.add(str(full_path))
    
    for log_file_path in all_log_files:
        path = Path(log_file_path)
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Extract timestamp
                    match = TIMESTAMP_RE.match(line)
                    if match:
                        ts_str = match.group(1)
                        try:
                            ts = parse_timestamp(ts_str)
                            # Ensure timezone-aware
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            
                            # Update last run time
                            if last_run_time is None or ts > last_run_time:
                                last_run_time = ts
                            
                            # Count runs in last 7 days
                            if ts >= SEVEN_DAYS_AGO:
                                if GATEWAY_START_RE.search(line):
                                    runs_7d += 1
                            
                            # Count errors and warnings
                            if " ERROR " in line or " ERROR:" in line:
                                error_count += 1
                            if " WARNING " in line or " WARNING:" in line:
                                warning_count += 1
                        except (ValueError, OSError):
                            continue
        except (PermissionError, FileNotFoundError, IsADirectoryError):
            continue
    
    # Convert last_run_time to ISO string
    last_run_str = last_run_time.isoformat() if last_run_time else None
    
    # Deduplicate runs_7d - count unique run sessions by looking for gateway start events
    # A more accurate approach: count distinct startup sequences
    # For now, we count each "Starting Hermes Gateway" as a run
    # If runs_7d seems too high, it's because multiple log lines might indicate the same run
    
    return {
        "robot_id": robot_id,
        "last_run_time": last_run_str,
        "runs_7d": runs_7d,
        "error_count": error_count,
        "warning_count": warning_count
    }


def main():
    """Main function to scan all robots and output JSON."""
    stats = {}
    
    for robot_id in ROBOT_RANGE:
        robot_stats = scan_robot_logs(robot_id)
        stats[f"robot-{robot_id}"] = robot_stats
    
    # Write output JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"Wrote stats to {OUTPUT_FILE}")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
