# Hermes + OpenClaw Governance Cockpit

Phase: Phase-2.4B  
Mode: OBSERVE_ONLY

This dashboard is a visualization layer for the AI Research Governance OS.

## Purpose

The Cockpit displays governance, health, consensus, replay, attribution, risk, and audit state.

It must not execute trades, change positions, mutate baseline strategy, create robots, or trigger autonomous learning.

## Core Principles

- Visualization only
- User decision only
- No execution controls
- No trading controls
- No hidden state override
- Official team only
- Governance Controller has priority

## Main Sections

1. Governance Overview
2. System Health
3. Consensus Center
4. Risk Heatmap
5. Replay Center
6. Attribution Center
7. Integrity Alerts
8. Audit Trail
9. Pipeline Monitor

## Source Files

- dashboard/dashboard_state_schema.yaml
- dashboard/dashboard_snapshot_template.json
- dashboard/cockpit_navigation_schema.yaml
- dashboard/cockpit_widget_registry.yaml
- dashboard/cockpit_layout_template.json
- governance/governance_state_snapshot_schema.yaml
- governance/risk_heatmap_schema.yaml
- governance/consensus_archive_schema.yaml
- reports/final_decision_summary.json

## Status

Cockpit Foundation: active

UI Implementation: pending
