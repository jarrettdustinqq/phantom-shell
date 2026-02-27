# Operations

## Agent-First Execution Rule

- Use agent-first execution for every task before requesting manual user action.
- Ask for manual user action only when blocked by permissions, tool limits, or safety constraints.
- When blocked, state the blocker and the smallest required user step.

## Pre-PR Checklist

- [ ] Before merge, paste the latest `verify-revoke-smoke` timestamp pair from the current run (`verify=<timestamp>`, `revoke=<timestamp>`).

## Branch Protection

- Require status check `verify-revoke-evidence / evidence-gate` on protected branches.

## Permanent PR Evidence Export

- Run `make export-evidence-tuple PR=<pr_number>` to write a timestamped JSON tuple, markdown index, and sha256 file under `/home/jarrettdustinqq/incident-evidence/phantom-shell/`.

## Dispatch PR Evidence Export (CI)

- Trigger the workflow manually: `gh workflow run export-pr-evidence.yml -f pr_number=<pr_number>`.
- The workflow uploads a `pr-<pr_number>-evidence-tuple` artifact bundle (`.json`, `.md`, `.sha256`) and upserts a single PR comment with the run/artifact location.

## Nightly Tamper Guardrail

- Purpose: nightly dispatch of `export-pr-evidence.yml` with `tamper_test=true` to verify integrity mismatch detection does not regress.
- Manual dispatch command: `gh workflow run nightly-tamper-guardrail.yml -f pr_number=<pr_number>`.
- PR selection order: workflow input `pr_number` -> repository variable `PR_EVIDENCE_GUARDRAIL_PR_NUMBER` -> default `11`.
- Pass criteria: dispatched `export-pr-evidence` run concludes `failure` and logs contain `Integrity mismatch for`.
- Fail criteria: any other conclusion or missing mismatch log evidence; the workflow upserts one marker-backed high-priority regression issue and fails.

## 3-Minute Evidence Gate Proof

1. Edit the PR body with this stale-test block and save:

```text
verify-revoke-smoke:
verify=2026-01-01T00:00:00Z
revoke=2026-01-01T00:05:00Z
- [x] verify-revoke-smoke evidence pair attached in exact format
```

Expected: `verify-revoke-evidence / evidence-gate` fails.

2. Run `make verify-revoke-smoke`, then use the current run timestamps: `verify=<rotate_plan_ts>` and `revoke=<rotate_exec_ts>`.
3. Replace the PR body with this fresh-test block (using your current run values) and save:

```text
verify-revoke-smoke:
verify=<rotate_plan_ts>
revoke=<rotate_exec_ts>
- [x] verify-revoke-smoke evidence pair attached in exact format
```

Expected: `verify-revoke-evidence / evidence-gate` passes.
