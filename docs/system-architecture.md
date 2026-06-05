# Phantom Shell System Architecture

This document defines how `phantom-shell` fits into the broader Jarrett agent-system workspace.

## Future-Agent Startup Rule

Before changing this repository, every agent must read the canonical registry and continuity state from `jarrettdustinqq/continuity`:

1. `repo-registry.json`
2. `state.json`

Agents must not infer repo roles from names alone. `continuity/repo-registry.json` is the machine-readable source of truth for repo classification, lifecycle state, responsibility boundaries, and next actions.

## Architecture Summary

`phantom-shell` is the production execution core. It owns runnable agent behavior, shell/tool execution safety, CI verification, evidence export, tamper guardrails, loop-agent execution, and operator-facing automation routines.

It does not own canonical cross-project memory. Durable project memory, state, handoffs, decisions, and repository classification live in `jarrettdustinqq/continuity`.

## Repository Roles

| Repository | Role | Boundary |
|---|---|---|
| `jarrettdustinqq/continuity` | Canonical memory/source of truth | Repo registry, state, project notes, context logs, decisions |
| `jarrettdustinqq/phantom-shell` | Production execution core | Agent runtime, shell utilities, loop-agent, CI, evidence export |
| `jarrettdustinqq/jarrettdustinqq-fleet` | Bootstrap/control plane | Controller setup, repo sync, health checks, mission-control, Control Hub |
| `jarrettdustinqq/continuity-spine` | Ledger/access automation | Access replay/check, access-delta ledger, promotion reports |
| `jarrettdustinqq/ledger-witness-offsite` | Witness/proof ledger | Anchor snapshots, proof hashes, receipts, verification gates |
| `jarrettdustinqq/phantom-shell-dr-vault` | Disaster recovery vault | Private backup snapshots and recovery material |

## Production Workflow

The full workflow is:

1. Bootstrap
2. Memory load
3. Execution
4. Verification
5. Recovery

### 1. Bootstrap

Primary repo: `jarrettdustinqq/jarrettdustinqq-fleet`

Fleet brings the controller/dev node online, syncs required repos, verifies local tooling, and launches mission-control or Control Hub workflows.

Expected controller setup flow:

```bash
./fleetctl bootstrap
./fleetctl health
./fleetctl mission-control
```

Fleet's `repos.txt` must track `continuity/repo-registry.json` for all repos that need to exist on the controller node.

### 2. Memory Load

Primary repo: `jarrettdustinqq/continuity`

Before editing `phantom-shell`, load the current state:

```text
repo-registry.json
state.json
projects/<relevant-project>.md
context-logs/<latest-relevant-handoff>.md
decisions/<relevant-decision>.md
```

Memory load determines:

- whether `phantom-shell` is the correct target repo
- which support repos are involved
- what durable facts already exist
- which decisions constrain the change
- what validation is required

### 3. Execution

Primary repo: `jarrettdustinqq/phantom-shell`

`phantom-shell` owns implementation work. Changes here should be small, testable, and production-usable.

Core local validation:

```bash
make verify
make test
```

Execution responsibilities:

- agent runtime behavior
- shell command safety
- loop-agent cycles
- evidence-export proof loops
- tamper guardrails
- CI gates
- reinstall workflows
- operational runbooks specific to execution

Execution non-responsibilities:

- canonical memory registry
- long-term cross-project handoff storage
- witness artifact retention
- DR snapshot storage
- controller bootstrap inventory

### 4. Verification

Primary support repos:

- `jarrettdustinqq/continuity-spine`
- `jarrettdustinqq/ledger-witness-offsite`

Verification proves that execution changes are replayable, checkable, and anchored.

Use `continuity-spine` for access replay/check and promotion gates. Use `ledger-witness-offsite` for private proof hashes, anchor snapshots, and receipts.

Evidence rules:

- proof artifacts must be replayable or rejectable
- hashes must be recomputable
- tamper tests must fail when expected
- witness logs must not store raw secrets
- evidence mismatch is a blocker

### 5. Recovery

Primary support repo: `jarrettdustinqq/phantom-shell-dr-vault`

DR recovery restores `phantom-shell` after loss, corruption, or environment drift.

Expected restore outline:

1. Restore from a named snapshot or manifest.
2. Verify restored files against expected hashes.
3. Run `make verify` and `make test` in `phantom-shell`.
4. Reload `continuity/repo-registry.json` and `continuity/state.json`.
5. Reconnect `fleet` bootstrap if the controller node was rebuilt.

## Change Routing Rules

Use this routing table before starting work:

| Change Type | Target Repo |
|---|---|
| Runtime agent behavior | `phantom-shell` |
| Shell/tool safety | `phantom-shell` |
| Execution CI gates | `phantom-shell` |
| Durable project state | `continuity` |
| Repo classifications | `continuity` |
| Controller bootstrap list | `jarrettdustinqq-fleet` |
| Access-delta replay/check | `continuity-spine` |
| Proof hashes / receipts | `ledger-witness-offsite` |
| DR snapshots / restore docs | `phantom-shell-dr-vault` |
| App UI or product surface | app-surface repo such as `aistudio` |

## PR Readiness Checklist

Before opening a `phantom-shell` PR:

- [ ] Read `continuity/repo-registry.json`.
- [ ] Read `continuity/state.json`.
- [ ] Confirm the change belongs in `phantom-shell`.
- [ ] Keep the change small and production-usable.
- [ ] Update docs/runbooks if behavior changed.
- [ ] Run `make verify`.
- [ ] Run `make test`.
- [ ] If evidence-related, document proof/tamper validation.
- [ ] If memory-related, update `continuity` instead of storing it here.

## Operating Principle

`phantom-shell` should be boring, testable, and evidence-gated. The broader agent system becomes reliable when every future agent starts from `continuity`, executes through `phantom-shell`, bootstraps through `fleet`, verifies through ledger/witness support, and recovers from the DR vault.
