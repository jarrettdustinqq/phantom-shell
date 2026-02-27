# Ecosystem Agent Quickstart

## Goal

Run multiple specialized agents over a shared connector fabric with strict permissions.

## Start Dashboard/API

```bash
scripts/run_universal_agent_dashboard.sh
```

## Seed Default Agents

```bash
scripts/bootstrap_ecosystem_agents.sh
```

## Open Terminal Console

```bash
scripts/run_ecosystem_hub_console.sh
```

## Safety Rules

- Keep high-risk connectors disabled by default.
- Give each agent only the connector IDs it actually needs.
- Use health checks before route/workflow execution.
- Review `logs/universal_agent_audit.log` after action runs.
