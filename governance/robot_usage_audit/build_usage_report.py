#!/usr/bin/env python3
"""
Build Usage Report - Reads 4 robot usage JSONs and outputs robot_usage_report.md with A/B/C/D grades
"""

import json
import os
from datetime import datetime
from collections import defaultdict

ROBOT_DIRS = [
    "/Users/gino/.hermes-robot-1",
    "/Users/gino/.hermes-robot-2",
    "/Users/gino/.hermes-robot-3",
    "/Users/gino/.hermes-robot-4",
]

USAGE_FILENAME = "skills/.usage.json"
OUTPUT_FILENAME = "/Users/gino/robot_usage_report.md"


def parse_timestamp(ts_str):
    """Parse ISO timestamp, return epoch seconds or 0 if None."""
    if ts_str is None:
        return 0
    try:
        return datetime.fromisoformat(ts_str.replace("+00:00", "+0000")).timestamp()
    except Exception:
        return 0


def calculate_score(skill_data, now_ts):
    """
    Calculate a usage score for a skill based on:
    - use_count (weighted heavily)
    - view_count (weighted moderately)
    - recency of last_used_at (bonus for recent usage)
    - patch_count (indicates active development)
    """
    use_count = skill_data.get("use_count", 0)
    view_count = skill_data.get("view_count", 0)
    patch_count = skill_data.get("patch_count", 0)
    last_used = parse_timestamp(skill_data.get("last_used_at"))
    last_viewed = parse_timestamp(skill_data.get("last_viewed_at"))

    # Base score from counts
    score = use_count * 10 + view_count * 2 + patch_count * 3

    # Recency bonus (up to 50 points if used/viewed recently)
    recency = max(last_used, last_viewed)
    if recency > 0:
        days_ago = (now_ts - recency) / 86400
        if days_ago < 1:
            score += 50
        elif days_ago < 7:
            score += 30
        elif days_ago < 30:
            score += 15

    return score


def assign_grade(score, all_scores):
    """Assign A/B/C/D grade based on percentile ranking."""
    if not all_scores:
        return "D"
    
    sorted_scores = sorted(all_scores, reverse=True)
    n = len(sorted_scores)
    
    # Find rank of this score
    rank = next(i for i, s in enumerate(sorted_scores) if s == score)
    percentile = (n - rank) / n * 100
    
    if percentile >= 75:
        return "A"
    elif percentile >= 50:
        return "B"
    elif percentile >= 25:
        return "C"
    else:
        return "D"


def load_robot_usage(robot_path):
    """Load usage data from a robot's .usage.json file."""
    usage_path = os.path.join(robot_path, USAGE_FILENAME)
    if not os.path.exists(usage_path):
        return {}
    
    with open(usage_path, "r") as f:
        return json.load(f)


def main():
    now_ts = datetime.now().timestamp()
    
    # Collect all skills across all robots
    robot_data = {}
    all_skills_scores = {}  # skill_name -> list of (robot_id, score)
    
    for robot_dir in ROBOT_DIRS:
        robot_name = os.path.basename(robot_dir)
        usage = load_robot_usage(robot_dir)
        robot_data[robot_name] = usage
        
        # Calculate scores for each skill in this robot
        for skill_name, skill_data in usage.items():
            score = calculate_score(skill_data, now_ts)
            if skill_name not in all_skills_scores:
                all_skills_scores[skill_name] = []
            all_skills_scores[skill_name].append((robot_name, score))
    
    # Build markdown report
    lines = []
    lines.append("# Robot Usage Report")
    lines.append(f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    
    # Summary table
    lines.append("## Summary\n")
    lines.append("| Robot | Total Skills | Total Uses | Total Views | Grade |")
    lines.append("|-------|-------------|------------|-------------|-------|")
    
    robot_summaries = []
    all_robot_scores = []
    
    for robot_dir in ROBOT_DIRS:
        robot_name = os.path.basename(robot_dir)
        usage = robot_data.get(robot_name, {})
        
        total_uses = sum(s.get("use_count", 0) for s in usage.values())
        total_views = sum(s.get("view_count", 0) for s in usage.values())
        skill_count = len(usage)
        
        # Calculate robot-level score
        robot_score = sum(calculate_score(s, now_ts) for s in usage.values())
        all_robot_scores.append((robot_name, robot_score, skill_count, total_uses, total_views))
    
    # Assign grades to robots
    robot_score_values = [x[1] for x in all_robot_scores]
    for i, (robot_name, score, skill_count, total_uses, total_views) in enumerate(all_robot_scores):
        grade = assign_grade(score, robot_score_values)
        lines.append(f"| {robot_name} | {skill_count} | {total_uses} | {total_views} | **{grade}** |")
    
    lines.append("")
    
    # Detailed skill breakdown per robot
    lines.append("## Skill Details\n")
    
    for robot_dir in ROBOT_DIRS:
        robot_name = os.path.basename(robot_dir)
        usage = robot_data.get(robot_name, {})
        
        if not usage:
            continue
        
        lines.append(f"### {robot_name}\n")
        lines.append("| Skill | Use Count | View Count | Patch Count | Last Used | Grade |")
        lines.append("|-------|-----------|------------|-------------|-----------|-------|")
        
        # Get all skill scores for this robot for grading
        skill_scores = {name: calculate_score(data, now_ts) for name, data in usage.items()}
        score_values = list(skill_scores.values())
        
        for skill_name, skill_data in sorted(usage.items(), key=lambda x: skill_scores.get(x[0], 0), reverse=True):
            score = skill_scores.get(skill_name, 0)
            grade = assign_grade(score, score_values)
            
            use_count = skill_data.get("use_count", 0)
            view_count = skill_data.get("view_count", 0)
            patch_count = skill_data.get("patch_count", 0)
            last_used = skill_data.get("last_used_at")
            
            if last_used:
                try:
                    last_used_str = datetime.fromisoformat(last_used.replace("+00:00", "+0000")).strftime("%Y-%m-%d")
                except Exception:
                    last_used_str = "N/A"
            else:
                last_used_str = "Never"
            
            lines.append(f"| {skill_name} | {use_count} | {view_count} | {patch_count} | {last_used_str} | **{grade}** |")
        
        lines.append("")
    
    # Grade distribution
    lines.append("## Grade Distribution\n")
    lines.append("\n**Grade Criteria:**")
    lines.append("- **A** (Top 25%): Highly active, recently used skills")
    lines.append("- **B** (50-75%): Moderately active skills")
    lines.append("- **C** (25-50%): Low activity skills")
    lines.append("- **D** (Bottom 25%): Minimal or no usage\n")
    
    # Write output
    output_path = OUTPUT_FILENAME
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    
    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    main()
