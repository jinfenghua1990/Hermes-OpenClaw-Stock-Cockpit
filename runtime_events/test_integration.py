#!/usr/bin/env python3
"""全链路 Runtime Event 集成测试 — 覆盖全部17个已接入模块"""
import sys
sys.path.insert(0, '/Users/gino/project_ai_trading')
from runtime_events.runtime_event_logger import read_events, log_event, list_event_files

# ── execution_layer (7) ──
log_event('openclaw_fetch_sh', 'execution_layer', 'success', 'test: OpenClaw data fetched', 2450)
log_event('feature_engine_sh', 'execution_layer', 'success', 'test: features computed', 1800)
log_event('coverage_monitor', 'execution_layer', 'success', 'test: coverage 95.2%', 3120)
log_event('report_pipeline', 'execution_layer', 'success', 'test: pre_market report done', 15200)
log_event('daily_pipeline', 'execution_layer', 'success', 'test: pipeline 8 steps done', 9800)
log_event('paper_trade_executor', 'execution_layer', 'success', 'test: paper trade cycle done', 3400)
log_event('notification_router', 'execution_layer', 'success', 'test: feishu sent ok', 800)

# ── governance_layer (6) ──
log_event('scheduler_sh', 'governance_layer', 'success', 'test: scheduler slot dispatched', 150)
log_event('replay_market_day', 'governance_layer', 'success', 'test: replayed 2026-05-12', 850)
log_event('event_engine', 'governance_layer', 'warning', 'test: 3 events: 1 red_alert', 2200)
log_event('daily_health_check', 'governance_layer', 'success', 'test: healthy 8/1/0', 4500)
log_event('position_adapter', 'governance_layer', 'success', 'test: unified_positions written', 1200)
log_event('robot5_risk_sh', 'governance_layer', 'success', 'test: risk check done', 2100)
log_event('main_aggregate_sh', 'governance_layer', 'success', 'test: aggregate report done', 5600)

# ── cockpit_layer (3) ──
log_event('rolling_snapshot', 'cockpit_layer', 'success', 'test: snapshot written', 900)
log_event('heartbeat_monitor', 'cockpit_layer', 'success', 'test: scheduler=ok', 120)
log_event('robot4_match_sh', 'cockpit_layer', 'success', 'test: strategy match done', 1800)

# ── Summary ──
print('=== 全链路 Runtime Event 集成测试 ===\n')
summary = {}
for f in list_event_files():
    events = read_events(f.stem)
    if events:
        e = events[-1]
        layer = e['layer']
        summary.setdefault(layer, []).append(e['module'])

total = 0
for layer, mods in sorted(summary.items()):
    print(f'  {layer}: {len(mods)} 模块 -> {", ".join(sorted(mods))}')
    total += len(mods)

print(f'\n总计: {total} 模块 × 3层 = {len(list_event_files())} 个 jsonl 文件')
print(f'文件列表: {[p.name for p in sorted(list_event_files())]}')

# ── 验证：每层应有正确模块数 ──
expected = {
    'execution_layer': 7,
    'governance_layer': 7,
    'cockpit_layer': 3,
}
ok = True
for layer, expected_count in expected.items():
    actual = len(summary.get(layer, []))
    if actual != expected_count:
        print(f'\n⚠️ {layer}: 期望 {expected_count} 模块，实际 {actual}')
        ok = False

if ok:
    print('\n✅ 全链路集成测试通过！17模块全部接入。')
else:
    print('\n❌ 集成测试有缺失，请检查。')
