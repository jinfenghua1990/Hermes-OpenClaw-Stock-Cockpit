import React, { useEffect, useMemo, useState } from 'react';
import GovernanceScalabilityPanel from './components/GovernanceScalabilityPanel.jsx';

const BASE = '/Users/gino/project_ai_trading';

async function fetchJSON(path, fallback = null) {
  try {
    const apiPath = '/data' + path.replace(BASE, '');
    const r = await fetch(apiPath);
    if (!r.ok) return fallback;
    return await r.json();
  } catch {
    return fallback;
  }
}

function Card({ title, children }) {
  return (
    <div className="card">
      {title && <div style={{ fontWeight: 700, marginBottom: 10 }}>{title}</div>}
      {children}
    </div>
  );
}

function Badge({ value }) {
  const v = String(value || 'UNKNOWN').toLowerCase();
  const color = v.includes('success') || v.includes('pass') || v.includes('active') || v.includes('paper')
    ? 'var(--green)'
    : v.includes('warning') || v.includes('pending')
      ? 'var(--yellow)'
      : v.includes('critical') || v.includes('fail') || v.includes('error')
        ? 'var(--red)'
        : 'var(--text-dim)';
  return <span style={{ color, fontWeight: 700 }}>{value || 'UNKNOWN'}</span>;
}

function Metric({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12, marginBottom: 6 }}>
      <span style={{ color: 'var(--text-dim)' }}>{label}</span>
      <span>{value}</span>
    </div>
  );
}

function TopPicks({ topPicks, decisionLog }) {
  const picks = topPicks?.top_picks || [];
  const decisions = decisionLog?.decisions || [];
  const decMap = Object.fromEntries(decisions.map(d => [d['股票代码'] || d.symbol, d]));

  if (!picks.length) return <Card title="Top Picks">暂无精选个股</Card>;

  return (
    <Card title={`Top Picks (${picks.length})`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {picks.map((p, i) => {
          const code = p['股票代码'] || p.symbol || `#${i}`;
          const dec = decMap[code] || {};
          return (
            <div key={code} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong>{p['股票名称'] || p.name || '未知股票'}</strong>
                <span style={{ color: 'var(--text-dim)' }}>{code}</span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4 }}>
                模式：{p['所属模式'] || p.mode || '—'} | AI：{p['AI评分'] || p.ai_score || '—'}
              </div>
              <div style={{ fontSize: 11, marginTop: 4 }}>
                Decision: <Badge value={dec.decision || 'NO_DECISION'} />
                {dec.execution_status && <span> | Execution: <Badge value={dec.execution_status} /></span>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--blue-bright)', marginTop: 4 }}>
                Structure: {p.structure_type || dec.structure_type || 'unknown'} | Confidence: {p.structure_confidence ?? dec.structure_confidence ?? '—'}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export default function App2_7D() {
  const [clock, setClock] = useState('');
  const [health, setHealth] = useState(null);
  const [topPicks, setTopPicks] = useState(null);
  const [decisionLog, setDecisionLog] = useState(null);
  const [replay, setReplay] = useState(null);
  const [phase27d, setPhase27d] = useState(null);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Taipei' }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    async function load() {
      const [hc, tp, pd, rp, g27d] = await Promise.all([
        fetchJSON(`${BASE}/system_health/history/${today}.json`, {}),
        fetchJSON(`${BASE}/reports/top_picks.json`, {}),
        fetchJSON(`${BASE}/reports/paper_decision_log.json`, {}),
        fetchJSON(`${BASE}/replay_engine/snapshots/${today}.json`, {}),
        fetchJSON(`${BASE}/system_health/phase_2_7d_status.json`, {}),
      ]);
      setHealth(hc);
      setTopPicks(tp);
      setDecisionLog(pd);
      setReplay(rp);
      setPhase27d(g27d);
    }
    load();
  }, [today]);

  const executionSummary = replay?.execution_summary || replay?.auto_execution_summary || {};
  const ms = replay?.market_structure_summary || {};
  const risk = replay?.risk_validation_summary || {};
  const ext = replay?.phase_2_7d_extension || {};

  const governancePanelData = {
    shadow_strategy_count: ext?.strategy_registry_ref?.shadow_strategy_count || 0,
    arbitration_enabled: Boolean(ext?.arbitration_result?.enabled),
    conflict_count: replay?.agent_conflict_count || 0,
    reconciliation_status: ext?.execution_reconciliation?.status || phase27d?.checks?.execution_reconciliation_health?.status || 'UNKNOWN',
    baseline_drift_detected: Boolean(ext?.baseline_drift_detected),
    replay_split_snapshot_ready: Boolean(ext?.split_snapshot_ready),
    version: ext?.phase || 'Phase-2.7D'
  };

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Hermes AI Research Governance Cockpit</h1>
          <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>Phase-2.7D Governance Scalability | {clock}</div>
        </div>
      </header>

      <div className="grid-4">
        <Card title="System">
          <Metric label="SOUL_MODE" value={<Badge value={replay?.soul_mode || 'OBSERVE_ONLY'} />} />
          <Metric label="Account" value={<Badge value={replay?.account_mode || 'PAPER_ONLY'} />} />
          <Metric label="Phase" value={replay?.phase || 'Phase-2.7D'} />
        </Card>
        <Card title="Health">
          <Metric label="Overall" value={<Badge value={health?.overall_status || 'UNKNOWN'} />} />
          <Metric label="Success" value={health?.status_counts?.success ?? '—'} />
          <Metric label="Warning" value={health?.status_counts?.warning ?? '—'} />
          <Metric label="Critical" value={health?.status_counts?.critical ?? '—'} />
        </Card>
        <Card title="Market Structure">
          <Metric label="Valid Rate" value={ms.valid_rate ?? '—'} />
          <Metric label="Valid" value={ms.valid_count ?? '—'} />
          <Metric label="Invalid" value={ms.invalid_count ?? '—'} />
        </Card>
        <Card title="Execution">
          <Metric label="Manual Filled" value={executionSummary.manual_filled_count ?? 0} />
          <Metric label="Manual Pending" value={executionSummary.manual_pending_count ?? 0} />
          <Metric label="Skipped" value={executionSummary.skipped_count ?? 0} />
        </Card>
      </div>

      <div className="grid-2" style={{ marginTop: 12 }}>
        <GovernanceScalabilityPanel data={governancePanelData} />
        <Card title="Risk Validation">
          <Metric label="Total" value={risk.total ?? '—'} />
          <Metric label="Pass" value={risk.pass_count ?? '—'} />
          <Metric label="Invalid" value={risk.invalid_count ?? '—'} />
          <Metric label="Snapshot UUID" value={replay?.snapshot_uuid || '—'} />
        </Card>
      </div>

      <div style={{ marginTop: 12 }}>
        <TopPicks topPicks={topPicks} decisionLog={decisionLog} />
      </div>

      <footer className="footer">PAPER_ONLY | OBSERVE_ONLY | Baseline Frozen | robot_6~10 RESERVED_ONLY</footer>
    </div>
  );
}
