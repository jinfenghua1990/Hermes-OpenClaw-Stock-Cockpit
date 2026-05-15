#!/usr/bin/env python3
"""
Scan cron jobs and scripts to find robot invocations.
Outputs robot_dependency_graph.json with dependency relationships.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path("/Users/gino")
PROJECT_DIR = BASE_DIR / "project_ai_trading"
CRON_SCRIPTS_DIR = PROJECT_DIR / "cron" / "scripts"
CRONTAB_FILE = BASE_DIR / ".crontab"
HERMES_ROBOTS_DIR = BASE_DIR / ".hermes-robot-"
OUTPUT_FILE = BASE_DIR / "robot_dependency_graph.json"

# Known robot identifiers
ROBOT_PATTERNS = [
    r"robot[_-]?(\d+)",
    r"robot[-\s]?(\d+)",
    r"OpenClaw",
    r"hermes.*robot",
    r"feature_engine",
    r"main_aggregate",
    r"position_adapter",
    r"collect_reports",
    r"kline_update",
    r"audit_engine",
]

LAYER_PATTERNS = [
    ("execution_layer", ["openclaw_fetch", "feature_engine", "robot4_match", "kline_update"]),
    ("governance_layer", ["robot5_risk", "audit_engine"]),
    ("reporting_layer", ["main_aggregate", "report_pipeline", "notification_router"]),
]


def normalize_robot_name(name: str) -> str:
    """Normalize robot/script names for consistent graph nodes."""
    name = name.strip().lower()
    # Map known variants to canonical names
    mapping = {
        "openclaw_fetch": "OpenClaw",
        "feature_engine": "robot-3 FeatureEngine",
        "robot4_match": "robot-4 PatternMatch",
        "robot4_pattern_match": "robot-4 PatternMatch",
        "kline_update": "robot-4 PatternMatch",
        "robot5_risk": "robot-5 RiskAudit",
        "audit_engine": "robot-5 RiskAudit",
        "main_aggregate": "Main Aggregate",
        "report_pipeline": "Main Aggregate",
        "notification_router": "NotificationRouter",
        "position_adapter": "PositionAdapter",
        "collect_reports": "ReportCollector",
        "openclaw": "OpenClaw",
    }
    return mapping.get(name, name.title())


def extract_cron_jobs(crontab_path: Path) -> list[dict]:
    """Extract robot invocations from crontab."""
    jobs = []
    if not crontab_path.exists():
        return jobs

    content = crontab_path.read_text()
    for line_num, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Parse cron schedule + command
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue

        schedule, command = parts[0:5], parts[5]
        schedule_str = " ".join(schedule)

        # Check for robot references in command
        robots_found = []
        for pattern in ROBOT_PATTERNS:
            for match in re.finditer(pattern, command, re.IGNORECASE):
                robots_found.append(normalize_robot_name(match.group(0)))

        if robots_found or any(x in command.lower() for x in ["robot", "openclaw", "aggregate", "feature", "match", "risk"]):
            jobs.append({
                "source": "crontab",
                "line": line_num,
                "schedule": schedule_str,
                "command": command,
                "robots": list(set(robots_found)) if robots_found else [],
                "raw_script": os.path.basename(command.split()[0]) if command else "",
            })
    return jobs


def extract_script_dependencies(script_path: Path) -> dict:
    """Extract robot dependencies from a script file."""
    if not script_path.exists():
        return {}

    content = script_path.read_text()
    dependencies = []
    invocations = []
    robots = []
    description = ""

    # Extract comment/description from top
    for line in content.splitlines()[:10]:
        if line.strip().startswith("#"):
            desc_match = re.search(r"Phase-\S+ cron #?\d*:?\s*(.+)", line)
            if desc_match:
                description = desc_match.group(1).strip()
                break

    # Find script invocations (other scripts called via bash/source)
    for line in content.splitlines():
        line_stripped = line.strip()

        # Direct script invocations
        for pattern in [
            r'/bin/bash\s+"([^"]+\.sh)"',
            r'/bin/bash\s+(\S+\.sh)',
            r'source\s+"([^"]+\.sh)"',
            r'source\s+(\S+\.sh)',
            r'python3?\s+"([^"]+\.py)"',
            r'python3?\s+(\S+\.py)',
        ]:
            for match in re.finditer(pattern, line_stripped):
                script_name = os.path.basename(match.group(1))
                if script_name and script_name != os.path.basename(script_path.name):
                    invocations.append(script_name)

        # Find robot references in embedded Python
        if "robot" in line_stripped.lower():
            for pattern in ROBOT_PATTERNS:
                for match in re.finditer(pattern, line_stripped, re.IGNORECASE):
                    robots.append(normalize_robot_name(match.group(0)))

    # Determine layer
    script_name_lower = script_path.stem.lower()
    layer = "unknown"
    for layer_name, keywords in LAYER_PATTERNS:
        if any(kw in script_name_lower for kw in keywords):
            layer = layer_name
            break

    # Determine robot identity
    robot_id = None
    if "robot4" in script_name_lower or "match" in script_name_lower:
        robot_id = "robot-4 PatternMatch"
    elif "robot5" in script_name_lower or "risk" in script_name_lower:
        robot_id = "robot-5 RiskAudit"
    elif "feature_engine" in script_name_lower:
        robot_id = "robot-3 FeatureEngine"
    elif "openclaw_fetch" in script_name_lower:
        robot_id = "OpenClaw"
    elif "main_aggregate" in script_name_lower:
        robot_id = "Main Aggregate"
    elif "scheduler" in script_name_lower:
        robot_id = "Scheduler"

    # Pre/Post conditions from comments
    pre_requisites = []
    post_conditions = []
    for line in content.splitlines():
        if line.strip().startswith("# 前置") or line.strip().startswith("# Pre"):
            deps = re.findall(r"[\w-]+\.sh", line)
            pre_requisites.extend([os.path.basename(d) for d in deps])
        if line.strip().startswith("# 后置") or line.strip().startswith("# Post"):
            deps = re.findall(r"[\w-]+\.sh", line)
            post_conditions.extend([os.path.basename(d) for d in deps])

    return {
        "script_name": script_path.name,
        "robot_id": robot_id,
        "layer": layer,
        "description": description,
        "invocations": list(set(invocations)),
        "robots_mentioned": list(set(robots)),
        "pre_requisites": list(set(pre_requisites)),
        "post_conditions": list(set(post_conditions)),
    }


def extract_hermes_cron_jobs(hermes_base: Path) -> list[dict]:
    """Extract jobs from hermes robot cron jobs.json files."""
    jobs = []

    for i in range(1, 20):
        robot_dir = hermes_base.parent / f".hermes-robot-{i}"
        cron_dir = robot_dir / "cron"
        jobs_file = cron_dir / "jobs.json"

        if not jobs_file.exists():
            continue

        try:
            data = json.loads(jobs_file.read_text())
            for job in data.get("jobs", []):
                jobs.append({
                    "robot_id": f"robot-{i}",
                    "job_id": job.get("id", ""),
                    "job_name": job.get("name", ""),
                    "script": job.get("script", ""),
                    "prompt": job.get("prompt", "")[:200] if job.get("prompt") else "",
                    "schedule": job.get("schedule", {}).get("display", ""),
                    "schedule_kind": job.get("schedule", {}).get("kind", ""),
                    "enabled": job.get("enabled", False),
                    "state": job.get("state", ""),
                    "source": f"hermes-robot-{i}",
                })
        except (json.JSONDecodeError, OSError):
            continue

    return jobs


def build_dependency_graph(
    crontab_jobs: list,
    script_deps: list,
    hermes_jobs: list,
) -> dict:
    """Build a dependency graph from scanned data."""

    # Build nodes
    nodes = {}
    for script in script_deps:
        robot_id = script["robot_id"]
        if robot_id and robot_id not in nodes:
            nodes[robot_id] = {
                "id": robot_id,
                "type": "robot",
                "layer": script["layer"],
                "description": script["description"],
                "scripts": [],
                "crontab_entries": [],
                "hermes_jobs": [],
            }
        if robot_id and script["script_name"]:
            nodes[robot_id]["scripts"].append(script["script_name"])

    # Add node for Scheduler (orchestrator)
    if "Scheduler" not in nodes:
        nodes["Scheduler"] = {
            "id": "Scheduler",
            "type": "orchestrator",
            "layer": "execution_layer",
            "description": "Phase-1.6 launchd-based scheduler",
            "scripts": ["scheduler.sh"],
            "crontab_entries": [],
            "hermes_jobs": [],
        }
        nodes["Scheduler"]["scripts"] = ["scheduler.sh"]

    # Add node for OpenClaw
    if "OpenClaw" not in nodes:
        nodes["OpenClaw"] = {
            "id": "OpenClaw",
            "type": "data_source",
            "layer": "execution_layer",
            "description": "Market data fetcher",
            "scripts": ["openclaw_fetch.sh"],
            "crontab_entries": [],
            "hermes_jobs": [],
        }

    # Add node for Main Aggregate
    if "Main Aggregate" not in nodes:
        nodes["Main Aggregate"] = {
            "id": "Main Aggregate",
            "type": "reporting",
            "layer": "reporting_layer",
            "description": "Report aggregation and generation",
            "scripts": ["main_aggregate.sh"],
            "crontab_entries": [],
            "hermes_jobs": [],
        }

    # Add cron entries to nodes
    for cj in crontab_jobs:
        raw = cj.get("raw_script", "")
        if not raw:
            continue
        # Map script to robot
        robot_map = {
            "openclaw_fetch.sh": "OpenClaw",
            "feature_engine.sh": "robot-3 FeatureEngine",
            "robot4_match.sh": "robot-4 PatternMatch",
            "robot5_risk.sh": "robot-5 RiskAudit",
            "main_aggregate.sh": "Main Aggregate",
            "scheduler.sh": "Scheduler",
            "notification_router.py": "NotificationRouter",
            "position_adapter.py": "PositionAdapter",
        }
        robot = robot_map.get(raw)
        if robot and robot in nodes:
            nodes[robot]["crontab_entries"].append({
                "schedule": cj["schedule"],
                "line": cj["line"],
            })

    # Add hermes jobs
    for hj in hermes_jobs:
        robot_id = hj["robot_id"]
        if robot_id not in nodes:
            nodes[robot_id] = {
                "id": robot_id,
                "type": "hermes_robot",
                "layer": "unknown",
                "description": f"Hermes {robot_id}",
                "scripts": [],
                "crontab_entries": [],
                "hermes_jobs": [],
            }
        nodes[robot_id]["hermes_jobs"].append({
            "job_id": hj["job_id"],
            "job_name": hj["job_name"],
            "schedule": hj["schedule"],
            "enabled": hj["enabled"],
            "state": hj["state"],
        })

    # Build edges (dependencies based on workflow)
    edges = []
    # Pre-defined workflow edges based on Phase-1.6 design
    workflow_chain = [
        ("Scheduler", "OpenClaw", "triggers at 08:20/10:25/13:25/15:20"),
        ("Scheduler", "robot-3 FeatureEngine", "triggers at 08:25/10:28/13:28/15:25"),
        ("Scheduler", "robot-4 PatternMatch", "triggers at 15:28"),
        ("Scheduler", "robot-5 RiskAudit", "triggers at 15:29"),
        ("Scheduler", "Main Aggregate", "triggers at 08:30/10:30/13:30/15:30"),
        ("OpenClaw", "robot-3 FeatureEngine", "data output → feature input"),
        ("robot-3 FeatureEngine", "robot-4 PatternMatch", "daily_review path: features → strategy"),
        ("robot-3 FeatureEngine", "Main Aggregate", "pre_market/intraday paths"),
        ("robot-4 PatternMatch", "robot-5 RiskAudit", "strategy → risk check"),
        ("robot-5 RiskAudit", "Main Aggregate", "risk results → daily review"),
    ]

    for src, tgt, reason in workflow_chain:
        if src in nodes and tgt in nodes:
            edges.append({
                "source": src,
                "target": tgt,
                "type": "workflow_dependency",
                "reason": reason,
            })

    # Add script-to-script invocation edges
    for script in script_deps:
        src_robot = script["robot_id"]
        if not src_robot or src_robot == "Scheduler":
            continue
        for invoked_script in script["invocations"]:
            # Map invoked script to robot
            robot_map = {
                "openclaw_fetch.sh": "OpenClaw",
                "feature_engine.sh": "robot-3 FeatureEngine",
                "robot4_match.sh": "robot-4 PatternMatch",
                "robot5_risk.sh": "robot-5 RiskAudit",
                "main_aggregate.sh": "Main Aggregate",
                "scheduler.sh": "Scheduler",
                "robot4_match.sh": "robot-4 PatternMatch",
                "robot5_risk.sh": "robot-5 RiskAudit",
            }
            tgt_robot = robot_map.get(invoked_script)
            if tgt_robot and tgt_robot != src_robot:
                # Check if this edge already exists
                existing = {(e["source"], e["target"]) for e in edges}
                if (src_robot, tgt_robot) not in existing:
                    edges.append({
                        "source": src_robot,
                        "target": tgt_robot,
                        "type": "script_invocation",
                        "via_script": invoked_script,
                    })

    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "scan_base": str(BASE_DIR),
            "total_crontab_entries": len(crontab_jobs),
            "total_scripts_scanned": len(script_deps),
            "total_hermes_jobs": len(hermes_jobs),
        },
        "workflow_summary": {
            "description": "Phase-1.6 有限自动化 - 机器人依赖链",
            "daily_pipeline": "OpenClaw → robot-3 → (robot-4 → robot-5) → Main Aggregate",
            "execution_times": {
                "pre_market": "08:20-08:30",
                "intraday_am": "10:25-10:30",
                "intraday_pm": "13:25-13:30",
                "daily_review": "15:20-15:30",
            },
        },
        "nodes": nodes,
        "edges": edges,
        "crontab_raw_entries": crontab_jobs,
        "script_details": script_deps,
        "hermes_cron_jobs": hermes_jobs,
    }


def main():
    print("Scanning for robot dependencies...")

    # 1. Scan crontab
    print(f"  Scanning crontab: {CRONTAB_FILE}")
    crontab_jobs = extract_cron_jobs(CRONTAB_FILE)
    print(f"    Found {len(crontab_jobs)} relevant cron entries")

    # 2. Scan scripts directory
    print(f"  Scanning scripts: {CRON_SCRIPTS_DIR}")
    script_deps = []
    if CRON_SCRIPTS_DIR.exists():
        for script_path in sorted(CRON_SCRIPTS_DIR.glob("*.sh")):
            deps = extract_script_dependencies(script_path)
            if deps:
                deps["source_file"] = str(script_path)
                script_deps.append(deps)
        for script_path in sorted(CRON_SCRIPTS_DIR.glob("*.py")):
            deps = extract_script_dependencies(script_path)
            if deps:
                deps["source_file"] = str(script_path)
                script_deps.append(deps)
    print(f"    Found {len(script_deps)} scripts with dependencies")

    # 3. Scan hermes robot cron jobs
    print("  Scanning hermes robot cron jobs...")
    hermes_jobs = extract_hermes_cron_jobs(HERMES_ROBOTS_DIR)
    print(f"    Found {len(hermes_jobs)} hermes cron jobs")

    # 4. Build graph
    print("  Building dependency graph...")
    graph = build_dependency_graph(crontab_jobs, script_deps, hermes_jobs)

    # 5. Write output
    output_path = OUTPUT_FILE
    output_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2))
    print(f"\n✅ Output written to: {output_path}")

    # Summary
    print(f"\n--- Summary ---")
    print(f"Nodes (robots/scripts): {len(graph['nodes'])}")
    print(f"Edges (dependencies): {len(graph['edges'])}")
    print(f"Workflow chain:")
    for edge in graph["edges"]:
        if edge["type"] == "workflow_dependency":
            print(f"  {edge['source']} → {edge['target']}")


if __name__ == "__main__":
    main()
