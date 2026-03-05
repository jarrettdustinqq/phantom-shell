# Lennox Kodex terminal reinstall (laptop)

Use this runbook when you want a clean reinstall of your local Codex terminal environment.

## Quick start

```bash
./scripts/reinstall_lennox_kodex_terminal.sh
```

## Objective alignment

This reinstall flow keeps your stack deterministic and ready for an autonomous AI ecosystem:

- Single local control point for tools and memory (`phantom-shell` repo).
- Verification gates on every reinstall (`make verify`, `make test`).
- Action logging discipline to support goal tracking and financial-asset growth experiments.

## Post-install operating loop

1. Define the current revenue or asset objective in `init.txt`.
2. Run `make verify`.
3. Run the loop workflow and track measurable deltas.
4. Keep only validated automations in the active stack.
