#!/usr/bin/env python3
"""
Robot Config Scanner
Scans all robot configurations (SOUL.md, ROLE_CONFIG.md) and generates robot_registry.json
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path.home() / ".hermes"
OUTPUT_FILE = BASE_DIR / "governance" / "robot_usage_audit" / "robot_registry.json"


def parse_robot_id_from_path(path: Path) -> Optional[str]:
    """Extract robot ID from path like /Users/gino/.hermes/robot-1/SOUL.md"""
    match = re.search(r'robot-\d+', str(path))
    return match.group(0) if match else None


def extract_field(content: str, *patterns) -> Optional[str]:
    """Try multiple regex patterns to extract a field value"""
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def extract_list_field(content: str, *patterns) -> list:
    """Try multiple regex patterns to extract a list field value"""
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            items = re.findall(r'[\w\u4e00-\u9fff\-]+', match.group(1))
            return items
    return []


def extract_enabled(content: str) -> bool:
    """Determine if robot is enabled based on content"""
    disabled_patterns = [
        r'暂停|已暂停|已禁用|disabled|inactive',
        r'禁止.*定时推送',
        r'OBSERVE_ONLY|观察模式',
    ]
    for pattern in disabled_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return False
    return True


def extract_schedule(content: str) -> Optional[str]:
    """Extract schedule/cron information"""
    patterns = [
        r'(?:schedule|cron|定时)[:\s]*([^\n]+)',
        r'(?:每日|每天)[:\s]*([^\n]+)',
    ]
    return extract_field(content, *patterns)


def extract_owner(content: str) -> Optional[str]:
    """Extract owner/maintainer information"""
    patterns = [
        r'(?:owner|负责人|维护)[:\s]*([^\n]+)',
        r'由\s*([^\s]+)\s*管理',
    ]
    return extract_field(content, *patterns)


def extract_dependency(content: str) -> Optional[str]:
    """Extract workflow dependency info"""
    patterns = [
        r'(?:上一级|上一节点|upstream)[:\s]*([^\n]+)',
        r'(?:下一级|下一节点|downstream)[:\s]*([^\n]+)',
        r'(?:依赖|depends? on)[:\s]*([^\n]+)',
    ]
    return extract_field(content, *patterns)


def extract_model(content: str) -> Optional[str]:
    """Extract LLM model information"""
    # First try YAML code block pattern (most reliable)
    yaml_match = re.search(r'```yaml\s+.*?default_model:\s*"?([^"`\n]+)"?', content, re.DOTALL)
    if yaml_match:
        model = yaml_match.group(1).strip()
        # Clean up any markdown artifacts
        model = re.sub(r'^\*\*:\s*', '', model)
        return model

    # Try simple key: value pattern
    patterns = [
        r'default_model[:\s=]*"?([^"`\n]+)"?',
        r'model[:\s=]*"?([^"`\n]+)"?',
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            model = match.group(1).strip()
            # Clean up markdown artifacts
            model = re.sub(r'^\*\*:\s*', '', model)
            if model and model not in ['null', 'None', '']:
                return model
    return None


def extract_last_session(content: str) -> Optional[str]:
    """Extract last session/activity info"""
    patterns = [
        r'(?:last_session|last session|最后会话|上次活动)[:\s]*([^\n]+)',
    ]
    return extract_field(content, *patterns)


def parse_soul_md(path: Path) -> dict:
    """Parse SOUL.md file and extract robot info"""
    try:
        content = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  [WARN] Failed to read {path}: {e}")
        return {}

    robot_name = None
    role = None

    # Extract robot name and role from header line
    # Pattern 1: "# Robot-1: SysAdmin" -> robot_name=Robot-1, role=SysAdmin
    m = re.search(r'^#\s*Robot-(\d+):\s*([^\n]+)', content, re.MULTILINE)
    if m:
        robot_name = f"Robot-{m.group(1)}"
        role = m.group(2).strip()
    else:
        # Pattern 2: "# 自动化市场选股 (robot-10)" -> robot_name=robot-10, role=自动化市场选股
        m = re.search(r'^#\s*([^\n]+?)\s+\((robot-\d+)\)', content, re.MULTILINE)
        if m:
            robot_name = m.group(2).strip()
            role = m.group(1).strip()
        else:
            # Pattern 3: "**名称**: Robot-1"
            m = re.search(r'\*\*名称\*\*[:\s]*([^\n]+)', content)
            if m:
                robot_name = m.group(1).strip()
            # Pattern 4: Chinese style "名称: Robot-1"
            m = re.search(r'^名称[:\s]*Robot-(\d+)', content, re.MULTILINE)
            if m:
                robot_name = f"Robot-{m.group(1)}"

    # Also check for Chinese name patterns
    if not robot_name:
        cn_match = re.search(r'你是\s+\*\*([^\*]+?)\s*\(', content)
        if cn_match:
            robot_name = cn_match.group(1).strip()

    # Extract role
    if not role:
        role_patterns = [
            r'角色[:\s\*]*([^\n\*]+)',
            r'\*\*(?:角色|Role)[:\s]*\*\*\s*([^\n]+)',
            r'(?:🔧|📊|🔍|🛡️|🌐|🎯)\s*([^\n]+)',
        ]
        for pattern in role_patterns:
            match = re.search(pattern, content)
            if match:
                role = match.group(1).strip()
                break

    return {
        'robot_name': robot_name,
        'role': role,
        'enabled': extract_enabled(content),
        'schedule': extract_schedule(content),
        'owner': extract_owner(content),
        'dependency': extract_dependency(content),
        'model': extract_model(content),
        'last_session': extract_last_session(content),
        '_soul_path': str(path),
    }


def parse_role_config_md(path: Path) -> dict:
    """Parse ROLE_CONFIG.md file and extract additional robot info"""
    try:
        content = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  [WARN] Failed to read {path}: {e}")
        return {}

    robot_id = extract_field(content, r'机器人ID[:\s]*([^\n]+)')
    name = extract_field(content, r'名称[:\s]*([^\n]+)')
    role = extract_field(content, r'角色[:\s]*([^\n]+)')
    description = extract_field(content, r'描述[:\s]*([^\n]+)')

    return {
        'robot_id': robot_id,
        'name': name,
        'role': role or description,
        'model': extract_model(content) or None,
        'enabled': extract_enabled(content),
        '_role_config_path': str(path),
    }


def merge_robot_data(soul_data: dict, role_config_data: dict, robot_id: str) -> dict:
    """Merge data from SOUL.md and ROLE_CONFIG.md"""
    # Start with soul data
    merged = {
        'robot_name': soul_data.get('robot_name') or role_config_data.get('name') or robot_id,
        'role': soul_data.get('role') or role_config_data.get('role'),
        'enabled': soul_data.get('enabled', True),
        'schedule': soul_data.get('schedule'),
        'owner': soul_data.get('owner'),
        'dependency': soul_data.get('dependency'),
        'model': soul_data.get('model') or role_config_data.get('model'),
        'last_session': soul_data.get('last_session'),
    }

    return merged


def scan_robots():
    """Scan all robot directories and collect configuration"""
    robots = {}
    processed = 0
    errors = 0

    # Find all robot directories
    robot_dirs = sorted(BASE_DIR.glob("robot-*"))
    profiles_dirs = sorted((BASE_DIR / "profiles").glob("robot-*"))

    print(f"[*] Scanning robot configurations...")
    print(f"[*] Base directory: {BASE_DIR}")
    print(f"[*] Found {len(robot_dirs)} robot directories in ~/.hermes/robot-*")
    print(f"[*] Found {len(profiles_dirs)} robot directories in ~/.hermes/profiles/robot-*")

    # Process each robot directory
    for robot_dir in robot_dirs:
        robot_id = robot_dir.name
        print(f"\n[+] Processing {robot_id}...")

        soul_path = robot_dir / "SOUL.md"
        role_config_path = robot_dir / "ROLE_CONFIG.md"

        soul_data = {}
        role_config_data = {}

        # Parse SOUL.md
        if soul_path.exists():
            print(f"  [*] Parsing SOUL.md...")
            soul_data = parse_soul_md(soul_path)
            if soul_data:
                print(f"      -> Found robot_name: {soul_data.get('robot_name', 'N/A')}")
                print(f"      -> Found role: {soul_data.get('role', 'N/A')}")
        else:
            print(f"  [WARN] SOUL.md not found in {robot_dir}")

        # Parse ROLE_CONFIG.md
        if role_config_path.exists():
            print(f"  [*] Parsing ROLE_CONFIG.md...")
            role_config_data = parse_role_config_md(role_config_path)
            if role_config_data:
                print(f"      -> Found model: {role_config_data.get('model', 'N/A')}")
        else:
            print(f"  [WARN] ROLE_CONFIG.md not found in {robot_dir}")

        # Merge data
        merged = merge_robot_data(soul_data, role_config_data, robot_id)

        # Use robot_id as fallback for robot_name
        if not merged['robot_name']:
            merged['robot_name'] = robot_id

        if merged['robot_name'] == robot_id or not merged['robot_name']:
            # Try to make it more readable
            merged['robot_name'] = robot_id.replace('robot-', 'Robot-').title()

        robots[robot_id] = merged
        processed += 1
        print(f"  [+] {robot_id} processed successfully")

    # Also check profiles directory (backup/alternate location)
    for profiles_dir in profiles_dirs:
        robot_id = profiles_dir.name
        if robot_id not in robots:
            print(f"\n[+] Processing {profiles_dir} (from profiles/)...")
            soul_path = profiles_dir / "SOUL.md"
            if soul_path.exists():
                print(f"  [*] Parsing SOUL.md...")
                soul_data = parse_soul_md(soul_path)
                if soul_data:
                    robots[robot_id] = {
                        'robot_name': soul_data.get('robot_name') or robot_id,
                        'role': soul_data.get('role'),
                        'enabled': soul_data.get('enabled', True),
                        'schedule': soul_data.get('schedule'),
                        'owner': soul_data.get('owner'),
                        'dependency': soul_data.get('dependency'),
                        'model': soul_data.get('model'),
                        'last_session': soul_data.get('last_session'),
                    }
                    processed += 1
                    print(f"  [+] {robot_id} processed successfully")

    return robots, processed, errors


def main():
    print("=" * 60)
    print("Robot Config Scanner")
    print("=" * 60)

    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Scan robots
    robots, processed, errors = scan_robots()

    # Convert to list format for JSON output
    robot_list = []
    for robot_id, data in sorted(robots.items()):
        entry = {
            'robot_name': data.get('robot_name'),
            'role': data.get('role'),
            'enabled': data.get('enabled', True),
            'schedule': data.get('schedule'),
            'owner': data.get('owner'),
            'dependency': data.get('dependency'),
            'model': data.get('model'),
            'last_session': data.get('last_session'),
        }
        robot_list.append(entry)

    # Write output
    output_data = {
        'total_robots': len(robot_list),
        'robots': robot_list,
    }

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n{'=' * 60}")
        print(f"[+] Successfully wrote robot registry to:")
        print(f"    {OUTPUT_FILE}")
        print(f"[+] Total robots processed: {processed}")
        print(f"{'=' * 60}")
    except Exception as e:
        print(f"\n[!] ERROR: Failed to write output: {e}")
        sys.exit(1)

    # Print summary
    print("\n[*] Summary:")
    for entry in robot_list:
        status = "✓" if entry['enabled'] else "✗"
        print(f"  {status} {entry['robot_name']} | {entry['role']} | model: {entry['model'] or 'N/A'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
