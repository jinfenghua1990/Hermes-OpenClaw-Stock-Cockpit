# Candidate Pool Freshness Policy

## 核心原则

候选股票池必须每日刷新，禁止系统长期复用旧候选池。

---

## 当前问题

如果：

```text
portfolio/candidate_rankings.json
```

超过 1 个交易日未刷新，则：

```text
candidate_pool_status = STALE
```

不得继续使用旧候选池生成：

- Top Picks
- Paper Decision
- Intraday Runtime
- Feishu Push

---

## 强制要求

### 1. Morning Runtime

每天盘前必须执行候选池刷新。

如果候选池未刷新：

```text
morning_pipeline = WARNING / ERROR
```

### 2. Intraday Runtime

盘中每 15 分钟运行前必须检查候选池 freshness。

如果候选池 stale：

```text
runtime_data_stale_or_missing = true
```

并推送飞书风险提醒。

### 3. Paper Decision

如果候选池 stale：

```text
paper_skip
reason = stale_candidate_pool
```

禁止继续使用旧候选池做买入判断。

---

## Freshness SLA

候选池更新时间必须满足：

```text
candidate_rankings.updated_at >= today 08:30
```

如果没有 updated_at，则使用文件 modified time 判断。

---

## 结论

候选池刷新不是用户手动确认事项，而是系统 Runtime 职责。

```text
主动刷新
主动检测 stale
主动阻断旧数据
主动推送异常
```
