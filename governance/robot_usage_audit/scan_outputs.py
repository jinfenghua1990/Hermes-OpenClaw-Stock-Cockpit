#!/usr/bin/env python3
"""
Scan robot output directories and generate robot_output_stats.json
Scans .hermes-robot-* directories for output/log files and generates statistics
"""

import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

WORKSPACE = Path("/Users/gino")
ROBOT_PATTERN = ".hermes-robot-"
OUTPUT_FILE = "robot_output_stats.json"


def scan_directory(path: Path) -> dict:
    """Scan a directory and return stats"""
    stats = {
        "total_files": 0,
        "total_size": 0,
        "file_types": defaultdict(int),
        "files": []
    }
    
    if not path.exists():
        return stats
    
    try:
        for item in path.rglob("*"):
            if item.is_file():
                stats["total_files"] += 1
                try:
                    size = item.stat().st_size
                    stats["total_size"] += size
                    ext = item.suffix.lower() or "no_extension"
                    stats["file_types"][ext] += 1
                    stats["files"].append({
                        "name": item.name,
                        "path": str(item.relative_to(path.parent)),
                        "size": size,
                        "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                    })
                except Exception:
                    pass
    except Exception:
        pass
    
    return stats


def scan_robot(robot_path: Path) -> dict:
    """Scan a single robot directory"""
    robot_name = robot_path.name
    stats = {
        "robot_name": robot_name,
        "robot_path": str(robot_path),
        "scanned_at": datetime.now().isoformat(),
        "logs": {},
        "sessions": {},
        "cache": {},
        "total_output_size": 0,
        "total_output_files": 0
    }
    
    # Key output directories to scan
    output_dirs = {
        "logs": robot_path / "logs",
        "sessions": robot_path / "sessions",
        "cache": robot_path / "cache",
        "memories": robot_path / "memories",
        "feishu_card": robot_path / "feishu_card",
        "cron": robot_path / "cron"
    }
    
    for dir_name, dir_path in output_dirs.items():
        if dir_path.exists():
            dir_stats = scan_directory(dir_path)
            if dir_stats["total_files"] > 0:
                stats[dir_name] = {
                    "path": str(dir_path),
                    "file_count": dir_stats["total_files"],
                    "total_size": dir_stats["total_size"],
                    "file_types": dict(dir_stats["file_types"])
                }
                stats["total_output_files"] += dir_stats["total_files"]
                stats["total_output_size"] += dir_stats["total_size"]
    
    # Log file specific analysis
    logs_path = robot_path / "logs"
    if logs_path.exists():
        log_types = ["agent.log", "gateway.log", "errors.log", "nohup.log", "restart.log"]
        for log_type in log_types:
            log_file = logs_path / log_type
            if log_file.exists():
                try:
                    size = log_file.stat().st_size
                    lines = 0
                    with open(log_file, 'r', errors='ignore') as f:
                        lines = sum(1 for _ in f)
                    stats["logs"][log_type] = {
                        "size": size,
                        "lines": lines
                    }
                except Exception:
                    pass
    
    return stats


def main():
    """Main function to scan all robot directories"""
    results = {
        "scan_time": datetime.now().isoformat(),
        "workspace": str(WORKSPACE),
        "robots": []
    }
    
    # Find all robot directories
    try:
        for item in WORKSPACE.iterdir():
            if item.is_dir() and ROBOT_PATTERN in item.name:
                print(f"Scanning {item.name}...")
                robot_stats = scan_robot(item)
                results["robots"].append(robot_stats)
    except Exception as e:
        results["error"] = str(e)
    
    # Summary statistics
    results["summary"] = {
        "total_robots": len(results["robots"]),
        "total_output_files": sum(r["total_output_files"] for r in results["robots"]),
        "total_output_size": sum(r["total_output_size"] for r in results["robots"])
    }
    
    # Write output
    output_path = WORKSPACE / OUTPUT_FILE
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nScan complete. Results written to {output_path}")
    print(f"Scanned {results['summary']['total_robots']} robots")
    print(f"Total output files: {results['summary']['total_output_files']}")
    print(f"Total output size: {results['summary']['total_output_size']} bytes")


if __name__ == "__main__":
    main()