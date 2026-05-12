"""
Phase-2.3B-Fix: 股票池清洗
保留 A股个股，排除：指数/基金/ETF/可转债/B股/退市股
输出：data/stock_pool_a_clean.csv
"""

import akshare as ak
import csv
from pathlib import Path

DATA_HOME = Path("/Users/gino/project_ai_trading/data")
OUT_FILE  = DATA_HOME / "stock_pool_a_clean.csv"

# A股代码范围
VALID_PREFIXES = (
    "000", "001", "002", "003",  # 深市主板/中小板
    "300", "301",                  # 创业板
    "600", "601", "603", "605",   # 沪市主板
    "688", "689",                  # 科创板
    "8",                           # 北交所
)

def main():
    print("正在获取股票列表...")
    df = ak.stock_info_a_code_name()
    print(f"原始股票数: {len(df)}")

    rows = []
    for _, r in df.iterrows():
        code = str(r["code"]).strip().zfill(6)
        name = str(r.get("name", "")).strip()
        if not code.isdigit():
            continue
        # 排除：指数(000xxx前缀但非个股)、基金(150/159/510/512/513/515/588开头)
        if code.startswith(("150","159","510","511","512","513","515","588","589")):
            continue
        if code.startswith("4") or code.startswith("9"):
            continue  # 退市股/4开头的老三板
        if code.startswith("2"):
            continue  # B股
        # 只保留A股代码范围
        if not code.startswith(VALID_PREFIXES):
            continue

        # 判断交易所
        if code.startswith(("000","001","002","003","300","301","8")):
            exchange = "SZ"
        else:
            exchange = "SH"

        rows.append({
            "code": code,
            "name": name,
            "exchange": exchange,
            "board": _board(code),
            "is_st": "ST" in name,
        })

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code","name","exchange","board","is_st"])
        w.writeheader()
        w.writerows(rows)

    print(f"清洗后股票数: {len(rows)}")
    print(f"已保存: {OUT_FILE}")
    print(f"ST股: {sum(1 for r in rows if r['is_st'])}")
    print(f"沪市: {sum(1 for r in rows if r['exchange']=='SH')}")
    print(f"深市: {sum(1 for r in rows if r['exchange']=='SZ')}")

def _board(code):
    if code.startswith("688") or code.startswith("689"): return "科创板"
    if code.startswith("300") or code.startswith("301"): return "创业板"
    if code.startswith("8"): return "北交所"
    if code.startswith(("600","601","603","605")): return "沪主板"
    if code.startswith("002"): return "中小板"
    return "深主板"

if __name__ == "__main__":
    main()
