#!/usr/bin/env python3
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
HISTORY_DIR = BASE_DIR / 'system_health' / 'history'

SUCCESS_LIKE = ['success', 'warning_accepted']

index_file = HISTORY_DIR / 'index.json'
summary = {
    'effective_success_statuses': SUCCESS_LIKE,
    'phase': 'Phase-2.4B',
    'observation_mode': 'OBSERVE_ONLY'
}

reports = []
for path in HISTORY_DIR.glob('*.json'):
    if path.name == 'index.json':
        continue
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        status = data.get('overall_status', 'warning')
        reports.append({
            'date': data.get('date', path.stem),
            'status': status,
            'effective_success': status in SUCCESS_LIKE
        })
    except Exception:
        pass

summary['reports'] = sorted(reports, key=lambda x: x['date'], reverse=True)

with open(index_file, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print('health status normalized')
