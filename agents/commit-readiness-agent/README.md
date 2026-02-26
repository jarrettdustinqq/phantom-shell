# Commit Readiness Agent

`commit-readiness-agent` runs a strict pre-commit workflow for loop-agent work.

It is designed to:

- install only missing minimum test dependency (`pytest`) if needed
- run `tests/test_loop_agent_engine.py` as the commit gate
- stage only loop-agent-related files
- verify staged diff scope before commit
- create one single-purpose commit with an imperative subject

## Scope Rules

This agent should include only:

- `.gitignore` updates for loop-agent artifacts when present
- `agents/loop-agent/*`
- `phantom_shell/loop_agent_engine.py`
- `phantom_shell/__init__.py` loop-agent exports
- `scripts/loop_agent_console.py`
- `scripts/run_loop_agent.sh`
- `tests/test_loop_agent_engine.py`

It should exclude unrelated modified files from the commit.

## Commit Gate

The commit decision must be based strictly on:

```bash
python3 -m pytest -q tests/test_loop_agent_engine.py
```

If this gate fails, do not commit.
