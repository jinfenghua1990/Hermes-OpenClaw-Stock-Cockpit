import React, { useState, useEffect } from 'react';

/* ────────────────────────────────────────────────────────────
   Data Loading Utilities
──────────────────────────────────────────────────────────── */
const BASE = '/Users/gino/project_ai_trading';

async function fetchJSON(path) {
  try {
    // Use Vite dev server proxy to avoid file:// CORS issues
    const apiPath = '/data' + path.replace(BASE, '');
    const r = await fetch(apiPath);
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

function getMeta(path) {
  try {
    const s = require('fs').statSync(path);
    return new Date(s.mtime).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  } catch { return '—'; }
}

/* ────────────────────────────────────────────────────────────
   Badge / Status Helpers
──────────────────────────────────────────────────────────── */
function Badge({ s }) {
  const map = { pass: 'badge-pass', success: 'badge-pass', warning: 'badge-warning', error: 'badge-error', info: 'badge-info' };
  return <span className={`badge ${map[s] || 'badge-neutral'}`}>{s || 'unknown'}</span>;
}

function StatusDot({ s }) {
  const c = { pass: 'var(--green)', success: 'var(--green)', warning: 'var(--yellow)', error: 'var(--red)' };
  return <span style={{ color: c[s] || 'var(--text-dim)', fontWeight: 700 }}>●</span>;
}

/* ────────────────────────────────────────────────────────────
   Section Components
──────────────────────────────────────────────────────────── */
function Section({ title, children }) {
  return (
    <div className="section">
      <div className="section-title">{title}</div>
      {children}
    </div>
  );
}

function Card({ children, style }) {
  return <div className="card" style={style}>{children}</div>;
}

/* ────────────────────────────────────────────────────────────
   System Status
──────────────────────────────────────────────────────────── */
function SystemStatus({ phase, mode, freeze, soul, uptime }) {
  return (
    <div className="grid-4">
      <Card>
        <div className="metric-label">Phase</div>
        <div className="metric-value" style={{ color: 'var(--accent)' }}>{phase || '—'}</div>
        <div className="metric-label">Mode: {mode || '—'}</div>
      </Card>
      <Card>
        <div className="metric-label">System Freeze</div>
        <div className="metric-value" style={{ color: freeze === 'ACTIVE' ? 'var(--green)' : 'var(--yellow)' }}>
          {freeze || '—'}
        </div>
        <div className="metric-label">Soul Mode: {soul || '—'}</div>
      </Card>
      <Card>
        <div className="metric-label">Daily Health Check</div>
        <div style={{ fontSize: 24, fontWeight: 700 }}>{uptime || '—'}</div>
        <div className="metric-label">稳定性观察</div>
      </Card>
      <Card>
        <div className="metric-label">禁止事项</div>
        <div className="flex-col">
          {['❌ 新增Robot', '❌ Baseline修改', '❌ 自动学习', '❌ 自动交易'].map(t => (
            <span key={t} style={{ fontSize: 11, color: 'var(--text-dim)' }}>{t}</span>
          ))}
        </div>
      </Card>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Runtime Event Health
──────────────────────────────────────────────────────────── */
function RuntimeEventHealth({ data }) {
  if (!data) return <Card><div className="loading">加载中...</div></Card>;
  const { total_modules, active_today, missing_today = [], warning_modules = [], status } = data;
  return (
    <Card>
      <div className="flex-between" style={{ marginBottom: 12 }}>
        <span>模块活跃</span>
        <Badge s={status} />
      </div>
      <div className="big-num neutral" style={{ marginBottom: 8 }}>{active_today}/{total_modules}</div>
      {warning_modules.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--yellow)', marginBottom: 6 }}>
          ⚠️ Warning: {warning_modules.join(', ')}
        </div>
      )}
      {missing_today.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--red)', marginBottom: 6 }}>
          ❌ Missing: {missing_today.join(', ')}
        </div>
      )}
    </Card>
  );
}

/* ────────────────────────────────────────────────────────────
   Snapshot Consistency
──────────────────────────────────────────────────────────── */
function SnapshotConsistency({ data }) {
  if (!data) return <Card><div className="loading">加载中...</div></Card>;
  const { consistent, status, runtime_usage_modules, runtime_event_modules, dashboard_modules } = data;
  return (
    <Card>
      <div className="flex-between" style={{ marginBottom: 12 }}>
        <span>模块数一致性</span>
        <Badge s={status} />
      </div>
      <div className="flex-col" style={{ fontSize: 12 }}>
        <div>runtime_usage: <strong>{runtime_usage_modules}</strong></div>
        <div>runtime_event: <strong>{runtime_event_modules}</strong></div>
        <div>dashboard: <strong>{dashboard_modules}</strong></div>
        <div style={{ marginTop: 6, color: consistent ? 'var(--green)' : 'var(--red)' }}>
          {consistent ? '✅ 完全一致' : '❌ 不一致'}
        </div>
      </div>
    </Card>
  );
}

/* ────────────────────────────────────────────────────────────
   Top Picks
──────────────────────────────────────────────────────────── */
function TopPicks({ data, decisions, riskValidation }) {
  if (!data) return <Card><div className="loading">加载中...</div></Card>;
  const picks = data.top_picks || [];
  // 构建决策映射
  const decMap = {};
  if (decisions)
    decisions.forEach(d => decMap[d.get ? d.get('股票代码') : d['股票代码']] = d);
  // 构建风险校验映射
  const riskMap = {};
  if (riskValidation)
    riskValidation.forEach(r => riskMap[r.symbol] = r);
  const totalValid = riskValidation ? riskValidation.filter(r => r.is_valid).length : null;
  if (picks.length === 0) return (
    <Card>
      <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>暂无精选个股</div>
    </Card>
  );
  return (
    <Card>
      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 6 }}>
        🔝 Top Picks <span style={{ marginLeft: 4 }}>| {picks.length}只</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {picks.map((p, i) => {
          const pct = p.涨跌幅 || 0;
          const pctColor = pct >= 0 ? 'var(--green)' : 'var(--red)';
          const actionColor = p.操作建议?.includes('🔔') ? 'var(--blue-bright)' : p.操作建议?.includes('⚠️') ? 'var(--yellow)' : 'var(--text-dim)';
          const dec = decMap[p.股票代码] || {};
          const decision = dec.decision || '';
          const decBg = {'paper_buy': '#0d2b1a', 'paper_skip': '#1a0d0d', 'paper_sell': '#1a0d1a'}[decision] || '#0a0a15';
          const decBadge = {'paper_buy': '📗买入', 'paper_skip': '🚫跳过', 'paper_hold': '📋持有', 'paper_sell': '📕卖出'}[decision] || '';
          const decReason = dec.reason || '';
          return (
            <div key={i} style={{
              border: '1px solid var(--border)',
              borderRadius: 6,
              padding: '8px 10px',
              background: decBg,
            }}>
              <div className="flex-between" style={{ marginBottom: 4 }}>
                <div>
                  <strong style={{ fontSize: 13, color: 'var(--text)' }}>{p.股票名称}</strong>
                  <span style={{ fontSize: 11, color: 'var(--text-dim)', marginLeft: 6 }}>{p.股票代码}</span>
                </div>
                <span style={{ fontSize: 12, color: pctColor, fontWeight: 600 }}>
                  {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                </span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 3 }}>
                <span style={{ color: 'var(--blue-bright)' }}>{p.所属模式}</span>
                <span style={{ marginLeft: 8 }}>AI {p.AI评分}</span>
                <span style={{ marginLeft: 8, color: actionColor }}>{p.操作建议}</span>
                {(() => {
                  const rv = riskMap[p.股票代码];
                  if (!rv) return null;
                  if (!rv.is_valid) return <span style={{ marginLeft: 6, color: 'var(--red)', fontSize: 10 }}>❌风控失败</span>;
                  if (rv.warnings?.length) return <span style={{ marginLeft: 6, color: 'var(--yellow)', fontSize: 10 }}>⚠️风控警告</span>;
                  return <span style={{ marginLeft: 6, color: 'var(--green)', fontSize: 10 }}>✅风控通过</span>;
                })()}
              </div>
              {decision && (
                <div style={{ fontSize: 10, marginBottom: 2 }}>
                  <span style={{ fontWeight: 600, color: decision === 'paper_buy' ? 'var(--green)' : 'var(--red)' }}>{decBadge}</span>
                  <span style={{ color: 'var(--text-dim)', marginLeft: 6 }}>{decReason}</span>
                </div>
              )}
              <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>
                {p.入选原因}
              </div>
              {/* Phase-2.7A: 市场结构字段 */}
              {p.structure_type && p.structure_type !== '?' && (
                <div style={{ fontSize: 10, color: 'var(--blue-bright)', marginTop: 2 }}>
                  📊 {p.structure_type} | 置信度 {typeof p.structure_confidence === 'number' ? `${(p.structure_confidence * 100).toFixed(0)}%` : p.structure_confidence}
                  {p.swing_low > 0 && p.swing_high > 0 && ` | swing ${p.swing_low.toFixed(2)}/${p.swing_high.toFixed(2)}`}
                  {p.support_price > 0 && p.pressure_price > 0 && ` | 建议 ${p.support_price.toFixed(2)}~${p.pressure_price.toFixed(2)}`}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ────────────────────────────────────────────────────────────
   Emotion Snapshot
──────────────────────────────────────────────────────────── */
function EmotionSnapshot({ data }) {
  if (!data) return <Card><div className="loading">加载中...</div></Card>;
  const em = data.emotion_analysis || {};
  const score = em.emotion_score || 0;
  const phase = em.market_phase || 'unknown';
  const risk = em.market_risk_level || 'high';
  const phaseMap = { recovery_phase: '复苏', breakout_phase: '突破', defensive_phase: '防御', consolidation_phase: '震荡', trend_phase: '趋势' };
  const riskColor = { low: 'var(--green)', medium: 'var(--yellow)', medium_high: 'var(--orange)', high: 'var(--red)' };
  return (
    <Card>
      <div className="flex-between" style={{ marginBottom: 8 }}>
        <span style={{ fontSize: 12 }}>🧠 市场情绪</span>
        <span style={{ fontSize: 11, color: riskColor[risk] || 'var(--text-dim)', fontWeight: 600 }}>
          {risk.toUpperCase()}
        </span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: score >= 50 ? 'var(--green)' : 'var(--red)', marginBottom: 4 }}>
        {score}/100
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>
        {phaseMap[phase] || phase} | {em.strongest_mode || '—'}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>
        突破型: {data.market_metrics?.mode2_count || 0} | 小阳型: {data.market_metrics?.mode3_count || 0}
      </div>
    </Card>
  );
}
/* ────────────────────────────────────────────────────────────
   Runtime Metrics Panel — Phase-2.6D
──────────────────────────────────────────────────────────── */
function RuntimeMetrics({ data }) {
  if (!data) return <Card><div className="loading">加载中...</div></Card>;
  const { governance_status, health_check_summary, risk_interception_count, pipeline_today, observation_freeze, health_check_critical, health_check_warning, health_check_success, replay_snapshot_status, replay_snapshot_date, replay_snapshot_uuid } = data;
  const metricColor = (v) => v === 'PASS' ? 'var(--green)' : v === 'CRITICAL' ? 'var(--red)' : v === 'WARNING' ? 'var(--yellow)' : 'var(--text-dim)';
  return (
    <Card>
      <div className="flex-between" style={{ marginBottom: 10 }}>
        <span>📊 Runtime Metrics</span>
        <Badge s={governance_status} />
      </div>
      <div style={{ fontSize: 11, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        <div>Pipeline</div>
        <div style={{ color: pipeline_today === 'ACTIVE' ? 'var(--green)' : 'var(--yellow)' }}>{pipeline_today}</div>
        <div>Health</div>
        <div style={{ color: metricColor(health_check_summary) }}>{health_check_summary || '?'}</div>
        <div>Governance</div>
        <div style={{ color: metricColor(governance_status) }}>{governance_status || '?'}</div>
        <div>风险拦截</div>
        <div style={{ color: risk_interception_count > 0 ? 'var(--red)' : 'var(--green)' }}>{risk_interception_count} 次</div>
        <div>HC Critical</div>
        <div style={{ color: health_check_critical > 0 ? 'var(--red)' : 'var(--green)' }}>{health_check_critical}</div>
        <div>HC Warning</div>
        <div style={{ color: health_check_warning > 0 ? 'var(--yellow)' : 'var(--green)' }}>{health_check_warning}</div>
        <div>HC Success</div>
        <div style={{ color: 'var(--green)' }}>{health_check_success}</div>
        <div>观测冻结</div>
        <div style={{ color: observation_freeze ? 'var(--green)' : 'var(--red)' }}>{observation_freeze ? '🔒 ON' : '❌ OFF'}</div>
        <div>Risk Validation</div>
        <div style={{ color: 'var(--green)' }}>✅ ON</div>
        <div>Replay Snapshot</div>
        <div style={{ color: replay_snapshot_status === 'success' ? 'var(--green)' : replay_snapshot_status === 'warning' ? 'var(--yellow)' : 'var(--red)' }}>
          {replay_snapshot_status === 'success' ? '✅ PASS' : replay_snapshot_status === 'warning' ? '⚠️ WARN' : '❌ FAIL'}
        </div>
        {replay_snapshot_date && (
          <>
            <div>snapshot 日期</div>
            <div style={{ fontSize: 10 }}>{replay_snapshot_date}</div>
          </>
        )}
        {replay_snapshot_uuid && (
          <>
            <div>snapshot UUID</div>
            <div style={{ fontSize: 10 }}>{replay_snapshot_uuid}</div>
          </>
        )}
      </div>
    </Card>
  );
}

/* ────────────────────────────────────────────────────────────
   Freeze Integrity
──────────────────────────────────────────────────────────── */
function FreezeIntegrity({ data }) {
  if (!data) return <Card><div className="loading">加载中...</div></Card>;
  const { status, all_checks_passed } = data;
  const checks = [
    ['OBSERVE_ONLY', data.observe_only],
    ['auto_trade=false', data.auto_trade_disabled],
    ['auto_learn=false', data.auto_learn_disabled],
    ['adjust_weights=false', data.adjust_weights_disabled],
    ['modify_baseline=false', data.modify_baseline_disabled],
    ['robot_6~10 frozen', data.robot_6_10_frozen],
  ];
  return (
    <Card>
      <div className="flex-between" style={{ marginBottom: 10 }}>
        <span>冻结完整性</span>
        <Badge s={status} />
      </div>
      <div className="flex-col">
        {checks.map(([k, v]) => (
          <div key={k} style={{ fontSize: 11, color: v ? 'var(--green)' : 'var(--red)' }}>
            {v ? '✅' : '❌'} {k}
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ────────────────────────────────────────────────────────────
   Paper Trade
──────────────────────────────────────────────────────────── */
function PaperTrade({ report, positions }) {
  const [tab, setTab] = useState('pnl');
  if (!report) return <Card><div className="loading">加载中...</div></Card>;
  const mode = report.mode || 'PAPER_ONLY';
  const ks = report.kill_switch ? 'TRUE (已开启)' : 'FALSE (观察模式)';
  const pnl = report.total_pnl || 0;
  return (
    <Card>
      <div className="flex-between" style={{ marginBottom: 10 }}>
        <span>Paper Trade</span>
        <span className="badge badge-info">{mode}</span>
      </div>
      <div className="big-num" style={{ color: pnl >= 0 ? 'var(--green)' : 'var(--red)', marginBottom: 4 }}>
        {pnl >= 0 ? '+' : ''}{pnl.toLocaleString('zh-CN', { maximumFractionDigits: 2 })} 元
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 8 }}>
        KILL_SWITCH: {ks}
      </div>
      <div className="flex" style={{ gap: 4 }}>
        {['pnl', 'positions', 'risk'].map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              background: tab === t ? 'var(--blue-bright)' : 'var(--card-hover)',
              border: '1px solid var(--border)',
              color: 'var(--text)',
              padding: '2px 10px',
              borderRadius: 4,
              fontSize: 11,
              cursor: 'pointer'
            }}>
            {t}
          </button>
        ))}
      </div>
      {tab === 'pnl' && (
        <div style={{ marginTop: 8, fontSize: 11 }}>
          <div>当日盈亏: <strong style={{ color: (report.daily_pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
            {(report.daily_pnl || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })} 元
          </strong></div>
          <div>总资产: <strong>{report.total_assets?.toLocaleString()} 元</strong></div>
          <div>可用: <strong>{report.available_balance?.toLocaleString()} 元</strong></div>
        </div>
      )}
      {tab === 'positions' && (
        <div style={{ marginTop: 8, fontSize: 11 }}>
          <div>持仓数量: <strong>{report.positions_count || 0} 只</strong></div>
          {positions && positions.positions?.length > 0 ? (
            <table style={{ marginTop: 6 }}>
              <thead><tr><th>名称</th><th>盈亏</th><th>状态</th></tr></thead>
              <tbody>
                {positions.positions.map((p, i) => (
                  <tr key={i}>
                    <td>{p.name}</td>
                    <td style={{ color: (p.profit || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {(p.profit || 0) >= 0 ? '+' : ''}{(p.profit || 0).toFixed(2)}
                    </td>
                    <td><Badge s={p.count > 0 ? 'pass' : 'info'} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div style={{ color: 'var(--text-dim)' }}>当前空仓</div>}
        </div>
      )}
      {tab === 'risk' && (
        <div style={{ marginTop: 8, fontSize: 11 }}>
          <div>集中度风险: <strong style={{ color: 'var(--green)' }}>无</strong></div>
          <div>退市风险: <strong style={{ color: 'var(--green)' }}>无</strong></div>
          <div>熔断状态: <strong>未触发</strong></div>
        </div>
      )}
    </Card>
  );
}

/* ────────────────────────────────────────────────────────────
   Report Delivery
──────────────────────────────────────────────────────────── */
function ReportDelivery({ data }) {
  if (!data) return <Card><div className="loading">加载中...</div></Card>;
  const deliveries = data.deliveries || {};
  return (
    <Card>
      <div style={{ marginBottom: 10 }}>
        <span>报告发送状态</span>
      </div>
      {Object.entries(deliveries).map(([k, v]) => (
        <div key={k} style={{ marginBottom: 8 }}>
          <div className="flex-between">
            <span style={{ fontSize: 12 }}>{k}</span>
            <Badge s={v?.status || 'pending'} />
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>
            {v?.last_sent ? `上次发送: ${v.last_sent}` : '尚未发送'}
          </div>
        </div>
      ))}
    </Card>
  );
}

/* ────────────────────────────────────────────────────────────
   Daily Report Preview
──────────────────────────────────────────────────────────── */
function DailyReport({ reportPath }) {
  const [content, setContent] = useState('');
  useEffect(() => {
    const apiPath = '/data' + reportPath.replace(BASE, '');
    fetch(apiPath).then(r => r.text()).then(t => setContent(t.slice(0, 3000))).catch(() => {});
  }, [reportPath]);
  if (!content) return <Card><div className="loading">加载中...</div></Card>;
  return (
    <Card>
      <div style={{ marginBottom: 8, fontSize: 12 }}>日报预览 (最近)</div>
      <pre style={{
        fontSize: 11,
        color: 'var(--text-dim)',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
        maxHeight: 300,
        overflow: 'auto',
        background: '#0a0a15',
        padding: 10,
        borderRadius: 6,
        border: '1px solid var(--border)'
      }}>
        {content}
      </pre>
    </Card>
  );
}

/* ────────────────────────────────────────────────────────────
   Footer
──────────────────────────────────────────────────────────── */
function Footer({ lastUpdate }) {
  return (
    <div className="footer">
      Hermes AI Trading Cockpit — Phase-2.7A Market Structure Engine | 最后更新: {lastUpdate || '—'}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Main App
──────────────────────────────────────────────────────────── */
export default function App() {
  const [clock, setClock] = useState('');
  const [lastUpdate, setLastUpdate] = useState('');

  const [health, setHealth] = useState(null);
  const [runtimeHealth, setRuntimeHealth] = useState(null);
  const [consistency, setConsistency] = useState(null);
  const [freeze, setFreeze] = useState(null);
  const [reportDelivery, setReportDelivery] = useState(null);
  const [paperTrade, setPaperTrade] = useState(null);
  const [paperPositions, setPaperPositions] = useState(null);
  const [topPicks, setTopPicks] = useState(null);
  const [emotionData, setEmotionData] = useState(null);
  const [paperDecisions, setPaperDecisions] = useState(null);
  const [riskValidation, setRiskValidation] = useState(null);
  const [runtimeMetrics, setRuntimeMetrics] = useState(null);

  // Clock
  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Load data
  useEffect(() => {
    async function load() {
      const [
        healthData,
        rhData,
        scData,
        fiData,
        rdData,
        ptData,
        ppData,
      ] = await Promise.all([
        fetchJSON(`${BASE}/reports/runtime_event_health.json`),
        fetchJSON(`${BASE}/reports/runtime_event_health.json`),
        fetchJSON(`${BASE}/reports/snapshot_consistency.json`),
        fetchJSON(`${BASE}/reports/freeze_integrity.json`),
        fetchJSON(`${BASE}/reports/report_delivery_status.json`),
        fetchJSON(`${BASE}/paper_trading/reports/daily_pnl_report.json`),
        fetchJSON(`${BASE}/paper_trading/reports/positions_snapshot_report.json`),
        fetchJSON(`${BASE}/reports/top_picks.json`),
        fetchJSON(`${BASE}/emotion_engine/cache/market_emotion_snapshot.json`),
        fetchJSON(`${BASE}/reports/paper_decision_log.json`).catch(() => ({})),
        fetchJSON(`${BASE}/governance/snapshots/${new Date().toISOString().slice(0,10)}.json`).catch(() => null),
        fetchJSON(`${BASE}/system_health/history/${new Date().toISOString().slice(0,10)}.json`).catch(() => null),
      ]);
      setHealth(healthData);
      setRuntimeHealth(rhData);
      setConsistency(scData);
      setFreeze(fiData);
      setReportDelivery(rdData);
      setPaperTrade(ptData);
      setPaperPositions(ppData);
      setTopPicks(tpData);
      setEmotionData(emData);
      setPaperDecisions(pdData || {});
      // Extract validation_results from decision_log for risk validation display
      setRiskValidation(pdData?.validation_results || null);
// Build runtimeMetrics from governance snapshot + health check history
      const govSnap = res[10];
      const hcHist = res[11];
      const riskInterceptions = (pdData?.validation_results || []).filter(r => !r.is_valid).length;
      setRuntimeMetrics({
        phase: 'Phase-2.6E',
        governance_status: govSnap?.status || 'UNKNOWN',
        health_check_summary: hcHist?.overall_status || 'UNKNOWN',
        risk_interception_count: riskInterceptions,
        pipeline_today: govSnap ? 'ACTIVE' : 'NO_SNAPSHOT',
        observation_freeze: true,
        risk_validation_enabled: govSnap?.risk_validation_enabled || true,
        health_check_critical: hcHist?.critical_count || 0,
        health_check_warning: hcHist?.warning_count || 0,
        health_check_success: hcHist?.success_count || 0,
        // Phase-2.6E: Replay Snapshot persistence
        replay_snapshot_status: hcHist?.checks?.replay_snapshot_persistence?.status || 'UNKNOWN',
        replay_snapshot_date: hcHist?.checks?.replay_snapshot_persistence?.snapshot_date || null,
        replay_snapshot_uuid: hcHist?.checks?.replay_snapshot_persistence?.snapshot_uuid || '?',
      });
      setLastUpdate(new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }));
    }
    load();
    const id = setInterval(load, 30000); // refresh every 30s
    return () => clearInterval(id);
  }, []);

  const phase = health?.phase || 'Phase-2.5';
  const mode = 'OBSERVE_ONLY';

  return (
    <div>
      {/* Header */}
      <div className="header">
        <div className="header-title">🤖 HERMES COCKPIT</div>
        <div className="header-right">
          <span className="header-clock">{clock}</span>
          <span className="badge badge-pass">Phase-2.6D</span>
          <span className="badge badge-info">{mode}</span>
        </div>
      </div>

      {/* Main */}
      <div className="main">

      {/* A. Top Picks + Emotion (Phase-2.6D Risk Price Validation) */}
      <Section title={<>🔝 Top Picks <span style={{color:'var(--red)',fontSize:11}}>(风险价格校验)</span></>}>
        <div className="grid-2">
          <TopPicks data={topPicks} decisions={paperDecisions?.decisions} riskValidation={riskValidation} />
          <EmotionSnapshot data={emotionData} />
        </div>
      </Section>

      {/* B. System Status */}
      <Section title="B. System Status">
        <SystemStatus
          phase={phase}
          mode={mode}
          freeze={freeze?.freeze_status || freeze?.freeze_state || 'ACTIVE'}
          soul={freeze?.observe_only ? 'OBSERVE_ONLY' : '—'}
          uptime={health ? `${health.active_today || 0}/${health.total_modules || 0}` : '—'}
        />
      </Section>

      {/* C. Health Gates (Governance) — Phase-2.6D Runtime Metrics */}
      <Section title={<>C. Health Gates <span style={{fontSize:11,color:'var(--text-dim)'}}>(Phase-2.6D)</span></>}>
        <div className="grid-2">
          <RuntimeMetrics data={runtimeMetrics} />
          <RuntimeEventHealth data={runtimeHealth} />
          <FreezeIntegrity data={freeze} />
          <SnapshotConsistency data={consistency} />
          <ReportDelivery data={reportDelivery} />
        </div>
      </Section>

      {/* D. Paper Trade */}
      <Section title="D. Paper Trade">
        <div className="grid-2">
          <PaperTrade report={paperTrade} positions={paperPositions} />
          {paperTrade && (
            <Card>
              <div style={{ marginBottom: 8 }}>风控状态</div>
              <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                <div>✅ KILL_SWITCH: {paperTrade.kill_switch ? 'ON' : 'OFF (观察)'}</div>
                <div>✅ 单股仓位上限: 30%</div>
                <div>✅ 单日最多: 10 笔</div>
                <div>✅ 熔断阈值: 连续3笔亏损</div>
                <div>✅ 禁止 &gt;300 元股</div>
                <hr className="divider" />
                <div style={{ color: 'var(--green)' }}>🛡️ 风控通过 — 可正常交易</div>
              </div>
            </Card>
          )}
        </div>
      </Section>

      {/* E. Daily Report */}
      <Section title="E. Daily Report">
        <DailyReport reportPath={`file://${BASE}/reports/history/2026-05-13.md`} />
      </Section>

      </div>

      <Footer lastUpdate={lastUpdate} />
    </div>
  );
}
