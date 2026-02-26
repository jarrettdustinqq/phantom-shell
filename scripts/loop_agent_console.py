#!/usr/bin/env python3
"""Interactive console for loop-agent recursive improvement workflows."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import argparse
import shlex
import sys
import textwrap

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.loop_agent_engine import LoopAgentEngine, LoopCycle


def truncate(text: str, max_chars: int = 1600) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 14] + "\n...[truncated]"


def format_cycle(cycle: LoopCycle) -> str:
    tool_lines = []
    for item in cycle.recommended_tools.get("tools", [])[:4]:
        tool_lines.append(
            f"- {item['name']} (fit={item['fit']}, setup={item['setup_cost']}, gain={item['expected_gain']})"
        )
    if not tool_lines:
        tool_lines.append("- (none)")
    return "\n".join(
        [
            f"Cycle {cycle.cycle_number} @ {cycle.timestamp}",
            f"objective: {cycle.objective}",
            f"baseline: score={cycle.baseline.get('score')} strategy={cycle.baseline.get('strategy')}",
            f"change_applied: {cycle.change_applied}",
            (
                "result_delta: "
                f"mode={cycle.result_delta.get('mode')} "
                f"actual={cycle.result_delta.get('actual_delta')} "
                f"projected={cycle.result_delta.get('projected_delta')} "
                f"new_score={cycle.result_delta.get('new_score')}"
            ),
            f"self_update: {cycle.self_update}",
            "recommended_tools:",
            *tool_lines,
            f"next_decision: {cycle.next_decision}",
        ]
    )


def help_text() -> str:
    return textwrap.dedent(
        """
        Commands:
          /help
          /objective <text>
          /baseline <score 0-100> [strategy text]
          /status
          /cycle [notes]
          /autopilot <count> [notes]
          /history [count]
          /recommend [count]
          /tools
          /search <query>
          /web <url>
          /shell <command>
          /python <code>
          /export [path]
          /reset
          /quit

        Tips:
          - If no objective is set, run: /objective <your goal>
          - For /cycle, you can provide a measured score when prompted.
          - /autopilot uses projected scores and runs fast loop batches.
        """
    ).strip()


def print_banner(state_path: Path) -> None:
    print("=" * 72)
    print("Loop Agent Console")
    print("Recursive self-improvement engine with tooling and recommendations")
    print(f"state: {state_path}")
    print("=" * 72)


def print_status(engine: LoopAgentEngine) -> None:
    status = engine.status()
    print(
        "\n".join(
            [
                "status:",
                f"- objective: {status['objective']}",
                f"- baseline_score: {status['baseline_score']}",
                f"- current_score: {status['current_score']}",
                f"- cycle_count: {status['cycle_count']}",
                f"- strategy: {status['strategy']}",
                f"- updated_at: {status['updated_at']}",
            ]
        )
    )


def parse_float(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid number: {value}") from exc


def prompt_measured_score() -> float | None:
    raw = input("Measured score [0-100] (blank uses projected): ").strip()
    if not raw:
        return None
    value = parse_float(raw)
    if value < 0 or value > 100:
        raise ValueError("Measured score must be in range 0-100.")
    return value


def default_export_path(state_path: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return state_path.parent / "exports" / f"loop-agent-report-{timestamp}.md"


def run_cycle(engine: LoopAgentEngine, note: str) -> None:
    measured = prompt_measured_score()
    cycle = engine.run_cycle(note=note, measured_score=measured)
    print(format_cycle(cycle))


def run_autopilot(engine: LoopAgentEngine, args: list[str]) -> None:
    if not args:
        raise ValueError("Usage: /autopilot <count> [notes]")
    count = int(args[0])
    if count < 1:
        raise ValueError("Autopilot count must be >= 1.")
    if count > 50:
        raise ValueError("Autopilot count capped at 50 to keep output usable.")
    note = " ".join(args[1:]).strip()
    for idx in range(count):
        cycle = engine.run_cycle(note=f"{note} [auto {idx + 1}/{count}]".strip())
        print(
            f"[autopilot] cycle={cycle.cycle_number} "
            f"delta={cycle.result_delta.get('actual_delta')} "
            f"score={cycle.result_delta.get('new_score')} "
            f"decision={cycle.next_decision}"
        )


def run_shell(engine: LoopAgentEngine, command: str) -> None:
    risk = engine.shell_risk(command)
    if risk:
        confirm = input(
            "Potentially destructive command detected. "
            "Type YES to continue: "
        ).strip()
        if confirm != "YES":
            print("Cancelled.")
            return
    result = engine.run_shell(command)
    print(f"exit_code: {result['exit_code']}")
    if result["stdout"]:
        print("stdout:")
        print(truncate(result["stdout"]))
    if result["stderr"]:
        print("stderr:")
        print(truncate(result["stderr"]))


def run_python(engine: LoopAgentEngine, code: str) -> None:
    result = engine.run_python(code)
    print(f"exit_code: {result['exit_code']}")
    if result["stdout"]:
        print("stdout:")
        print(truncate(result["stdout"]))
    if result["stderr"]:
        print("stderr:")
        print(truncate(result["stderr"]))


def run_search(engine: LoopAgentEngine, query: str) -> None:
    rows = engine.search_web(query)
    if not rows:
        print("No search results parsed.")
        return
    print(f"results for: {query}")
    for idx, row in enumerate(rows, start=1):
        print(f"{idx}. {row['title']}")
        print(f"   {row['url']}")


def run_web(engine: LoopAgentEngine, url: str) -> None:
    preview = engine.fetch_web_preview(url)
    print(f"preview ({url}):")
    print(truncate(preview, max_chars=2600))


def print_recommendations(engine: LoopAgentEngine, limit: int) -> None:
    rows = engine.recommend_tools(limit=limit)
    targets = engine.recommend_targets(limit=4)
    print("tool recommendations:")
    for idx, item in enumerate(rows, start=1):
        print(
            f"{idx}. {item.name} | fit={item.fit} | setup={item.setup_cost} "
            f"| risk={item.risk} | gain={item.expected_gain}"
        )
        print(f"   {item.reason}")
    print("recommended targets for this loop style:")
    for idx, target in enumerate(targets, start=1):
        print(f"{idx}. {target['target']}")
        print(f"   {target['reason']}")


def print_history(engine: LoopAgentEngine, count: int) -> None:
    rows = engine.cycle_history(limit=count)
    if not rows:
        print("No cycles yet.")
        return
    for cycle in rows:
        print(format_cycle(cycle))
        print("-" * 72)


def print_tools() -> None:
    print(
        "\n".join(
            [
                "available capabilities:",
                "- recursive improvement cycles with persistent memory",
                "- objective scoring and measured/projected deltas",
                "- self-updating playbook after each cycle",
                "- ranked tool recommendations plus suggested target programs",
                "- shell execution (with confirmation for dangerous patterns)",
                "- python snippet execution",
                "- web search and URL preview utilities",
                "- markdown report export",
            ]
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Loop Agent interactive console")
    parser.add_argument(
        "--state-path",
        type=Path,
        default=Path(".loop-agent/state.json"),
        help="Path for persistent state JSON file.",
    )
    parser.add_argument(
        "--objective",
        type=str,
        default="",
        help="Optional objective to set at startup.",
    )
    return parser


def process_command(engine: LoopAgentEngine, line: str, state_path: Path) -> bool:
    parts = shlex.split(line)
    if not parts:
        return True
    cmd, *args = parts

    if cmd in {"/quit", "/exit"}:
        return False
    if cmd == "/help":
        print(help_text())
        return True
    if cmd == "/objective":
        if not args:
            raise ValueError("Usage: /objective <text>")
        objective = " ".join(args).strip()
        engine.set_objective(objective)
        print(f"objective set: {objective}")
        return True
    if cmd == "/baseline":
        if not args:
            raise ValueError("Usage: /baseline <score 0-100> [strategy]")
        score = parse_float(args[0])
        strategy = " ".join(args[1:]).strip()
        engine.set_baseline(score, strategy)
        print(
            f"baseline updated: score={engine.state.baseline_score} "
            f"strategy={engine.state.strategy}"
        )
        return True
    if cmd == "/status":
        print_status(engine)
        return True
    if cmd == "/cycle":
        note = " ".join(args).strip()
        run_cycle(engine, note=note)
        return True
    if cmd == "/autopilot":
        run_autopilot(engine, args)
        return True
    if cmd == "/history":
        count = int(args[0]) if args else 5
        print_history(engine, count=count)
        return True
    if cmd == "/recommend":
        limit = int(args[0]) if args else 6
        print_recommendations(engine, limit=limit)
        return True
    if cmd == "/tools":
        print_tools()
        return True
    if cmd == "/search":
        if not args:
            raise ValueError("Usage: /search <query>")
        run_search(engine, query=" ".join(args))
        return True
    if cmd == "/web":
        if not args:
            raise ValueError("Usage: /web <url>")
        run_web(engine, url=args[0])
        return True
    if cmd == "/shell":
        if not args:
            raise ValueError("Usage: /shell <command>")
        run_shell(engine, command=" ".join(args))
        return True
    if cmd == "/python":
        if not args:
            raise ValueError("Usage: /python <code>")
        run_python(engine, code=" ".join(args))
        return True
    if cmd == "/export":
        path = Path(args[0]) if args else default_export_path(state_path)
        report = engine.export_markdown_report(path)
        print(f"exported: {report}")
        return True
    if cmd == "/reset":
        confirm = input("Type RESET to clear loop-agent state: ").strip()
        if confirm == "RESET":
            engine.reset_state()
            print("State reset complete.")
        else:
            print("Cancelled.")
        return True

    raise ValueError(f"Unknown command: {cmd}. Run /help.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    state_path = args.state_path
    engine = LoopAgentEngine(state_path=state_path)

    if args.objective.strip():
        engine.set_objective(args.objective.strip())

    print_banner(state_path=state_path)
    print_help = (
        "Use /help for commands. Recommended start: "
        "/objective <goal> then /cycle"
    )
    print(print_help)
    print_status(engine)

    while True:
        try:
            line = input("\nloop-agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting loop-agent console.")
            break
        if not line:
            continue
        try:
            should_continue = process_command(engine, line, state_path=state_path)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"error: {exc}")
            continue
        if not should_continue:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
