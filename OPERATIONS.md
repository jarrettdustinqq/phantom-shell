# Operations

## Agent-First Execution Rule

- Use agent-first execution for every task before requesting manual user action.
- Ask for manual user action only when blocked by permissions, tool limits, or safety constraints.
- When blocked, state the blocker and the smallest required user step.

## Pre-PR Verification Contract

The required `verify-revoke-evidence / evidence-gate` is an automatic exact-head repository verification gate.

It must:

1. check out `github.event.pull_request.head.sha` explicitly;
2. assert the checked-out commit equals that exact head SHA;
3. install the repository dependencies from `requirements.txt`;
4. run `scripts/verify_config.py`;
5. run the repository pytest suite.

A contributor cannot satisfy this check by editing the PR body. Typed timestamps, checklist claims, and other self-attestation are not verification evidence.

The former `verify-revoke-smoke` timestamp requirement was retired because the repository contained no corresponding smoke implementation. Do not recreate a fictional command or use fresh timestamps as proof. If a real verify/revoke capability is introduced later, give it an executable implementation and independently verifiable evidence tied to the exact commit before making it a required gate.

## Branch Protection

- Require status check `verify-revoke-evidence / evidence-gate` on protected branches.
- Keep ordinary `phantom-shell-ci` required where configured.
- A passing check proves only the code and tests executed by that workflow on the exact PR head; it does not prove host deployment or external runtime state.

## Permanent PR Evidence Export

- Run `make export-evidence-tuple PR=<pr_number>` to write a timestamped JSON tuple, markdown index, and sha256 file under `/home/jarrettdustinqq/incident-evidence/phantom-shell/`.
- The export records PR/status-check observations for audit. Legacy verify/revoke timestamp fields may be absent and are not required for readiness.

## Dispatch PR Evidence Export (CI)

- Trigger the workflow manually: `gh workflow run export-pr-evidence.yml -f pr_number=<pr_number>`.
- The workflow uploads a `pr-<pr_number>-evidence-tuple` artifact bundle (`.json`, `.md`, `.sha256`) and upserts a single PR comment with the run/artifact location.

## Export Integrity Tamper Test (CI)

- Dispatch tamper test: `gh workflow run export-pr-evidence.yml -f pr_number=<pr_number> -f tamper_test=true`
- Expected outcome: workflow fails in `Verify uploaded artifact integrity` with `::error::Integrity mismatch ...` and non-zero exit.
- Dispatch normal test: `gh workflow run export-pr-evidence.yml -f pr_number=<pr_number> -f tamper_test=false`
- Expected outcome: workflow passes and integrity verification reports `PASS`.
- Record template:
  - Failing run URL: `<paste failing run URL>`
  - Mismatch error line: `<paste exact mismatch error line>`
  - Passing run URL: `<paste passing run URL>`

## Nightly Tamper Guardrail

- Purpose: nightly dispatch of `export-pr-evidence.yml` with `tamper_test=true` to prove mismatch detection still fails correctly.
- Manual dispatch: `gh workflow run nightly-tamper-guardrail.yml -f pr_number=<pr_number>`.
- PR selection order: workflow `pr_number` input -> repository variable `PR_EVIDENCE_GUARDRAIL_PR_NUMBER` -> default `11`.
- Pass: export run concludes `failure` and logs include `Integrity mismatch for`.
- Fail: any other result; workflow opens or updates one marker-backed high-priority issue and fails.
