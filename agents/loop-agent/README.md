# Loop Agent

`loop-agent` is a high-autonomy recursive optimizer.

It runs continuous improve-measure-update cycles on its own operating strategy,
then recommends external tools/frameworks that could run the same loop better.

## User-Friendly Console

Run:

```bash
scripts/run_loop_agent.sh
```

The console is interactive and persistent. It stores state at:

`projects/phantom-shell/.loop-agent/state.json`

### Core Commands

- `/help`
- `/objective <goal>`
- `/baseline <score 0-100> [strategy]`
- `/cycle [notes]`
- `/autopilot <count> [notes]`
- `/status`
- `/history [count]`
- `/recommend [count]`
- `/tools`
- `/search <query>`
- `/web <url>`
- `/shell <command>`
- `/python <code>`
- `/export [path]`
- `/reset`
- `/quit`

## Core Loop

1. Baseline objective and metrics
2. Diagnose highest-leverage bottleneck
3. Apply one high-impact change
4. Re-measure and log deltas
5. Update its own playbook
6. Recommend external accelerators
7. Decide continue or stop

## Output Contract

Each cycle returns:

- `objective`
- `baseline`
- `change_applied`
- `result_delta`
- `self_update`
- `recommended_tools`
- `next_decision`

## Recommended Tool Targets

The agent is expected to consider and rank options such as:

- Codex CLI workflows
- OpenAI Responses API agents
- LangGraph
- AutoGen
- CrewAI
- CI runners
- Containerized sandboxes
- Observability stacks

## Minimal Safety Floor

The design is intentionally low-friction, but still requires:

- no secret exfiltration
- operator confirmation for destructive/irreversible actions
- legal/policy-compliant behavior
