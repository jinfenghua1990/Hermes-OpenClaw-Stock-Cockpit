#!/usr/bin/env python3
"""
Phase-2.6C Paper Decision Engine — Full Decision Traceability
Phase-2.6D: 新增 Risk Price Validation Gate（统一调用 governance/risk_price_validation.py）
"""
import json, os, sys, yaml
from datetime import datetime
from pathlib import Path

BASE        = Path('/Users/gino/project_ai_trading')
TOP_PICKS   = BASE / 'reports/top_picks.json'
DECISION_LOG = BASE / 'reports/paper_decision_log.json'
TRACE_LOG    = BASE / 'reports/decision_trace_log.json'
PROVENANCE  = BASE / 'reports/data_provenance_summary.json'
WATCHLIST   = BASE / 'paper_trading/watchlist.json'
POSITIONS   = BASE / 'portfolio/unified_positions.json'
TRADE_LOG   = BASE / 'portfolio/trade_log.json'
RISK_REPORT = BASE / 'paper_trading/reports/risk_status_report.json'
SCHEMA_YAML = BASE / 'governance/decision_trace_schema.yaml'
FACTORS     = BASE / 'features/cache/daily_technical_factors.json'

# ── Phase-2.6D: 加载 Risk Price Validation Gate ─────────────────────
sys.path.insert(0, str(BASE / 'governance'))
from risk_price_validation import validate_risk_price_structure

TODAY = datetime.now().strftime('%Y-%m-%d')
NOW   = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
NOW_S = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def load_json(path, fallback=None):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return fallback if fallback is not None else {}


def calc_position(price, total_assets, avail_balance, max_pct=0.20):
    """计算建议仓位（最高20%）
    total_assets 为0时用 avail_balance 兜底（模拟账户参考可用资金）
    """
    if not price or price <= 0:
        return 0, 0, 0
    # 兜底：如果总资产为空，用可用资金
    ref_capital = total_assets if total_assets > 0 else (avail_balance if avail_balance > 0 else 0)
    if ref_capital == 0:
        return 0, 0, 0
    max_amount = ref_capital * max_pct
    shares = int(max_amount / price / 100) * 100  # 整手
    pct = (shares * price / ref_capital * 100)
    return shares, pct, max_amount


def get_buy_timing(action, rsi, change_pct):
    """判断买入时机"""
    if '低吸' in action or rsi < 30:
        return 'next_day_low_buy'
    elif '突破' in action:
        return 'intraday_buy'
    elif '观察' in action or '⚠️' in action:
        return 'watch_only'
    return 'watch_only'


def build_entry_zone(price, change_pct):
    """计算买入区间"""
    if not price or price <= 0:
        return None, None, None
    # 昨日收盘参考价
    ref = price / (1 + change_pct / 100) if change_pct else price
    zone_min = round(ref * 0.98, 2)   # -2% 低吸位
    zone_max = round(price * 1.005, 2)  # +0.5% 当日区间上限
    max_chase = round(price * 1.025, 2)  # 超过+2.5% 不追
    return zone_min, zone_max, max_chase


def get_agent_trace(decision_time, top_picks_ts):
    """构建完整经手链路"""
    return [
        {
            'agent': 'MAIN',
            'role': 'coordinator',
            'input_file': '-',
            'output_file': '-',
            'timestamp': decision_time,
            'status': 'completed',
            'note': '协调各Robot工作，不直接处理数据'
        },
        {
            'agent': 'OpenClaw',
            'role': 'data_fetch',
            'input_file': 'openclaw/data_output/',
            'output_file': 'openclaw/data_output/',
            'timestamp': top_picks_ts,
            'status': 'completed',
            'note': '采集K线/行情数据'
        },
        {
            'agent': 'robot_3',
            'role': 'factor_compute',
            'input_file': 'openclaw/data_output/',
            'output_file': 'features/cache/daily_technical_factors.json',
            'timestamp': top_picks_ts,
            'status': 'completed',
            'note': '计算RSI/MA5/MA20/量比等技术因子'
        },
        {
            'agent': 'robot_4',
            'role': 'mode_scan',
            'input_file': 'features/cache/daily_technical_factors.json',
            'output_file': 'mode_scan/output/',
            'timestamp': top_picks_ts,
            'status': 'completed',
            'note': '模式扫描：小阳启动/回踩止跌/2波启动/突破启动'
        },
        {
            'agent': 'action_engine',
            'role': 'ranking',
            'input_file': 'portfolio/candidate_rankings.json, mode_scan/output/, emotion_engine/',
            'output_file': 'reports/top_picks.json',
            'timestamp': top_picks_ts,
            'status': 'completed',
            'note': 'AI评分排序，生成Top Picks'
        },
        {
            'agent': 'paper_decision_engine',
            'role': 'decision',
            'input_file': 'reports/top_picks.json, portfolio/unified_positions.json, paper_trading/watchlist.json',
            'output_file': 'reports/paper_decision_log.json',
            'timestamp': decision_time,
            'status': 'completed',
            'note': '基于规则生成paper_buy/skip/hold/sell决策'
        },
        {
            'agent': 'paper_risk_controller',
            'role': 'risk_check',
            'input_file': 'reports/paper_decision_log.json',
            'output_file': 'paper_trading/reports/risk_status_report.json',
            'timestamp': decision_time,
            'status': 'completed',
            'note': '风控检查：单票仓位/总仓位/高开过滤'
        },
    ]


def process():
    print(f"=== Paper Decision Engine Phase-2.6C === {NOW_S}")

    top_picks_data = load_json(TOP_PICKS, None)
    if not top_picks_data:
        print("❌ top_picks.json 不存在，退出"); return

    picks = top_picks_data.get('top_picks', [])
    top_picks_ts = top_picks_data.get('generated_at', NOW)
    print(f"Top Picks: {len(picks)} 只")

    # 读取持仓
    unified = load_json(POSITIONS, {})
    capital = unified.get('capital', {})
    total_assets = capital.get('total_assets', 0)
    avail_balance = capital.get('avail_balance', 0)
    positions = unified.get('positions', [])
    holding_syms = {p.get('symbol') for p in positions}

    # 读取风控报告
    risk_data = load_json(RISK_REPORT, {})

    # 读取 trade_log（用于每日1笔限制）
    trade_log = load_json(TRADE_LOG, {'trades': []})
    today_trades = [t for t in trade_log.get('trades', [])
                    if t.get('trade_date') == TODAY and t.get('success') == True]
    today_buy_count = sum(1 for t in today_trades if t.get('action') == 'buy')
    today_buy_syms = {t.get('symbol') for t in today_trades if t.get('action') == 'buy'}

    print(f"持仓: {len(positions)} | 总资产: {total_assets:,.0f} | 可用: {avail_balance:,.0f}")
    print(f"今日已买入: {today_buy_count} 笔 → {today_buy_syms}")

    decisions = []
    trace_picks = []

    for p in picks:
        sym   = p.get('股票代码', '')
        name  = p.get('股票名称', '')
        price = p.get('价格') or p.get('last_price')
        chg   = p.get('涨跌幅', 0)
        rsi   = p.get('RSI', 50)
        ma5   = p.get('MA5') or p.get('ma5')
        ma20  = p.get('MA20') or p.get('ma20')
        vol_ratio = p.get('量比', p.get('volume_ratio', 1))
        action = p.get('操作建议', '观察')
        mode   = p.get('所属模式', '')
        score  = p.get('AI评分', 0)
        obs    = p.get('建议观察位', {})
        support = obs.get('支撑位', obs.get('support_price'))
        pressure = obs.get('压力位', obs.get('pressure_price'))
        reasons = p.get('入选原因', '')
        risks   = p.get('风险点', [])

        # Phase-2.7A: 市场结构字段（来自 market_structure_engine）
        structure_type = p.get('structure_type', 'unknown')
        structure_confidence = p.get('structure_confidence', 0.0)
        structure_source = p.get('structure_source', 'unknown')
        structure_version = p.get('structure_version', '2.7a')
        swing_low = p.get('swing_low', 0.0)
        swing_high = p.get('swing_high', 0.0)
        # structure invalid → 直接 paper_skip
        if structure_type == 'invalid':
            action = 'paper_skip'
            decision = 'paper_skip'
            reason = 'invalid_price_structure'

        # 买入区间
        zone_min, zone_max, max_chase = build_entry_zone(price, chg)

        # 止损位（支撑-3%）
        stop_loss = round(support * 0.97, 2) if support else None

        # 止盈观察位（压力位）
        take_profit_watch = pressure

        # 建议股数（最高20%仓位；total_assets为0时用avail_balance兜底）
        qty, pos_pct, pos_amt = calc_position(price, total_assets, avail_balance, 0.20)

        # 买入时机
        buy_timing = get_buy_timing(action, rsi, chg)

        # ── 决策逻辑 ────────────────────────────────────────────────
        skip_reason = ''
        decision = 'paper_skip'
        actual_action = 'skip'

        # 规则1：无价格 → await_price_confirm，不允许 paper_buy
        if not price or price <= 0:
            decision = 'await_price_confirm'
            actual_action = 'watch_only'
            skip_reason = f'价格为空（market_close），无法确认买入价，改为次日前置确认'
            print(f"  ⚠️ {name}: 无价格 → await_price_confirm")

        # 规则2：action=avoid → paper_skip
        elif 'avoid' in action.lower():
            skip_reason = f'系统标记为 avoid，禁止买入'

        # 规则3：今日已买入 → paper_skip
        elif sym in today_buy_syms:
            skip_reason = f'今日已买入该股，每日至多1笔'

        # 规则4：每日1笔上限
        elif today_buy_count >= 1:
            skip_reason = f'今日已决策买入{today_buy_syms}，每日至多1笔'
            # 如果该股本身高分且今日未买，仍标记 paper_skip 但注明原因

        # 规则5：已持有 → paper_skip
        elif sym in holding_syms:
            decision = 'paper_hold'
            actual_action = 'hold'
            skip_reason = '已持有，观察是否需要卖出'

        # 规则6：paper_trade_enabled=false → 全部 paper_skip
        elif not os.environ.get('PAPER_TRADING_ENABLED', 'true').lower() in ('true', '1'):
            skip_reason = 'PAPER_TRADING_ENABLED=false，模拟交易未开启'

        # 规则7：买入信号 + 满足条件 → paper_buy
        elif '低吸' in action and '⚠️' not in action:
            if score >= 75 and rsi < 75 and price and price > 0:
                if total_assets == 0 and avail_balance == 0:
                    # Phase-2.6C: 资金数据缺失 → await_capital_confirm，不允许 paper_buy
                    decision = 'await_capital_confirm'
                    actual_action = 'watch_only'
                    skip_reason = f'资金数据缺失（total_assets=0），需次日前置确认，建议仓位{qty}股参考'
                    print(f"  ⏳ {name}: await_capital_confirm（资金数据缺失）")
                elif pos_pct <= 20:
                    decision = 'paper_buy'
                    actual_action = 'buy'
                    skip_reason = ''
                    print(f"  ✅ {name}: paper_buy | qty={qty} | pos={pos_pct:.1f}%")
                else:
                    skip_reason = f'仓位{pos_pct:.1f}%>20%，超限'
                    print(f"  🚫 {name}: skip | {skip_reason}")

        # 规则8：突破/观察类 → watch_only
        elif '观察' in action or '突破' in action:
            decision = 'paper_skip'
            actual_action = 'watch_only'
            skip_reason = f'操作建议={action}，非明确买入信号'
            print(f"  🚫 {name}: watch_only | {skip_reason}")

        # 兜底
        else:
            skip_reason = f'不满足买入条件（评分={score}, RSI={rsi}, action={action}）'

        # ══ Phase-2.6D: Risk Price Validation Gate ══════════════════════
        # 在进入 paper_trade_executor 前，必须通过价格结构校验
        # 读取因子数据时间戳作为 data_as_of（统一时间基准）
        factor_ts = load_json(FACTORS, {}).get('timestamp', f"{TODAY} 15:00")
        risk_payload = {
            'symbol': sym,
            'name': name,
            'current_price': price,
            'support_price': support,
            'pressure_price': pressure,
            'stop_loss': stop_loss,
            'take_profit_watch': take_profit_watch,
            'entry_zone_min': zone_min,
            'entry_zone_max': zone_max,
            'data_as_of': factor_ts,
            'support_data_as_of': factor_ts,
            'pressure_data_as_of': factor_ts,
            'risk_data_as_of': factor_ts,
            # Phase-2.7A: 市场结构
            'structure_type': structure_type,
            'structure_confidence': structure_confidence,
        }
        rv = validate_risk_price_structure(risk_payload)
        # 如果校验失败 → 强制 paper_skip，禁止进入 paper_trade_executor
        if not rv['validation_passed']:
            decision = 'paper_skip'
            actual_action = 'skip'
            skip_reason = f"invalid_price_structure: {'; '.join(rv['errors'])}"
            print(f"  🛡️ {name}: 风险价格校验失败 → paper_skip | {skip_reason}")

        # ── 构建溯源数据 ────────────────────────────────────────────
        pick_trace = {
            'symbol': sym,
            'name': name,
            'timestamps': {
                'report_time': top_picks_ts,
                'decision_time': NOW,
                'market_time': f"{TODAY} 15:00",
                'data_as_of': f"{TODAY} 15:00",
            },
            'price_data': {
                'last_price': price,
                'change_pct': chg,
                'volume_ratio': vol_ratio,
                'rsi': rsi,
                'ma5': ma5,
                'ma20': ma20,
                'support_price': support,
                'pressure_price': pressure,
            },
            'decision': {
                'decision': decision,
                'action': actual_action,
                'buy_timing': buy_timing,
                'entry_zone_min': zone_min,
                'entry_zone_max': zone_max,
                'max_chase_price': max_chase,
                'stop_loss': stop_loss,
                'take_profit_watch': take_profit_watch,
                'position_size_pct': round(pos_pct, 2),
                'quantity': qty,
                'reason': reasons if decision == 'paper_buy' else '',
                'skip_reason': skip_reason,
                # Phase-2.6D: Risk Validation 结果
                'risk_validation_passed': rv['validation_passed'],
                'validation_reason': rv['reason'],
                'validation_errors': rv['errors'],
                'validation_warnings': rv['warnings'],
                'risk_data_as_of': rv['risk_data_as_of'],
                'corrected_values': rv['corrected_values'],
            },
            'data_sources': {
                'kline_source': {
                    'engine': 'OpenClaw',
                    'file': 'openclaw/data_output/',
                    'timestamp': top_picks_ts,
                },
                'price_source': {
                    'engine': 'OpenClaw',
                    'file': 'mx_data_output/',
                    'timestamp': top_picks_ts,
                },
                'factor_source': {
                    'engine': 'robot_3',
                    'file': 'features/cache/daily_technical_factors.json',
                    'timestamp': top_picks_ts,
                },
                'mode_scan_source': {
                    'engine': 'robot_4',
                    'file': 'mode_scan/output/',
                    'timestamp': top_picks_ts,
                },
                'ranking_source': {
                    'engine': 'action_engine',
                    'file': 'reports/top_picks.json',
                    'timestamp': top_picks_ts,
                },
                'risk_source': {
                    'engine': 'paper_risk_controller',
                    'file': 'paper_trading/reports/risk_status_report.json',
                    'timestamp': NOW,
                },
                'paper_decision_source': {
                    'engine': 'paper_decision_engine',
                    'file': 'reports/paper_decision_log.json',
                    'timestamp': NOW,
                },
            },
            'agent_trace': get_agent_trace(NOW, top_picks_ts) + ['risk_price_validation'],
        }

        trace_picks.append(pick_trace)

        # ── 写入 decision_log（兼容旧格式）──────────────────────────
        decisions.append({
            'date': TODAY,
            '股票代码': sym,
            '股票名称': name,
            'decision': decision,
            'action': actual_action,
            'buy_timing': buy_timing,
            'entry_zone_min': zone_min,
            'entry_zone_max': zone_max,
            'max_chase_price': max_chase,
            'stop_loss': stop_loss,
            'take_profit_watch': take_profit_watch,
            'position_size_pct': round(pos_pct, 2),
            'quantity': qty,
            'reason': reasons if decision == 'paper_buy' else skip_reason,
            'skip_reason': skip_reason,
            'AI评分': score,
            'RSI': rsi,
            '操作建议': action,
            '所属模式': mode,
            # Phase-2.7A: 市场结构字段
            'structure_type': structure_type,
            'structure_confidence': structure_confidence,
            'structure_source': structure_source,
            'structure_version': structure_version,
            'swing_low': swing_low,
            'swing_high': swing_high,
            # Phase-2.6D: risk_validation fields
            'risk_validation_passed': rv.get('validation_passed'),
            'validation_reason': rv.get('reason'),
            'validation_errors': rv.get('errors'),
            'validation_warnings': rv.get('warnings'),
            'risk_data_as_of': rv.get('risk_data_as_of', '?'),
            'corrected_values': rv.get('corrected_values', {}),
            'generated_at': NOW_S,
        })

    # ── 写入 decision_trace_log.json ──────────────────────────────
    trace_data = {
        'schema_version': '1.0',
        'phase': 'Phase-2.6C Decision Traceability',
        'generated_at': NOW,
        'date': TODAY,
        'paper_only': True,
        'real_trade_prohibited': True,
        'killswitch_check': True,
        'decisions': trace_picks,
    }
    with open(TRACE_LOG, 'w', encoding='utf-8') as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 溯源日志: {TRACE_LOG}")

    # ── 写入 data_provenance_summary.json ──────────────────────────
    buys = [d for d in decisions if d['decision'] == 'paper_buy']
    sells = [d for d in decisions if d['decision'] == 'paper_sell']
    skips = [d for d in decisions if d['decision'] in ('paper_skip', 'await_price_confirm', 'await_capital_confirm')]
    holds = [d for d in decisions if d['decision'] == 'paper_hold']
    await_cap = [d for d in decisions if d['decision'] == 'await_capital_confirm']

    prov = {
        'schema_version': '1.0',
        'phase': 'Phase-2.6C Data Provenance',
        'generated_at': NOW,
        'date': TODAY,
        'total_picks': len(decisions),
        'decision_summary': {
            'paper_buy': len(buys),
            'paper_sell': len(sells),
            'paper_skip': len(skips),
            'paper_hold': len(holds),
            'await_price_confirm': len([d for d in decisions if d['decision'] == 'await_price_confirm']),
        },
        'buy_candidates': [{'symbol': d['股票代码'], 'name': d['股票名称'],
                            'qty': d['quantity'], 'entry_zone': f"{d['entry_zone_min']}~{d['entry_zone_max']}",
                            'stop_loss': d['stop_loss'], 'buy_timing': d['buy_timing']} for d in buys],
        'skip_candidates': [{'symbol': d['股票代码'], 'name': d['股票名称'],
                             'skip_reason': d['skip_reason']} for d in skips],
        'data_sources_summary': {
            'kline': 'OpenClaw / openclaw/data_output/',
            'price': 'OpenClaw / mx_data_output/',
            'factors': 'robot_3 / features/cache/daily_technical_factors.json',
            'mode_scan': 'robot_4 / mode_scan/output/',
            'ranking': 'action_engine / reports/top_picks.json',
            'risk': 'paper_risk_controller / paper_trading/reports/risk_status_report.json',
            'decision': 'paper_decision_engine / reports/paper_decision_log.json',
        },
        'agent_chain': 'MAIN → OpenClaw → robot_3 → robot_4 → action_engine → paper_decision_engine → paper_risk_controller',
    }
    with open(PROVENANCE, 'w', encoding='utf-8') as f:
        json.dump(prov, f, ensure_ascii=False, indent=2)
    print(f"✅ 数据溯源: {PROVENANCE}")

    # ── 写入 decision_log.json（兼容旧格式）─────────────────────────
    log_data = {
        'schema_version': '2.7B',
        'phase': 'Phase-2.7B Paper Execution Bridge',
        'generated_at': NOW,
        'date': TODAY,
        'paper_only': True,
        'real_trade_prohibited': True,
        'killswitch_check': True,
        'decisions': decisions,
        # Phase-2.6D: top-level validation_results for health check
        'validation_results': [
            {
                'symbol': d['股票代码'],
                'name': d['股票名称'],
                'current_price': d.get('current_price') or d.get('last_price') or d.get('价格'),
                'is_valid': d.get('risk_validation_passed', d.get('validation_passed')),
                'errors': d.get('validation_errors', []),
                'warnings': d.get('validation_warnings', []),
            }
            for d in decisions
        ],
        'summary': {
            'total_picks': len(decisions),
            'paper_buy': len(buys),
            'paper_skip': len(skips),
            'paper_hold': len(holds),
            'paper_sell': len(sells),
            'await_capital_confirm': len(await_cap),
            'buy_symbols': [d['股票代码'] for d in buys],
            'sell_symbols': [d['股票代码'] for d in sells],
            'skip_symbols': [d['股票代码'] for d in skips],
        },
    }
    with open(DECISION_LOG, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 决策日志: {DECISION_LOG}")

    # Phase-2.7B: 注入 paper_order_intent
    sys.path.insert(0, str(BASE / 'execution_bridge'))
    from eastmoney_paper_bridge import run_bridge
    bridge_result = run_bridge()
    log_data['execution_summary'] = bridge_result.get('execution_summary', {})
    with open(DECISION_LOG, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    # ── 打印汇总 ────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"📗 买入: {len(buys)} 只 → {[d['股票名称'] for d in buys]}")
    print(f"📋 持有: {len(holds)} 只 → {[d['股票名称'] for d in holds]}")
    print(f"📕 卖出: {len(sells)} 只 → {[d['股票名称'] for d in sells]}")
    print(f"🚫 跳过: {len(skips)} 只 → {[d['股票名称'] for d in skips]}")
    if await_cap:
        print(f"⏳ 待确认: {len(await_cap)} 只 → {[d['股票名称'] for d in await_cap]}")
        for d in await_cap:
            print(f"   ⏳ {d['股票名称']} ({d['股票代码']}): {d['skip_reason']}")
    print(f"\n经手链路: MAIN → OpenClaw → robot_3 → robot_4 → action_engine → paper_decision_engine → paper_risk_controller")
    for d in buys:
        print(f"\n  📗 {d['股票名称']} ({d['股票代码']})")
        print(f"     买入区间: {d['entry_zone_min']}~{d['entry_zone_max']}")
        print(f"     止损位: {d['stop_loss']}")
        print(f"     数量: {d['quantity']}股 | 仓位: {d['position_size_pct']:.1f}%")
        print(f"     买入时机: {d['buy_timing']}")
        print(f"     原因: {d['reason']}")


if __name__ == '__main__':
    process()
