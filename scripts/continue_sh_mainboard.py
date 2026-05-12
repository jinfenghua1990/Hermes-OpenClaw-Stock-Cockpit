#!/usr/bin/env python3
"""
断点续传：继续下载 sh_mainboard 剩余部分
"""

import json
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "scripts" else Path.cwd()
sys.path.append(str(PROJECT_ROOT))

from core.symbol_normalizer import normalize_symbol

# 加载剩余清单
batch_file = PROJECT_ROOT / "data_quality" / "missing_batches" / "sh_mainboard.json"
symbols = json.loads(batch_file.read_text(encoding="utf-8"))

# 检查哪些已下载
kline_dir = PROJECT_ROOT / "data" / "kline_daily"
downloaded = set()
for p in kline_dir.glob("*.csv"):
    downloaded.add(p.stem)

remaining = [s for s in symbols if s not in downloaded]
print(f"[INFO] Total sh_mainboard: {len(symbols)}")
print(f"[INFO] Already downloaded: {len(downloaded)}")
print(f"[INFO] Remaining to download: {len(remaining)}")

if not remaining:
    print("[INFO] All sh_mainboard already downloaded!")
    sys.exit(0)

# 导入下载函数
sys.path.append(str(PROJECT_ROOT / "data_pipeline" / "downloaders"))
from fetch_mainboard_kline import fetch_kline, save_csv, load_failed, save_failed

failed = load_failed()
success = 0
fail = 0
BATCH_SIZE = 50
BATCH_SLEEP = 3

print("\n" + "="*50)
print(f"Starting download of {len(remaining)} remaining symbols...")
print("="*50 + "\n")

for i, symbol in enumerate(remaining):
    print(f"[DOWN] {symbol} ({i+1}/{len(remaining)})")
    result = fetch_kline(symbol)
    
    if result["success"]:
        if save_csv(symbol, result["data"]):
            print(f"[OK] {symbol}")
            success += 1
        else:
            print(f"[FAIL] {symbol} (save error)")
            failed.append({"symbol": symbol, "market": "sh_mainboard", "reason": "save error"})
            fail += 1
    else:
        print(f"[FAIL] {symbol} ({result['reason']})")
        failed.append({"symbol": symbol, "market": "sh_mainboard", "reason": result['reason']})
        fail += 1
    
    # 每 50 只 sleep 3 秒
    if (i + 1) % BATCH_SIZE == 0:
        print(f"[INFO] Processed {i+1}/{len(remaining)}, sleeping {BATCH_SLEEP}s...")
        time.sleep(BATCH_SLEEP)

save_failed(failed)

print("\n" + "="*50)
print("[DONE] Summary:")
print(f"  Success: {success}")
print(f"  Failed:  {fail}")
print(f"  Total:   {len(remaining)}")
print(f"  Failed saved to: {PROJECT_ROOT / 'data_pipeline' / 'logs' / 'failed_symbols.json'}")
print("="*50)