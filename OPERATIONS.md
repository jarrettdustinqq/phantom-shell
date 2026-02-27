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

## Export Integrity Tamper Test (CI)

- Dispatch tamper test: `gh workflow run export-pr-evidence.yml -f pr_number=<pr_number> -f tamper_test=true`
- Expected outcome: workflow fails in `Verify uploaded artifact integrity` with `::error::Integrity mismatch ...` and non-zero exit.
- Dispatch normal test: `gh workflow run export-pr-evidence.yml -f pr_number=<pr_number> -f tamper_test=false`
- Expected outcome: workflow passes and integrity verification reports `PASS`.
- Record:
  - Failing run URL: `<paste failing run URL>`
  - Mismatch error line: `<paste exact ::error::Integrity mismatch line>`
  - Passing run URL: `<paste passing run URL>`

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
