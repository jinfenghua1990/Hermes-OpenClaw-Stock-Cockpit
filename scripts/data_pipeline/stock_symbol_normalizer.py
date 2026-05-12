"""
Phase-2.3B-Fix: 股票代码规范化工具
职责：
1. 统一 A股普通代码格式（去除 SH/SZ 前缀）
2. 区分指数代码和个股代码
3. 生成规范化股票池（区分沪/深/科创/北交所）
4. 排除基金/ETF/可转债/B股/退市股
"""

import re
from pathlib import Path

# ── A股代码分类 ─────────────────────────────────────────────────────────────
def normalize_code(raw: str) -> dict:
    """将各种格式的股票代码规范化为标准结构"""
    raw = str(raw).strip().upper()
    original = raw

    # 去除交易所前缀
    raw = re.sub(r"^(SH|SZ|BJ)\s*", "", raw)

    # 补齐6位
    raw = raw.zfill(6)

    # 分类
    if re.match(r"^(000|001|002|003)\d{3}$", raw):
        board = "深主板/中小板"; exchange = "SZ"
    elif re.match(r"^(300|301)\d{3}$", raw):
        board = "创业板"; exchange = "SZ"
    elif re.match(r"^(600|601|603|605)\d{3}$", raw):
        board = "沪主板"; exchange = "SH"
    elif re.match(r"^68[89]\d{3}$", raw):
        board = "科创板"; exchange = "SH"
    elif re.match(r"^83\d{3}$", raw):
        board = "北交所"; exchange = "BJ"
    elif re.match(r"^4\d{5}$", raw):
        board = "老三板"; exchange = "SZ"
    elif re.match(r"^(150|159|510|511|512|513|515|588|589)\d{3}$", raw):
        board = "基金/ETF"; exchange = None
    elif re.match(r"^9\d{5}$", raw):
        board = "退市"; exchange = None
    elif re.match(r"^2\d{5}$", raw):
        board = "B股"; exchange = None
    else:
        board = "未知"; exchange = None

    return {
        "original": original,
        "code": raw,
        "board": board,
        "exchange": exchange,
        "is_a_stock": board in ("深主板/中小板","创业板","沪主板","科创板","北交所"),
    }

def is_index(code: str) -> bool:
    """判断是否为指数（排除）"""
    # 上证指数 000001, 深证成指 399001, 创业板指 399006, 科创50 000688 等
    INDEX_CODES = {
        "000001", "000300", "000016", "000688",  # 常见宽基指数
        "399001", "399005", "399006", "399300",
        "000905", "000852", "000906", "000907",
    }
    return code in INDEX_CODES

# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            r = normalize_code(arg)
            print(f"{arg:10s} → {r}")
    else:
        # 演示
        tests = ["000001", "SZ000001", "SH600519", "300750", "688981", "833171", "150001", "900001"]
        for t in tests:
            r = normalize_code(t)
            print(f"{t:12s} → {r['code']}  {r['board']:10s}  is_stock={r['is_a_stock']}")
