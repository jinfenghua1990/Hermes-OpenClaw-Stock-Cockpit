# Phase-2.7D Data Source Trace Policy

## 目标

所有：
- Top Picks
- AI Summary
- Replay Snapshot
- Paper Decision
- Risk Validation
- Execution
- Report
- Cockpit Metrics
- Multi-Agent Decision

必须带：

1. source_agent
2. source_module
3. data_source
4. data_as_of
5. trace_id
6. replay_snapshot

禁止：

无来源数据进入治理系统。

---

# 强制规则

任何：
- AI 分析
- 风险分析
- Top Picks
- 情绪分析
- Market Structure
- Execution
- Paper Decision

如果缺少：

- source_agent
或
- data_source

则：

status = WARNING

如果缺少：

- data_as_of

则：

status = CRITICAL

---

# Agent Source Rules

robot_1:
baseline_pattern_engine

robot_2:
market_structure_review

robot_3:
sentiment_theme_review

robot_4:
risk_validation_review

robot_5:
execution_replay_audit

robot_6~10:
RESERVED_ONLY

---

# Approved Data Sources

允许：

- akshare
- tushare
- eastmoney
- replay_snapshot
- governance_snapshot
- execution_bridge
- cockpit_runtime
- runtime_cache

禁止：

unknown_source

---

# Replay Requirements

Replay Snapshot 必须保留：

- source_agent
- data_source
- trace_id
- replay_snapshot

否则：

Replay Integrity = FAIL

---

# Governance Principle

AI Research Governance Platform：

所有数据必须：

- 可追踪
- 可验证
- 可回放
- 可审计
- 可定位来源

禁止：

黑盒 AI 数据。
