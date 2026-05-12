#!/usr/bin/env python3
"""更新 cron_status.json"""
import json, sys
path, last_run = sys.argv[1], sys.argv[2]
try:
    with open(path) as f: d = json.load(f)
except: d = {}
d["last_run"] = last_run
d["last_success"] = last_run
with open(path, "w") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
