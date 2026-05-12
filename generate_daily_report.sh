#!/bin/bash

echo "[START] Generate Hermes Daily Market Report"

python report_engine/generators/build_market_summary.py
python report_engine/generators/generate_daily_report.py

echo "[DONE] Daily Market Report generated"
