#!/usr/bin/env python3
"""
robot-3 Feature Engine v10.0
处理三种 raw.json table key 格式:
1. stock_name(SZ/SH) = [vals]  (A股股票名列)
2. 中文指标名 = [vals]  (中文指标名列)
3. field_code = [vals] (field_set列)
"""

import subprocess
import json
import time
import re
from pathlib import Path
from datetime import datetime

MX_DATA = "/Users/gino/.hermes/skills/mx-data/mx_data.py"
OUT_DIR = Path("/Users/gino/mx_data_output")
FEATURES_DIR = Path("/Users/gino/project_ai_trading/features")
FEATURES_DIR.mkdir(parents=True, exist_ok=True)


def safe_float(v, default=0.0):
    try:
        return float(str(v).replace('%','').replace('元','').replace('港元','').strip())
    except:
        return default


def call_mx_data(query: str):
    r = subprocess.run(
        ["python3", MX_DATA, query, str(OUT_DIR)],
        capture_output=True, text=True, timeout=30
    )
    time.sleep(4)
    return r.returncode == 0


def get_all_raw_files(code: str) -> list:
    return sorted(Path(OUT_DIR).glob(f"*{code}*_raw.json"), key=lambda x: -x.stat().st_mtime)


def parse_raw_v10(raw_path: Path) -> dict:
    """解析 raw.json v10: 处理三种格式"""
    result = {}
    try:
        with open(raw_path) as f:
            d = json.load(f)
        
        tables = (d.get('data', {})
                   .get('data', {})
                   .get('searchDataResultDTO', {})
                   .get('dataTableDTOList', []))
        
        for t in tables:
            name_map = t.get('nameMap', {})
            table = t.get('table', {})
            field_set = t.get('fieldSet', [])
            field_return_name = t.get('field', {}).get('returnName', '')  # 查询的指标名
            
            table_keys = [k for k in table.keys() if k not in ('headName', 'headNameSub')]
            
            for key in table_keys:
                col_values = table.get(key, [])
                if not isinstance(col_values, list) or not col_values:
                    continue
                
                val = safe_float(col_values[0])
                
                # 判断 key 类型
                if '.SZ)' in key or '.SH)' in key:
                    # 格式1: stock name - 找 returnName 作为指标名
                    indicator_name = field_return_name
                    if indicator_name:
                        if '最新价' in indicator_name:
                            result['最新价'] = val
                        elif '收盘价' in indicator_name:
                            if '收盘价_list' not in result:
                                result['收盘价_list'] = []
                            result['收盘价_list'].extend([safe_float(v) for v in col_values if safe_float(v) > 0])
                
                elif key in name_map:
                    # 格式2/3: field_code 或中文指标名
                    indicator_name = name_map.get(key, '')
                    if not indicator_name or indicator_name == '数据来源':
                        continue
                    
                    if 'MA5' in indicator_name or ('5日' in indicator_name and '10' not in indicator_name and '20' not in indicator_name):
                        result['MA5'] = val
                    elif 'MA10' in indicator_name or '10日' in indicator_name:
                        result['MA10'] = val
                    elif 'MA20' in indicator_name or '20日' in indicator_name:
                        result['MA20'] = val
                    elif 'RSI' in indicator_name and 'MA' not in indicator_name:
                        result['RSI'] = val
                    elif '量比' in indicator_name and 'MA' not in indicator_name:
                        result['量比'] = val
                    elif '最低价' in indicator_name:
                        result['最低价'] = val
                    elif '最高价' in indicator_name:
                        result['最高价'] = val
                    elif '开盘价' in indicator_name:
                        result['开盘价'] = val
                    elif '昨收' in indicator_name or '前收盘' in indicator_name:
                        result['昨收'] = val
                
                elif key == field_return_name:
                    # 格式2: 直接用 returnName（如"最新价"）
                    if '最低价' in key:
                        result['最低价'] = val
                    elif '最高价' in key:
                        result['最高价'] = val
                    elif '开盘价' in key:
                        result['开盘价'] = val
                    elif '昨收' in key:
                        result['昨收'] = val
                    elif '最新价' in key:
                        result['最新价'] = val
                    elif '收盘价' in key:
                        if '收盘价_list' not in result:
                            result['收盘价_list'] = []
                        result['收盘价_list'].extend([safe_float(v) for v in col_values if safe_float(v) > 0])
    
    except Exception as e:
        print(f"    parse error {raw_path.name}: {e}")
    
    return result


def get_stock_features(code: str, name: str) -> dict:
    print(f"  正在获取 {name}({code}) 指标...")
    
    features = {
        "stock_code": code,
        "stock_name": name,
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "indicators": {}
    }
    ind = features["indicators"]
    
    try:
        queries = [
            f"{name} {code} MA5 MA20 RSI 量比",
            f"{name} {code} 最低价 最高价 开盘价",
            f"{name} {code} 昨收",
            f"{name} {code} 收盘价 10日",
            f"{name} {code} 最新价",
        ]
        for q in queries:
            call_mx_data(q)
            time.sleep(3)
        
        # 合并所有 raw.json
        all_data = {}
        for raw in get_all_raw_files(code):
            data = parse_raw_v10(raw)
            all_data.update(data)
        
        ind.update(all_data)
        
        closes = sorted(set(ind.get('收盘价_list', [])), reverse=True)
        
        close = ind.get('最新价', 0) or ind.get('昨收', 0)
        ma5 = ind.get('MA5', 0)
        ma20 = ind.get('MA20', 0)
        rsi = ind.get('RSI', 0)
        vol_ratio = ind.get('量比', 0)
        prev_close = ind.get('昨收', 0)
        high = ind.get('最高价', 0)
        low = ind.get('最低价', 0)
        
        # 日涨幅
        ind['日涨幅'] = round((close - prev_close) / prev_close * 100, 2) if prev_close > 0 and close > 0 else 0.0
        
        # 上下影线
        if close > 0 and high > 0 and low > 0:
            ind['上影线长度'] = round((high - close) / close * 100, 2)
            ind['下影线长度'] = round((close - low) / close * 100, 2)
        else:
            ind['上影线长度'] = 0.0
            ind['下影线长度'] = 0.0
        
        # 股价距MA20距离
        ind['股价距MA20距离'] = round((close - ma20) / ma20 * 100, 2) if ma20 > 0 and close > 0 else 0.0
        
        # MA5 > MA20
        ind['MA5大于MA20'] = bool(ma5 > ma20) if ma5 > 0 and ma20 > 0 else False
        
        # MA20趋势
        if len(closes) >= 5 and closes[0] > 0 and closes[4] > 0:
            slope = (closes[0] - closes[4]) / closes[4] * 100
            ind['MA20斜率'] = round(slope, 2)
            ind['MA20趋势'] = "up" if slope > 0.3 else ("down" if slope < -0.3 else "flat")
        else:
            ind['MA20趋势'] = "unknown"
            ind['MA20斜率'] = 0.0
        
        # 昨日涨停
        if len(closes) >= 3 and closes[1] > 0 and closes[2] > 0:
            prev_chg = (closes[1] - closes[2]) / closes[2] * 100
            ind['昨日涨停'] = bool(prev_chg >= 9.9)
            ind['昨日涨幅'] = round(prev_chg, 2)
        else:
            ind['昨日涨停'] = False
            ind['昨日涨幅'] = 0.0
        
        ind.pop('收盘价_list', None)
        
        print(f"    ✅ {name}: 最新价={close}, RSI={rsi}, MA5={ma5}, MA20={ma20}, "
              f"MA20趋势={ind.get('MA20趋势','?')}, 量比={vol_ratio}, "
              f"日涨幅={ind.get('日涨幅','?')}%, 下影={ind.get('下影线长度','?')}%, "
              f"昨涨={ind.get('昨日涨幅','?')}%, 昨涨停={ind.get('昨日涨停')}")
        
    except Exception as e:
        import traceback
        print(f"    ❌ {name} 失败: {e}")
        traceback.print_exc()
    
    return features


def main():
    print("=" * 60)
    print("robot-3 Feature Engine v10.0 开始运行")
    print("=" * 60)
    
    stocks = [
        ("301282", "金禄电子"),
        ("300476", "胜宏科技"),
        ("002130", "沃尔核材"),
        ("603629", "利通电子"),
        ("002463", "沪电股份"),
    ]
    
    all_features = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "robot": "robot-3 Feature Engine v10.0",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "stocks": []
    }
    
    for code, name in stocks:
        feat = get_stock_features(code, name)
        all_features["stocks"].append(feat)
    
    out_path = FEATURES_DIR / "daily_features.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_features, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ daily_features.json 已保存: {out_path}")


if __name__ == "__main__":
    main()
