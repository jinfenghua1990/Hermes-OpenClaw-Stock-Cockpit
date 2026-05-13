# SOUL STATUS

**版本**: v1.1 (Team Governance Freeze Update)
**更新时间**: 2026-05-13

---

## Current Mode

**OBSERVE_ONLY**

## Freeze Status

**🧊 ACTIVE** — Team Governance Freeze v1.0

## Policy

SOUL is allowed to observe market data, reports, emotion snapshots, replay outputs, and historical summaries.
SOUL is NOT allowed to:

- Modify baseline strategies
- Modify strategy parameters
- Adjust weights
- Trigger trades
- Write decision outputs
- Override human judgment
- Create new robots
- Extend team
- Use unregistered robots
- Modify team structure

## Current Phase

**Phase-2.4B-Stable**

## Governance

- 正式团队: MAIN, OpenClaw, robot_2, robot_3, robot_4, robot_5
- 保留位(未部署): robot_6, robot_7, robot_8, robot_9, robot_10
- unregistered_robot_access: BLOCKED
- dynamic_robot_creation: DISABLED

## Reason

Historical data is not yet sufficient for learning or autonomous optimization.
Team structure frozen to prevent unregistered robot invocation and governance drift.

## Source Files

- `governance/team_register.yaml` — 官方团队注册表
- `governance/freeze_status.json` — 冻结状态文件
- `governance/SOVEREIGNTY.md` — MAIN自约束规范
- `config/soul_config.json` — SOUL配置
