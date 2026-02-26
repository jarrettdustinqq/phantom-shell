# AGENTS.md

Repository-specific instructions for Codex.

## Mission

Keep `phantom-shell` configuration and Python tooling valid for autonomous execution.

## Required Checks

- `make verify`
- `make test`

## Constraints

- Keep configuration auditable and deterministic.
- Prefer additive updates and avoid deleting operator directives.
- ASCII by default.
