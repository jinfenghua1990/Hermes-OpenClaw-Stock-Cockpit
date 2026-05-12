#!/usr/bin/env python3
"""
Candidate Pool Layer - 候选股缓存管理器
Phase-1.6 观察期：仅缓存，不参与自动交易/审批/下单
Usage:
  python3 update_pool.py morning   # 08:30 盘前缓存
  python3 update_pool.py afternoon # 13:30 下午缓存
  python3 update_pool.py hot_sector # 热点板块缓存（收盘后）
  python3 update_pool.py merge     # 合并当日候选股到缓存
"""
import json
import sys
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/gino/project_ai_trading")
CANDIDATE_POOL_DIR = BASE / "candidate_pool"

POOL_FILES = {
    "morning": CANDIDATE_POOL_DIR / "morning_pool.json",
    "afternoon": CANDIDATE_POOL_DIR / "afternoon_pool.json",
    "hot_sector": CANDIDATE_POOL_DIR / "hot_sector_pool.json",
}

def load_features():
    """加载 Feature Engine 输出"""
    path = BASE / "features" / "daily_features.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("stocks", [])

def load_strategy():
    """加载 robot-4 模式匹配结果"""
    path = BASE / "logs" / "robot4_strategy.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)

def update_pool(pool_type):
    """
    更新候选股缓存池
    - morning: 08:30 盘前，基于 Feature Engine 初筛
    - afternoon: 13:30 下午，更新日内特征
    - hot_sector: 收盘后，热点板块候选
    """
    ts = datetime.now()
    pool_file = POOL_FILES.get(pool_type)
    if not pool_file:
        print(f"❌ 未知池类型: {pool_type}")
        return

    features = load_features()
    strategy = load_strategy() if pool_type in ["afternoon", "hot_sector"] else {}

    # 从 strategy 获取 pattern_match 结果
    matched_stocks = {
        s["stock_code"]: s
        for s in strategy.get("matched_stocks", [])
    }

    # 质量检查
    quality_path = BASE / "data_quality" / "daily_quality_report.json"
    quality_map = {}
    if quality_path.exists():
        with open(quality_path) as f:
            for q in json.load(f):
                quality_map[q["stock_code"]] = q

    candidates = []
    for stock in features:
        code = stock["stock_code"]
        name = stock["stock_name"]
        ind = stock.get("indicators", {})

        # 简单热度评分（基于 RSI 中性度 + 量比）
        rsi = ind.get("RSI", 50)
        volume_ratio = ind.get("量比", 1.0)
        heat_score = max(0, min(100, int(50 - abs(rsi - 50) + (volume_ratio - 1) * 20)))

        quality = quality_map.get(code, {})
        feature_quality = quality.get("quality_score", 0)

        candidates.append({
            "date": ts.strftime("%Y-%m-%d"),
            "stock_code": code,
            "stock_name": name,
            "sector": stock.get("sector", ""),
            "source": "robot-3",
            "heat_score": heat_score,
            "feature_quality": feature_quality,
            "rsi": ind.get("RSI", 0),
            "volume_ratio": volume_ratio,
            "ma20_distance": ind.get("股价距MA20距离", 0),
            "pattern_match": [matched_stocks[code]] if code in matched_stocks else []
        })

    # 按热度排序，保留 top 20
    candidates.sort(key=lambda x: x["heat_score"], reverse=True)
    candidates = candidates[:20]

    with open(pool_file, "w") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    print(f"✅ {pool_type} pool 更新: {len(candidates)} 只候选")
    for c in candidates[:5]:
        print(f"   {c['stock_name']}({c['stock_code']}): heat={c['heat_score']} quality={c['feature_quality']}")
    if len(candidates) > 5:
        print(f"   ... 还有 {len(candidates)-5} 只")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: update_pool.py [morning|afternoon|hot_sector|merge]")
        sys.exit(1)
    cmd = sys.argv[1]
    update_pool(cmd)
