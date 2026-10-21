# Loop Agent

`loop-agent` is a persistent console for improvement proposals and recorded scores.

It records user-supplied measurements and suggests changes and tools. A cycle
does not execute the suggested change or independently measure its result.

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
2. Propose a change
3. Apply and measure the change outside the scoring cycle
4. Supply the measured score and record the delta
5. Update the playbook only from supplied measurements
6. Recommend external accelerators
7. Decide whether to continue or collect a measurement

Blank measurements and `/autopilot` produce projections only. Their scores are
deterministic illustrations, not forecasts or evidence of improved performance.
They leave the stored score, strategy, and playbook unchanged, set `actual_delta`
to `null`, and return `collect_measurement`. The compatible `change_applied` field
contains a proposal in projected mode; console output and reports label it as such.
Supplied scores are recorded observations, not independently verified outcomes.

### Existing state from earlier versions

Earlier projected cycles may already have increased a saved score and promoted
playbook entries without measurements. This update preserves that history and
does not silently reconstruct a supposedly measured baseline. For such files,
retain the old state as historical evidence and start with a new `--state-path`,
then set a fresh baseline from an actual measurement. Old projected records remain
projections even when their legacy fields contain `actual_delta` or promotion text.

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
- operator confirmation for destructive actions and independently required approvals
- irreversibility alone is not a blocker; scope and authorization requirements still apply
- legal/policy-compliant behavior
