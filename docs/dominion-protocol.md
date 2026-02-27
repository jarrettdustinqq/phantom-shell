# DominionOS Protocol Implementation

This document maps the requested protocol into concrete, auditable components in this repository.

## Run the Control CLI

```bash
scripts/run_dominion_control.sh status
scripts/run_dominion_control.sh cycle --objective "Improve backup reliability and revenue resilience"
scripts/run_dominion_control.sh classify --text "Build passive income funnel with low risk"
scripts/run_dominion_swarm.sh
scripts/run_dominion_control.sh autotune --cpu-pct 42 --memory-pct 55 --queue-depth 18
scripts/run_dominion_control.sh catalyst --action propose --title "Upgrade queue retry" --hypothesis "Retry jitter reduces failures" --metric "error_rate" --baseline 6.2 --candidate 4.9
scripts/continuity_publish_guard.py --base-ref origin/main
```

State paths:

- `.loop-agent/dominion-policy.json`
- `.loop-agent/dominion-memory.json`
- `.loop-agent/dominion-events.jsonl`
- `.loop-agent/project-ark/`

## Implemented Components

1. Mission anchors and mode governance:
- Prime pillars and continuity mode tags are codified in `phantom_shell/dominion_protocol.py`.
- Objective classification maps tasks to mode tags and mission pillars.
- Structured vs Wild mode exists with explicit approver requirement for Wild mode.
- Auto-revert returns Wild mode to Structured when risk threshold is exceeded.

2. Memory fidelity and handoffs:
- Checkpoint memory uses vector-lite retrieval over token similarity.
- Strict handoff packet schema validation is enforced (`schema_version=1` + required keys).

3. Multi-agent orchestration scaffolding:
- Dominion agent definitions included: `reclaimor`, `mutator`, `ghost_writer`, `fund_tracker`,
  `identity_forge`, `tactician`, `dominion_guard`.
- Message bus emits append-only JSONL events for bootstrap and cycle actions.
- `scripts/dominion_agent_worker.py` runs each Dominion agent as a separate process over the bus.
- `scripts/run_dominion_swarm.sh` executes one process per agent in parallel (one-shot cycle).

4. Risk containment and fail-safes:
- Irreversible actions require explicit pre-approval.
- Trade guardrails block drawdown >5% and require pre-approval above 2.5% position size.
- Circuit breakers for trade/post frequency are enforced.
- Project Ark snapshots with retention pruning and restore tests are implemented.
- Off-site snapshot sync hook is supported via command templates
  (use `{snapshot_path}` placeholder in the command).
- Phoenix redeploy scaffolding restores snapshot content to a fresh destination.
- Snapshot restore enforces safe archive extraction and blocks traversal/link payloads.

5. Dual-LLM verification:
- Primary/secondary verification interface is implemented with explicit failover path.
- Works offline as a deterministic validation scaffold and can be replaced with live model calls.

6. Publishing and archive guardrails:
- Immutable sections are enforced using markers:
  `<!-- IMMUTABLE:START name --> ... <!-- IMMUTABLE:END name -->`
- Publish checks include immutable-section diff validation and sensitive-content alignment checks.

## Intentional Safety / Practical Limits

The following are intentionally not automated in this repo:

1. CAPTCHA/SMS bypass, stealth abuse, or identity-evasion automation.
2. Unattended fund transfer/trading execution.
3. Root-level ChromeOS modifications or kernel/eBPF changes from this project.
4. Full Kubernetes-in-Crostini orchestration as the default local path.

These are either high-risk, brittle on target hardware, or policy/regulatory sensitive.

## High-Leverage Next Steps

1. Connect `dual-verify` to real provider APIs behind least-privilege credentials.
2. Feed real connector telemetry into Dominion events and Auto-Tune loops.
3. Add a dedicated CI workflow that runs `publish-check` on Continuity archive PRs.
