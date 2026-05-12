#!/usr/bin/env python3
"""
Data Quality Layer - 质量评分检查
Phase-1.6 观察期：不拦截 cron 主流程，仅生成报告供 robot-4 参考
"""
import json
import sys
from pathlib import Path

def check_quality():
    BASE = Path("/Users/gino/project_ai_trading")
    features_path = BASE / "features" / "daily_features.json"
    rules_path = BASE / "data_quality" / "quality_rules.json"
    output_path = BASE / "data_quality" / "daily_quality_report.json"

    with open(features_path) as f:
        features = json.load(f)
    with open(rules_path) as f:
        rules = json.load(f)

    required = rules["required_fields"]
    weights = rules["weights"]
    min_score = rules["minimum_quality_score"]

    # 字段映射：quality 字段名 → features 指标名
    field_map = {
        "close": "最新价",
        "ma20": "MA20",
        "rsi": "RSI",
        "volume_ratio": "量比",
        "daily_change_pct": "日涨幅",
        "upper_shadow_pct": "上影线长度",
        "lower_shadow_pct": "下影线长度",
        "yesterday_limit_up": "昨日涨停",
    }

    results = []
    for stock in features.get("stocks", []):
        code = stock["stock_code"]
        name = stock["stock_name"]
        ind = stock.get("indicators", {})

        missing_required = []
        missing_optional = []
        total_weight = 0
        earned_weight = 0

        for field in required:
            feat_key = field_map[field]
            val = ind.get(feat_key, 0)
            total_weight += weights.get(field, 0)
            if val not in [0, "", None, "unknown", "N/A"] and isinstance(val, (int, float)) and val != 0.0:
                earned_weight += weights.get(field, 0)
            else:
                missing_required.append(feat_key)

        for field in rules.get("optional_fields", []):
            feat_key = field_map.get(field, field)
            val = ind.get(feat_key, 0)
            total_weight += weights.get(field, 0)
            if val not in [0, "", None, "unknown", "N/A"] and isinstance(val, (int, float)) and val != 0.0:
                earned_weight += weights.get(field, 0)
            else:
                missing_optional.append(feat_key)

        quality_score = int(earned_weight / total_weight * 100) if total_weight > 0 else 0
        feature_ready = quality_score >= min_score

        results.append({
            "stock_code": code,
            "stock_name": name,
            "quality_score": quality_score,
            "missing_fields": missing_required,
            "optional_missing": missing_optional,
            "data_source": "eastmoney",
            "feature_ready": feature_ready
        })

    with open(output_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 输出摘要
    ready = [r for r in results if r["feature_ready"]]
    not_ready = [r for r in results if not r["feature_ready"]]
    print(f"✅ 质量检查完成: {len(ready)} 只可参与匹配, {len(not_ready)} 只被过滤")
    for r in not_ready:
        print(f"  ⚠️  {r['stock_name']}({r['stock_code']}): score={r['quality_score']} < {min_score}, missing={r['missing_fields']}")

    return results

if __name__ == "__main__":
    check_quality()
