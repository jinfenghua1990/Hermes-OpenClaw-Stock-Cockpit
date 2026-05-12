import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
from core.symbol_normalizer import normalize_symbol

REPORT_PATH = Path("data_quality/coverage_report.json")
OUTPUT_DIR = Path("data_quality/missing_batches")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def classify_market(symbol: str) -> str:
    # 去掉 .SH/.SZ 后缀
    s = normalize_symbol(str(symbol).zfill(6))
    code = s.split(".")[0]
    if code.startswith(("600", "601", "603", "605")):
        return "sh_mainboard"
    if code.startswith(("000", "001", "002", "003")):
        return "sz_mainboard"
    if code.startswith("300"):
        return "gem"
    if code.startswith("688"):
        return "star"
    return "other"


def main():
    if not REPORT_PATH.exists():
        raise FileNotFoundError(f"coverage report not found: {REPORT_PATH}")
    
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    missing = report.get("missing_symbols", [])
    
    batches = {
        "sh_mainboard": [],
        "sz_mainboard": [],
        "gem": [],
        "star": [],
        "other": []
    }
    
    for raw in missing:
        symbol = normalize_symbol(str(raw).zfill(6))
        market = classify_market(symbol)
        batches[market].append(symbol)
    
    for market, symbols in batches.items():
        path = OUTPUT_DIR / f"{market}.json"
        path.write_text(
            json.dumps(symbols, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[OK] {market}: {len(symbols)} -> {path}")
    
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(
        json.dumps({k: len(v) for k, v in batches.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print("[DONE] missing batches generated")


if __name__ == "__main__":
    main()
