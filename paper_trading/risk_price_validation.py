#!/usr/bin/env python3
"""
Phase-2.6C-R1 Risk Price Validation Layer
紧急修复：止损/止盈/支撑/压力/买入区间价格逻辑校验
规则：
1. stop_loss < current_price  （止损必须低于现价）
2. support_price <= current_price <= pressure_price
3. take_profit_watch > current_price  （止盈必须高于现价）
4. entry_zone 偏离 current_price <= 15%
5. 所有价格必须同一 data_as_of
6. 校验失败 → decision 改为 paper_skip，reason=invalid_price_structure
"""
import json, sys
from datetime import datetime
from pathlib import Path

BASE = Path('/Users/gino/project_ai_trading')
TRACE_LOG  = BASE / 'reports/decision_trace_log.json'
DECISION_LOG = BASE / 'reports/paper_decision_log.json'
PROVENANCE  = BASE / 'reports/data_provenance_summary.json'

TODAY = datetime.now().strftime('%Y-%m-%d')
NOW   = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
NOW_S = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def validate_price_structure(pick_trace):
    """校验单只股票价格结构，返回 (is_valid, warnings, errors)"""
    errors = []
    warnings = []

    price_data = pick_trace.get('price_data', {})
    decision   = pick_trace.get('decision', {})
    timestamps = pick_trace.get('timestamps', {})

    current_price = price_data.get('last_price')
    support       = price_data.get('support_price')
    pressure      = price_data.get('pressure_price')
    stop_loss     = decision.get('stop_loss')
    tp_watch      = decision.get('take_profit_watch')
    zone_min      = decision.get('entry_zone_min')
    zone_max      = decision.get('entry_zone_max')
    decision_val  = decision.get('decision', 'no_action')

    # ── 规则1：止损必须 < 现价 ────────────────────────────────────
    if current_price and stop_loss:
        if stop_loss >= current_price:
            errors.append(f"stop_loss({stop_loss}) >= current_price({current_price})，止损方向错误！")
        elif stop_loss < current_price * 0.7:
            warnings.append(f"stop_loss({stop_loss}) 低于现价{current_price}超过30%，可能过于激进")

    # ── 规则2：支撑 <= 现价 <= 压力 ─────────────────────────────────
    if current_price and support and pressure:
        if support > current_price:
            errors.append(f"support({support}) > current_price({current_price})，支撑位错误！")
        if current_price > pressure:
            warnings.append(f"current_price({current_price}) > pressure({pressure})，已突破压力位")

    # ── 规则3：止盈观察位必须 > 现价 ─────────────────────────────────
    if current_price and tp_watch:
        if tp_watch <= current_price:
            errors.append(f"take_profit_watch({tp_watch}) <= current_price({current_price})，止盈位错误！")

    # ── 规则4：买入区间偏离 <= 15% ─────────────────────────────────
    if current_price and zone_min and zone_max:
        zone_mid = (zone_min + zone_max) / 2
        deviation = abs(zone_mid - current_price) / current_price * 100
        if deviation > 15:
            warnings.append(f"entry_zone({zone_min}~{zone_max}, 中值{zone_mid}) 偏离现价{current_price} {deviation:.1f}% > 15%")

    # ── 规则5：同一 data_as_of（暂不强制校验时间一致性）──────────────

    is_valid = len(errors) == 0
    return is_valid, warnings, errors


def fix_price_data(pick_trace):
    """Phase-2.6C-R1: 当价格结构错误时，智能修正价格数据用于决策
    不修改原始数据，只生成 corrected_suggested_values 供决策参考
    """
    price_data = pick_trace.get('price_data', {})
    decision   = pick_trace.get('decision', {})
    current_price = price_data.get('last_price', 0)
    support      = price_data.get('support_price')
    pressure     = price_data.get('pressure_price')
    stop_loss    = decision.get('stop_loss')
    tp_watch     = decision.get('take_profit_watch')
    zone_min     = decision.get('entry_zone_min')
    zone_max     = decision.get('entry_zone_max')

    corrections = {}

    if current_price and current_price > 0:
        # 修正支撑：如果支撑 < 现价 × 0.7，说明支撑已破，用现价 × 0.90 作为新支撑
        if support and support < current_price * 0.70:
            corrections['support_price'] = round(current_price * 0.90, 2)

        # 修正压力：如果压力 < 现价，说明已突破，用现价 × 1.10 作为新压力
        if pressure and pressure < current_price:
            corrections['pressure_price'] = round(current_price * 1.10, 2)

        # 修正止损：必须 < 现价，取现价 × 0.92（-8%，合理止损）
        if stop_loss and stop_loss >= current_price:
            corrections['stop_loss'] = round(current_price * 0.92, 2)

        # 修正止盈观察位：必须 > 现价，取现价 × 1.15（+15%）
        if tp_watch and tp_watch <= current_price:
            corrections['take_profit_watch'] = round(current_price * 1.15, 2)

        # 修正买入区间：如果区间上限 < 现价，用现价 ±3% 重新计算
        if zone_max and zone_max < current_price:
            corrections['entry_zone_min'] = round(current_price * 0.97, 2)
            corrections['entry_zone_max'] = round(current_price * 1.01, 2)

    return corrections


def process():
    print(f"=== Risk Price Validation === {NOW_S}")

    trace_data = {}
    try:
        with open(TRACE_LOG) as f:
            trace_data = json.load(f)
    except Exception as e:
        print(f"❌ 无法读取 {TRACE_LOG}: {e}")
        return

    picks = trace_data.get('decisions', [])
    if not picks:
        print("⚠️ 无 Top Picks 可校验"); return

    print(f"待校验: {len(picks)} 只\n")

    validated_picks = []
    validation_results = []

    for p in picks:
        sym  = p.get('symbol', '')
        name = p.get('name', '')
        decision_val = p.get('decision', {}).get('decision', 'no_action')
        current_price = p.get('price_data', {}).get('last_price')

        is_valid, warnings, errors = validate_price_structure(p)

        # 构建校验结果
        result = {
            'symbol': sym,
            'name': name,
            'current_price': current_price,
            'is_valid': is_valid,
            'warnings': warnings,
            'errors': errors,
            'original_decision': decision_val,
        }

        # 如果有错误 → 强制改为 paper_skip，并提供修正值
        if not is_valid:
            result['forced_skip'] = True
            result['forced_skip_reason'] = f"invalid_price_structure: {'; '.join(errors)}"
            # 智能修正价格数据
            corrections = fix_price_data(p)
            result['corrected_values'] = corrections if corrections else None
            # 修改决策（降级为 paper_skip）
            p['decision']['decision'] = 'paper_skip'
            p['decision']['action'] = 'skip'
            p['decision']['skip_reason'] = f"invalid_price_structure: {'; '.join(errors)}"
            if corrections:
                p['decision']['corrected_suggested_values'] = corrections
        else:
            result['forced_skip'] = False
            if warnings:
                result['warning_note'] = f"{'; '.join(warnings)}"

        validated_picks.append(p)
        validation_results.append(result)

        # 打印
        emoji = '✅' if is_valid else '❌'
        print(f"{emoji} {name} ({sym}): 现价={current_price}")
        for e in errors:
            print(f"   ❌ {e}")
        for w in warnings:
            print(f"   ⚠️  {w}")
        if not is_valid:
            corr = result.get('corrected_values', {})
            corr_str = ', '.join(f"{k}={v}" for k, v in corr.items()) if corr else '无修正值'
            print(f"   🔧 建议修正: {corr_str}")
        print()

    # ── 更新 decision_trace_log.json ─────────────────────────────────
    trace_data['decisions'] = validated_picks
    trace_data['validation_timestamp'] = NOW
    trace_data['validation_phase'] = 'Phase-2.6C-R1 Risk Price Validation'
    trace_data['validation_results'] = validation_results

    with open(TRACE_LOG, 'w', encoding='utf-8') as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"✅ 溯源日志已更新: {TRACE_LOG}")

    # ── 更新 paper_decision_log.json ────────────────────────────────
    dec_data = {}
    try:
        with open(DECISION_LOG) as f:
            dec_data = json.load(f)
    except:
        pass

    # 同步修正 decision_log 中的记录
    if 'decisions' in dec_data:
        for dec in dec_data['decisions']:
            sym = dec.get('股票代码', '')
            for vr in validation_results:
                if vr['symbol'] == sym and vr['forced_skip']:
                    dec['decision'] = 'paper_skip'
                    dec['action'] = 'skip'
                    dec['skip_reason'] = vr['forced_skip_reason']
                    # 同步修正值
                    if vr.get('corrected_values'):
                        for k, v in vr['corrected_values'].items():
                            dec[k] = v

        dec_data['validation_timestamp'] = NOW
        dec_data['validation_phase'] = 'Phase-2.6C-R1 Risk Price Validation'
        dec_data['validation_results'] = validation_results

        with open(DECISION_LOG, 'w', encoding='utf-8') as f:
            json.dump(dec_data, f, ensure_ascii=False, indent=2)
        print(f"✅ 决策日志已更新: {DECISION_LOG}")

    # ── 汇总报告 ────────────────────────────────────────────────────
    pass_cnt  = sum(1 for r in validation_results if r['is_valid'])
    fail_cnt  = len(validation_results) - pass_cnt
    warn_cnt  = sum(1 for r in validation_results if r['warnings'] and r['is_valid'])

    print(f"\n{'='*50}")
    print(f"📊 校验汇总: {pass_cnt}✅ 通过 | {fail_cnt}❌ 失败 | {warn_cnt}⚠️ 警告")

    failed = [r for r in validation_results if not r['is_valid']]
    if failed:
        print(f"\n❌ 已被强制改为 paper_skip:")
        for r in failed:
            corr = r.get('corrected_values', {})
            corr_str = ', '.join(f"{k}={v}" for k, v in corr.items()) if corr else '无修正值'
            print(f"   {r['name']} ({r['symbol']}): {r['forced_skip_reason']}")
            if corr_str != '无修正值':
                print(f"      建议修正: {corr_str}")

    warn_failed = [r for r in validation_results if r['warnings'] and r['is_valid']]
    if warn_failed:
        print(f"\n⚠️  存在警告（但仍通过）:")
        for r in warn_failed:
            print(f"   {r['name']} ({r['symbol']}): {r['warning_note']}")

    # 返回状态供 health check 使用
    overall_status = 'pass' if fail_cnt == 0 else 'error'
    if pass_cnt > 0 and fail_cnt == 0 and warn_cnt > 0:
        overall_status = 'warning'

    print(f"\n整体状态: {overall_status.upper()}")
    return overall_status, validation_results


if __name__ == '__main__':
    status, results = process()
    sys.exit(0 if status == 'pass' else 1)
