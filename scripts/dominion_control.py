#!/usr/bin/env python3
"""CLI for DominionOS protocol controls."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
from dataclasses import asdict
import json
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.dominion_protocol import (  # noqa: E402
    DominionOrchestrator,
    TranscendenceState,
)


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))


def parse_bool(value: str) -> bool:
    clean = value.strip().lower()
    if clean in {"1", "true", "yes", "y"}:
        return True
    if clean in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean: {value}")


def parse_json_arg(value: str) -> Any:
    return json.loads(value)


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DominionOS control CLI")
    parser.add_argument("--state-dir", default=".loop-agent", help="state directory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show Dominion status")
    sub.add_parser("bootstrap", help="emit default Dominion agent bootstrap events")

    classify = sub.add_parser("classify", help="classify objective into modes/pillars")
    classify.add_argument("--text", required=True)

    cycle = sub.add_parser("cycle", help="run one dominion self-improvement cycle")
    cycle.add_argument("--objective", required=True)

    memory = sub.add_parser("memory-query", help="query checkpoint memory")
    memory.add_argument("--query", required=True)
    memory.add_argument("--limit", type=int, default=5)

    handoff = sub.add_parser("handoff", help="validate and record a handoff")
    handoff.add_argument("--json", default="", help="inline JSON payload")
    handoff.add_argument("--json-file", default="", help="path to JSON payload")

    mode = sub.add_parser("mode", help="set or auto-revert mode")
    mode.add_argument("--set", dest="set_mode", default="", choices=["structured", "wild"])
    mode.add_argument("--approved-by", default="")
    mode.add_argument("--reason", default="")
    mode.add_argument("--risk-score", type=float, default=-1.0)
    mode.add_argument("--risk-threshold", type=float, default=0.6)

    decide = sub.add_parser("decide-action", help="evaluate safety decision for an action")
    decide.add_argument("--type", required=True, choices=["trade", "post", "publish", "delete", "other"])
    decide.add_argument("--irreversible", default="false")
    decide.add_argument("--preapproved", default="false")
    decide.add_argument("--trade-position-pct", type=float, default=0.0)
    decide.add_argument("--drawdown-pct", type=float, default=0.0)

    tx = sub.add_parser("transcendence", help="evaluate transcendence trigger")
    tx.add_argument("--archive-published-and-indexed", default="false")
    tx.add_argument("--external-collaborator-interacted", default="false")
    tx.add_argument("--deep-research-no-improvement-cycles", type=int, default=0)
    tx.add_argument("--revenue-stream-usd-monthly", type=float, default=0.0)
    tx.add_argument("--publish-sync-full-cycles", type=int, default=0)

    verify = sub.add_parser("dual-verify", help="run dual-LLM verification scaffold")
    verify.add_argument("--prompt", required=True)
    verify.add_argument("--draft", required=True)
    verify.add_argument("--primary-model", default="gpt-5")
    verify.add_argument("--secondary-model", default="claude-opus")
    verify.add_argument("--secondary-available", default="true")

    pub = sub.add_parser("publish-check", help="run immutable-section and alignment checks")
    pub.add_argument("--baseline", required=True)
    pub.add_argument("--candidate", required=True)
    pub.add_argument("--out", default="")

    backup = sub.add_parser("backup", help="create Project Ark snapshot")
    backup.add_argument("--include", action="append", default=[])
    backup.add_argument("--retention-days", type=int, default=7)

    phoenix = sub.add_parser("phoenix", help="restore snapshot to destination")
    phoenix.add_argument("--snapshot", required=True)
    phoenix.add_argument("--destination", required=True)

    tune = sub.add_parser("autotune", help="run autotune heuristic on metric sample")
    tune.add_argument("--cpu-pct", type=float, required=True)
    tune.add_argument("--memory-pct", type=float, required=True)
    tune.add_argument("--queue-depth", type=int, required=True)

    cat = sub.add_parser("catalyst", help="manage catalyst evolution board")
    cat.add_argument(
        "--action",
        required=True,
        choices=["list", "propose", "update", "merge-if-improved"],
    )
    cat.add_argument("--item-id", default="")
    cat.add_argument("--title", default="")
    cat.add_argument("--hypothesis", default="")
    cat.add_argument("--metric", default="")
    cat.add_argument("--baseline", type=float, default=0.0)
    cat.add_argument("--candidate", type=float, default=0.0)
    cat.add_argument("--status", default="")

    return parser


def default_handoff() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "from_agent": "jarrett_prime",
        "to_agent": "mutator",
        "created_at": "2026-02-27T00:00:00+00:00",
        "mode_tags": ["forge_engine", "self_improvement_loop"],
        "objective": "Ship one measurable upgrade with risk gate checks.",
        "history": ["Baseline captured", "Top bottleneck identified"],
        "parameters": {"experiment_id": "exp-001", "risk_limit": "low"},
        "next_actions": ["Run sandbox experiment", "Compare metrics", "Promote if improved"],
        "prime_pillars": ["survive_minimize_risk", "passive_income_independence"],
    }


def main() -> int:
    args = build_parser().parse_args()
    state_dir = Path(args.state_dir).resolve()
    dom = DominionOrchestrator(state_dir=state_dir)

    if args.command == "status":
        print_json(dom.status())
        return 0

    if args.command == "bootstrap":
        print_json({"events": dom.bootstrap_events()})
        return 0

    if args.command == "classify":
        print_json(
            {
                "text": args.text,
                "mode_tags": dom.policy.classify_modes(args.text),
                "prime_pillars": dom.policy.map_pillars(args.text),
            }
        )
        return 0

    if args.command == "cycle":
        print_json(dom.run_cycle(args.objective))
        return 0

    if args.command == "memory-query":
        print_json({"results": dom.memory.query(args.query, limit=args.limit)})
        return 0

    if args.command == "handoff":
        if args.json_file:
            payload = load_json_file(Path(args.json_file))
        elif args.json:
            payload = parse_json_arg(args.json)
        else:
            payload = default_handoff()
        print_json({"handoff": dom.build_handoff(payload)})
        return 0

    if args.command == "mode":
        out: dict[str, Any] = {"current": dom.policy.state.get("current_mode", "structured")}
        if args.set_mode:
            out["set_result"] = dom.policy.set_mode(
                mode=args.set_mode,
                approved_by=args.approved_by,
                reason=args.reason,
            )
        if args.risk_score >= 0:
            out["auto_revert_result"] = dom.policy.auto_revert_if_risky(
                risk_score=args.risk_score,
                threshold=args.risk_threshold,
            )
        print_json(out)
        return 0

    if args.command == "decide-action":
        decision = dom.policy.decide_action(
            action_type=args.type,
            irreversible=parse_bool(args.irreversible),
            preapproved=parse_bool(args.preapproved),
            trade_position_pct=args.trade_position_pct,
            drawdown_pct=args.drawdown_pct,
        )
        print_json({"decision": asdict(decision)})
        return 0

    if args.command == "transcendence":
        state = TranscendenceState(
            archive_published_and_indexed=parse_bool(args.archive_published_and_indexed),
            external_collaborator_interacted=parse_bool(args.external_collaborator_interacted),
            deep_research_no_improvement_cycles=args.deep_research_no_improvement_cycles,
            revenue_stream_usd_monthly=args.revenue_stream_usd_monthly,
            publish_sync_full_cycles=args.publish_sync_full_cycles,
        )
        print_json({"transcendence": dom.policy.evaluate_transcendence(state)})
        return 0

    if args.command == "dual-verify":
        result = dom.verifier.verify(
            prompt=args.prompt,
            draft=args.draft,
            primary_model=args.primary_model,
            secondary_model=args.secondary_model,
            secondary_available=parse_bool(args.secondary_available),
        )
        print_json({"verification": asdict(result)})
        return 0

    if args.command == "publish-check":
        report = dom.publish_guard.evaluate(
            baseline_path=Path(args.baseline),
            candidate_path=Path(args.candidate),
        )
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"report_path={out_path}")
        print_json({"publish_check": report})
        return 0

    if args.command == "backup":
        include = [Path(item) for item in args.include] if args.include else [ROOT_DIR / "docs", ROOT_DIR / "scripts", ROOT_DIR / "phantom_shell", ROOT_DIR / ".github"]
        result = dom.ark.create_snapshot(
            include_paths=include,
            retention_days=args.retention_days,
        )
        print_json({"snapshot": asdict(result)})
        return 0

    if args.command == "phoenix":
        result = dom.ark.phoenix_redeploy(
            snapshot_path=Path(args.snapshot),
            destination=Path(args.destination),
        )
        print_json({"phoenix": result})
        return 0

    if args.command == "autotune":
        instruction = dom.tuner.evaluate(
            cpu_pct=args.cpu_pct,
            memory_pct=args.memory_pct,
            queue_depth=args.queue_depth,
        )
        print_json({"instruction": asdict(instruction), "history": dom.tuner.history(limit=10)})
        return 0

    if args.command == "catalyst":
        if args.action == "list":
            print_json({"items": dom.catalyst.list_items()})
            return 0
        if args.action == "propose":
            if not args.title or not args.hypothesis or not args.metric:
                raise ValueError(
                    "--title, --hypothesis, and --metric are required for catalyst propose"
                )
            row = dom.catalyst.propose(
                title=args.title,
                hypothesis=args.hypothesis,
                metric=args.metric,
                baseline=args.baseline,
                candidate=args.candidate,
            )
            print_json({"item": row})
            return 0
        if args.action == "update":
            if not args.item_id or not args.status:
                raise ValueError("--item-id and --status are required for catalyst update")
            row = dom.catalyst.update_status(item_id=args.item_id, status=args.status)
            print_json({"item": row})
            return 0
        if args.action == "merge-if-improved":
            if not args.item_id:
                raise ValueError("--item-id is required for catalyst merge-if-improved")
            row = dom.catalyst.merge_if_improved(item_id=args.item_id)
            print_json({"result": row})
            return 0
        raise RuntimeError(f"unknown catalyst action: {args.action}")

    raise RuntimeError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
