#!/usr/bin/env python3
"""DominionOS agent worker process over the append-only event bus."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import hashlib
import json
import time

import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.dominion_protocol import DOMINION_AGENTS, DominionMessageBus, utc_now_iso


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def persona_from_seed(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    return f"persona-{digest}"


def build_output(agent_id: str, incoming_event: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    event_type = incoming_event.get("event_type", "")
    payload = dict(incoming_event.get("payload", {}))
    if agent_id == "reclaimor":
        return (
            "fund_found",
            {
                "source_event": event_type,
                "discovery_summary": "Potential recoverable balance detected in simulated scan.",
                "requires_operator_approval": True,
            },
        )
    if agent_id == "mutator":
        return (
            "mutation_proposed",
            {
                "source_event": event_type,
                "proposal": "Run one sandbox experiment and compare KPI delta before merge.",
                "sandbox_required": True,
            },
        )
    if agent_id == "ghost_writer":
        return (
            "content_draft_ready",
            {
                "source_event": event_type,
                "channel": "blog",
                "approval_required_before_publish": True,
            },
        )
    if agent_id == "fund_tracker":
        amount = float(payload.get("amount_usd", 0.0))
        return (
            "sale_event",
            {
                "source_event": event_type,
                "amount_usd": round(amount, 2),
                "seen_at": utc_now_iso(),
            },
        )
    if agent_id == "identity_forge":
        return (
            "persona_rotated",
            {
                "source_event": event_type,
                "persona_id": persona_from_seed(str(incoming_event.get("event_id", ""))),
                "note": "Metadata-only pseudonym rotation; no evasion automation performed.",
            },
        )
    if agent_id == "tactician":
        return (
            "new_trend",
            {
                "source_event": event_type,
                "trend": "operations automation reliability",
                "confidence": "medium",
            },
        )
    if agent_id == "dominion_guard":
        if event_type in {"backup_tick", "hourly_tick"}:
            return (
                "backup_complete",
                {
                    "source_event": event_type,
                    "result": "scheduled backup workflow should run via Project Ark command.",
                },
            )
        return (
            "agent_restarted",
            {
                "source_event": event_type,
                "result": "suggest rolling restart of affected worker with health checks.",
            },
        )
    return None


def run_once(state_dir: Path, agent_id: str) -> dict[str, Any]:
    event_log = state_dir / "dominion-events.jsonl"
    cursor_dir = state_dir / "agent-cursors"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    cursor_path = cursor_dir / f"{agent_id}.cursor"

    definitions = {row["agent_id"]: row for row in DOMINION_AGENTS}
    if agent_id not in definitions:
        raise ValueError(f"unknown agent_id: {agent_id}")

    triggers = set(definitions[agent_id]["triggers"])
    events = load_events(event_log)
    start_index = 0
    if cursor_path.exists():
        try:
            start_index = int(cursor_path.read_text(encoding="utf-8").strip())
        except ValueError:
            start_index = 0
    new_events = events[start_index:]
    bus = DominionMessageBus(event_log)
    emitted = []
    processed = 0
    for event in new_events:
        if event.get("event_type") not in triggers:
            continue
        processed += 1
        output = build_output(agent_id, event)
        if output is None:
            continue
        out_type, payload = output
        emitted.append(bus.emit(event_type=out_type, source=agent_id, payload=payload))
    cursor_path.write_text(str(len(events)), encoding="utf-8")
    return {
        "agent_id": agent_id,
        "processed_trigger_events": processed,
        "emitted_count": len(emitted),
        "emitted": emitted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="DominionOS agent worker")
    parser.add_argument("--state-dir", default=".loop-agent")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args()

    state_dir = Path(args.state_dir).resolve()
    if args.once:
        print(json.dumps(run_once(state_dir, args.agent_id), indent=2, ensure_ascii=True))
        return 0

    while True:
        result = run_once(state_dir, args.agent_id)
        print(json.dumps(result, ensure_ascii=True))
        time.sleep(max(0.5, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
