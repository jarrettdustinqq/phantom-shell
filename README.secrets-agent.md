# Secrets Agent Scaffold (Non-Custodial)

This starter provides a minimal CLI for password/key operations that never stores plaintext secrets.
It only reads metadata from an external vault CLI and writes metadata-only audit logs.

## Safety Guarantees

- No hardcoded secrets.
- No plaintext secret retrieval or persistence.
- Metadata-only logging to `SECRETS_AGENT_LOG_PATH` (default: `logs/secrets_agent_audit.log`).
- Rotate/revoke operations require explicit confirmation (`--plan-id` + `--confirm`).
- External execution uses opt-in hooks (`SECRETS_AGENT_ROTATE_HOOK`, `SECRETS_AGENT_REVOKE_HOOK`).

## Setup

1. Copy and edit environment file:

```bash
cp .env.example .env
```

2. Set backend and confirmation salt:

```bash
export SECRETS_AGENT_BACKEND=bitwarden
export SECRETS_AGENT_CONFIRM_SALT='replace-with-long-random-value'
```

3. Authenticate with your provider CLI outside this app:

- Bitwarden example: `bw login` then `bw unlock`
- 1Password example: `op signin`

4. Optional hooks for integration with your existing runbooks:

```bash
export SECRETS_AGENT_ROTATE_HOOK='echo rotate {item_id}'
export SECRETS_AGENT_REVOKE_HOOK='echo revoke {item_id}'
```

## Commands

- `python3 secrets_agent.py status`
- `python3 secrets_agent.py list-items`
- `python3 secrets_agent.py rotate-plan --item <id>`
- `python3 secrets_agent.py rotate-exec --plan-id <id> --confirm <token> [--item <id>] [--revoke]`
- `python3 secrets_agent.py key-audit --stale-days 90`

## Backend Abstraction Notes

`secrets_agent.py` includes adapters for:
- Bitwarden (`bw` CLI)
- 1Password (`op` CLI)
- `mock` backend for local smoke testing

Adapters are intentionally metadata-only. If your environment needs custom list/audit fields,
extend the metadata mapping in the backend class without adding secret reads.

## Threat Model (Starter)

In scope:
- Prevent accidental plaintext secret exposure via logs or local state.
- Require explicit operator confirmation before sensitive rotate/revoke actions.
- Provide traceability with append-only metadata audit lines.

Out of scope:
- Vault platform compromise.
- Host compromise with full process/memory access.
- Malicious external hook scripts configured by operator.

## Safe Operation Rules

- Run from a locked-down host with least-privilege vault account.
- Keep `SECRETS_AGENT_CONFIRM_SALT` outside source control.
- Treat hooks as privileged automation; review command templates before use.
- Use `rotate-plan` immediately before `rotate-exec` to avoid stale intent.
- Review audit log lines after each run; logs should contain IDs/timestamps only.

## Local Staging Dry Run

- Local runtime env file (not tracked): `.loop-agent/secrets-agent.env`
- Run full safe dry run flow (status -> rotate-plan -> rotate-exec):

```bash
./scripts/run_secrets_agent_dry_run.sh
```

## Revoke Smoke Verification

Run one command to verify `rotate-plan` + `rotate-exec --revoke` and fail if any new
`action=error` audit entry appears during the run:

```bash
make verify-revoke-smoke
```
