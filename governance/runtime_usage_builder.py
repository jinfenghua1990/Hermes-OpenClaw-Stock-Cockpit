#!/usr/bin/env python3
"""
Phase-2.4B-Stable
Runtime Usage Builder

从 module_runtime_schema.yaml 自动生成 runtime_usage_summary.json
避免 schema 有、summary 没有的数据不一致

流程:
  module_runtime_schema.yaml (source of truth)
    ↓
  runtime_usage_builder.py
    ↓
  reports/runtime_usage_summary.json (auto generated)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ 缺少 PyYAML 依赖，请执行: pip install pyyaml")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BASE_DIR / "governance" / "module_runtime_schema.yaml"
OUTPUT_PATH = BASE_DIR / "reports" / "runtime_usage_summary.json"


def load_schema():
    """加载 YAML schema"""
    if not SCHEMA_PATH.exists():
        print(f"❌ schema 文件不存在: {SCHEMA_PATH}")
        sys.exit(1)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_previous_summary():
    """加载上一次的 summary（保留 runtime_detected / last_runtime 等运行时状态）"""
    previous = {}
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for mod in data.get("modules", []):
                    previous[mod.get("name")] = {
                        "runtime_detected": mod.get("runtime_detected", False),
                        "last_runtime": mod.get("last_runtime", None),
                    }
        except (json.JSONDecodeError, Exception):
            pass
    return previous


def build_runtime_summary(schema, previous):
    """从 schema 构建 runtime summary"""
    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": str(SCHEMA_PATH.name),
        "total_modules": 0,
        "layers": {},
        "modules": []
    }

    layers = schema.get("layers", {})

    for layer_name, modules in layers.items():
        layer_modules = []
        for module in modules:
            name = module.get("name", "unknown")
            enabled = module.get("enabled", True)

            # 保留上一次的运行时状态
            prev = previous.get(name, {})
            runtime_detected = prev.get("runtime_detected", False)
            last_runtime = prev.get("last_runtime", None)

            entry = {
                "name": name,
                "layer": layer_name,
                "enabled": enabled,
                "runtime_detected": runtime_detected,
                "last_runtime": last_runtime
            }
            summary["modules"].append(entry)
            layer_modules.append(entry)

        summary["layers"][layer_name] = {
            "module_count": len(layer_modules),
            "modules": [m["name"] for m in layer_modules]
        }

    summary["total_modules"] = len(summary["modules"])
    return summary


def save_summary(summary):
    """写入 JSON 文件"""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"✅ runtime_usage_summary.json rebuilt")
    print(f"   └── {OUTPUT_PATH}")
    print(f"   └── {summary['total_modules']} modules in {len(summary['layers'])} layers")


if __name__ == "__main__":
    print("=" * 50)
    print("Runtime Usage Builder ─ Phase-2.4B-Stable")
    print("=" * 50)

    schema = load_schema()
    previous = load_previous_summary()
    summary = build_runtime_summary(schema, previous)
    save_summary(summary)
