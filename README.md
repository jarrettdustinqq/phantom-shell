# phantom-shell

Automation shell for funnel and operations tasks, with machine-checkable configuration.

Included agent packs:

- `agents/business-chatgpt-handoff`
- `agents/loop-agent`

## Universal Agent Dashboard

```bash
scripts/run_universal_agent_dashboard.sh
```

Then open `http://127.0.0.1:8787`.

What it gives you:

- A single dashboard to register connectors for programs, apps, AI services, and tools.
- Connector types: `shell`, `webhook`, `openai`, `mcp`, `custom`.
- State persistence in `.loop-agent/universal-agent-state.json`.
- Metadata-only audit logging in `logs/universal_agent_audit.log`.

## Ecosystem Agent Environment

Builds a multi-agent layer on top of connectors so you can interact in several ways.

Interaction modes:

- Web dashboard/API at `http://127.0.0.1:8787`.
- Terminal REPL via `scripts/run_ecosystem_hub_console.sh`.
- Automation bootstrap via `scripts/bootstrap_ecosystem_agents.sh`.

Agent state:

- `.loop-agent/ecosystem-hub-state.json`

Useful API routes:

- `GET /api/agents`
- `POST /api/agents/register`
- `POST /api/agents/toggle`
- `POST /api/agents/suggest`
- `POST /api/agents/route`
- `POST /api/agents/workflow`

## DominionOS Control Plane

```bash
scripts/run_dominion_control.sh status
scripts/run_dominion_control.sh cycle --objective "Improve risk-managed growth and backup resilience"
scripts/run_dominion_swarm.sh
scripts/continuity_publish_guard.py --base-ref origin/main
```

What it provides:

- Mission-anchor enforcement with continuity mode tagging.
- Structured handoff schema validation.
- Message-bus event logging for Dominion agent orchestration.
- Safety gates for irreversible actions and trade/post circuit breakers.
- Project Ark backups with restore tests and Phoenix-style restore scaffold.
- Immutable-section publish guardrails and dual-LLM verification scaffold.

Read: `docs/dominion-protocol.md`

## Autonomous Risk Triage

New module that scans `logs/universal_agent_audit.log`, connector health, and mission tasks, scoring the top risks and suggesting mitigations.

```bash
scripts/run_autonomous_risk_triage.sh
cat reports/autonomous-risk-triage.json
```

Dashboard: the new Triage card (bottom of the UI) surfaces top events; click “Mitigate” any time you want to see the recommended action details.

## ChatGPT Mission Control Agent

Creates and tracks auditable task packets for ChatGPT.com agents, including
`deep_research` and `agent_mode` task types.

```bash
scripts/run_chatgpt_mission_control.sh status
scripts/run_chatgpt_mission_control.sh create --title "Investigate X" --objective "Find causes" --mode deep_research --assignee chatgpt.com-research-agent --context "Scope: service X" --acceptance "Include sources;Include confidence"
scripts/run_chatgpt_mission_control.sh list
```

Generate a handoff prompt packet:

```bash
scripts/run_chatgpt_mission_control.sh packet --task-id <task_id>
```

Note: this mission-control agent prepares task packets and tracking state. It does
not directly automate ChatGPT.com web sessions.

## Ecosystem Intelligence Agent

Analyzes every local AI-autonomy component, runs internet/deep-research query sets,
and produces improvement recommendations with source links.

```bash
scripts/run_ecosystem_intelligence_agent.sh
```

Outputs:

- `reports/ecosystem-intelligence-report.md`
- `reports/ecosystem-intelligence-report.json`

Optional email delivery to Gmail/Yahoo (SMTP + app password):

```bash
scripts/run_ecosystem_intelligence_agent.sh --send-email --email-to you@gmail.com
```

Required env vars for email mode:

- `EI_SMTP_HOST` (Gmail: `smtp.gmail.com`, Yahoo: `smtp.mail.yahoo.com`)
- `EI_SMTP_PORT` (`587`)
- `EI_SMTP_USER`
- `EI_SMTP_PASS` (app password)
- `EI_SMTP_FROM`

## Loop Agent Console

```bash
scripts/run_loop_agent.sh
```

This launches a user-friendly interactive environment with persistent memory,
recursive improvement cycles, tool recommendations, and report export.

## Validation

```bash
make verify
make test
```
