import React from 'react';

export default function GovernanceScalabilityPanel({ data }) {
  if (!data) {
    return (
      <div className="card">
        <div className="loading">Governance Scalability 加载中...</div>
      </div>
    );
  }

  const {
    shadow_strategy_count = 0,
    arbitration_enabled = false,
    conflict_count = 0,
    reconciliation_status = 'UNKNOWN',
    baseline_drift_detected = false,
    replay_split_snapshot_ready = false,
    version = '2.7D'
  } = data;

  return (
    <div className="card">
      <div style={{ marginBottom: 10, fontWeight: 700 }}>
        🏛 Governance Scalability
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11 }}>
        <div>Version</div>
        <div>{version}</div>

        <div>Shadow Strategies</div>
        <div style={{ color: shadow_strategy_count > 0 ? 'var(--yellow)' : 'var(--green)' }}>
          {shadow_strategy_count}
        </div>

        <div>Arbitration</div>
        <div style={{ color: arbitration_enabled ? 'var(--green)' : 'var(--red)' }}>
          {arbitration_enabled ? 'ENABLED' : 'DISABLED'}
        </div>

        <div>Conflict Count</div>
        <div style={{ color: conflict_count > 0 ? 'var(--yellow)' : 'var(--green)' }}>
          {conflict_count}
        </div>

        <div>Execution Reconciliation</div>
        <div style={{ color: reconciliation_status === 'PASS' ? 'var(--green)' : 'var(--yellow)' }}>
          {reconciliation_status}
        </div>

        <div>Baseline Drift</div>
        <div style={{ color: baseline_drift_detected ? 'var(--red)' : 'var(--green)' }}>
          {baseline_drift_detected ? 'DETECTED' : 'PASS'}
        </div>

        <div>Replay Split Snapshot</div>
        <div style={{ color: replay_split_snapshot_ready ? 'var(--green)' : 'var(--yellow)' }}>
          {replay_split_snapshot_ready ? 'READY' : 'PENDING'}
        </div>
      </div>
    </div>
  );
}
