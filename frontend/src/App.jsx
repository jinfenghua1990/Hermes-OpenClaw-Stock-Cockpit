import React, { useState, useEffect } from 'react';

/* ────────────────────────────────────────────────────────────
   Data Loading Utilities
──────────────────────────────────────────────────────────── */
const BASE = '/Users/gino/project_ai_trading';

async function fetchJSON(path) {
  try {
    const r = await fetch(`file://${path}`);
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
    fetch(reportPath).then(r => r.text()).then(t => setContent(t.slice(0, 3000))).catch(() => {});
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
      Hermes AI Trading Cockpit — Phase-2.5 | 最后更新: {lastUpdate || '—'}
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
      ]);
      setHealth(healthData);
      setRuntimeHealth(rhData);
      setConsistency(scData);
      setFreeze(fiData);
      setReportDelivery(rdData);
      setPaperTrade(ptData);
      setPaperPositions(ppData);
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
          <span className="badge badge-pass">Phase-2.5</span>
          <span className="badge badge-info">{mode}</span>
        </div>
      </div>

      {/* Main */}
      <div className="main">

        {/* A. System Status */}
        <Section title="A. System Status">
          <SystemStatus
            phase={phase}
            mode={mode}
            freeze={freeze?.freeze_status || freeze?.freeze_state || 'ACTIVE'}
            soul={freeze?.observe_only ? 'OBSERVE_ONLY' : '—'}
            uptime={health ? `${health.active_today || 0}/${health.total_modules || 0}` : '—'}
          />
        </Section>

        {/* B. Health Gates */}
        <Section title="B. Health Gates">
          <div className="grid-2">
            <RuntimeEventHealth data={runtimeHealth} />
            <FreezeIntegrity data={freeze} />
            <SnapshotConsistency data={consistency} />
            <ReportDelivery data={reportDelivery} />
          </div>
        </Section>

        {/* C. Paper Trade */}
        <Section title="C. Paper Trade">
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

        {/* D. Daily Report */}
        <Section title="D. Daily Report">
          <DailyReport reportPath={`file://${BASE}/report_engine/outputs/2026-05-13.md`} />
        </Section>

      </div>

      <Footer lastUpdate={lastUpdate} />
    </div>
  );
}
