#!/usr/bin/env python3
"""
Intraday Runtime Factors Builder
Phase-2.8D Full China Market Baseline Selection

合并两层数据:
1. features/cache/daily_technical_factors.json (昨日收盘底座: MA5/MA20/RSI/MA20斜率等)
2. runtime_data/intraday_quote_snapshot.json (AkShare今日实时: pct_chg/最新价/最高/最低/成交量)

盘中 Runtime Factors = 历史底座 + 今日实时覆盖
用于 scanner 在盘中使用今日真实涨跌幅筛选

注意:
- factors pct_chg = 昨日收盘涨幅 (已过时)
- snapshot 涨跌幅 = 今日盘中实时涨幅 (正确)
- 合并后 scanner 用 snapshot 的涨跌幅覆盖 factors 的旧值
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
FACTORS_FILE = BASE_DIR / "features/cache/daily_technical_factors.json"
SNAPSHOT_FILE = BASE_DIR / "runtime_data/intraday_quote_snapshot.json"
OUTPUT_FILE = BASE_DIR / "runtime_data/intraday_runtime_factors.json"


def safe_float(v, default=0.0):
    try:
        return float(str(v).replace('%', '').replace(',', '').strip())
    except:
        return default


def build_intraday_factors():
    """构建盘中 Runtime Factors"""
    print("=" * 60)
    print("Intraday Runtime Factors Builder")
    print("Phase-2.8D Full China Market")
    print("=" * 60)

    # [1/4] 加载昨日 factors 底座
    print("[1/4] 加载昨日收盘 factors 底座...")
    if not FACTORS_FILE.exists():
        print(f"  ❌ 未找到: {FACTORS_FILE}")
        return
    factors_data = json.loads(FACTORS_FILE.read_text(encoding="utf-8"))
    factors = factors_data.get("factors", {})
    print(f"  factors 底座: {len(factors)} 只股票")

    # [2/4] 加载今日实时快照
    print("[2/4] 加载 AkShare 今日实时快照...")
    if not SNAPSHOT_FILE.exists():
        print(f"  ⚠ 未找到: {SNAPSHOT_FILE}，使用 factors 底座不覆盖")
        snapshot = {}
    else:
        snapshot_data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        snapshot = snapshot_data.get("quotes", {})
        print(f"  实时快照: {len(snapshot)} 只股票")

    # [3/4] 合并两层数据
    print("[3/4] 合并 factors + snapshot → intraday_runtime_factors...")
    merged = {}
    quote_data_as_of = ""
    if SNAPSHOT_FILE.exists():
        snap_d = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        quote_data_as_of = snap_d.get("quote_data_as_of", "")

    for symbol, fac in factors.items():
        # 归一化 symbol
        bare = symbol.replace('.SZ', '').replace('.SH', '').replace('sz', '').replace('sh', '')

        # 基础字段来自 factors
        item = dict(fac)

        # 今日实时字段覆盖昨日旧值
        live = snapshot.get(bare, {})
        if live:
            item["latest_close"] = live.get("最新价", item.get("latest_close", 0))
            item["pct_chg"] = live.get("涨跌幅", item.get("pct_chg", 0))
            item["latest_high"] = live.get("最高价", item.get("latest_high", 0))
            item["latest_low"] = live.get("最低价", item.get("最低价", item.get("latest_low", 0)))
            item["volume_ratio"] = live.get("成交量", item.get("volume_ratio", 0))
            # 今日时间戳
            if live.get("时间戳"):
                item["intraday_timestamp"] = live.get("时间戳")

        item["symbol_normalized"] = bare
        merged[bare] = item

    print(f"  合并后: {len(merged)} 只股票")

    # [4/4] 保存
    print("[4/4] 保存 intraday_runtime_factors.json...")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "phase": "Phase-2.8D",
        "generated_at": datetime.now().isoformat(),
        "factor_data_as_of": factors_data.get("generated_at", ""),
        "quote_data_as_of": quote_data_as_of,
        "total_symbols": len(merged),
        "factors": merged,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  已保存: {OUTPUT_FILE}")

    # 验证 300677
    test = merged.get("300677", {})
    if test:
        print(f"\n[验证] 300677 英科医疗:")
        print(f"  涨跌幅(pct_chg): {test.get('pct_chg')}%  ← 今日盘中实时（应该是 ~1%）")
        print(f"  最新价: {test.get('latest_close')}")
        print(f"  最高: {test.get('latest_high')}")
        print(f"  最低: {test.get('latest_low')}")
        print(f"  时间: {test.get('intraday_timestamp', 'N/A')}")

    print("=" * 60)
    print("完成")


if __name__ == "__main__":
    build_intraday_factors()
