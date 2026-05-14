# SOUL STATUS

Current Mode: OBSERVE_ONLY

Policy:
SOUL is allowed to observe market data, reports, emotion snapshots, replay outputs, and historical summaries.
SOUL is NOT allowed to:
- Modify baseline strategies
- Modify strategy parameters
- Adjust weights
- Trigger trades
- Write decision outputs
- Override human judgment

Current Phase: Phase-2.4B-Stable

Reason: Historical data is not yet sufficient for learning or autonomous optimization.

Frozen Baseline: Hermes Baseline v1.0
- Located at: baseline_v1/
- Status: PERMANENTLY FROZEN
- Four modes: MODE 1 (回踩止跌), MODE 2 (突破启动), MODE 3 (小阳启动), MODE 4 (2波启动)
- Resonance: 3+ modes → candidate, 2 modes → watch only, 0 modes → no trade

Architecture Separation:
- baseline_v1/ → permanently frozen, no modifications allowed
- experimental/ → AI research zone, must not contaminate baseline
- Runtime reads from baseline_v1/ only
