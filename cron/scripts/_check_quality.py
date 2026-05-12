#!/usr/bin/env python3
"""检查 daily_features.json 数据质量"""
import json, sys
path = sys.argv[1]
with open(path) as f: d = json.load(f)

required = ["RSI","MA5","MA20","量比","最新价","日涨幅","下影线长度","上影线长度","股价距MA20距离"]
for s in d.get("stocks",[]):
    name = s["stock_name"]
    ind = s.get("indicators",{})
    missing = sum(1 for k in required if ind.get(k, 0) in [0,"",None,"unknown"] or (isinstance(ind.get(k), float) and ind.get(k, 0) == 0.0))
    rate = missing / len(required)
    if rate > 0.3:
        print(f"WARN:{name} 数据缺失率 {rate*100:.0f}%", file=sys.stderr)
        sys.exit(2)

results = {s["stock_name"]: f"{sum(1 for k in required if s['indicators'].get(k, 0) in [0,'',None,'unknown'])}/{len(required)}" for s in d.get("stocks",[])}
print("|".join(f"{k}:{v}" for k,v in results.items()))
