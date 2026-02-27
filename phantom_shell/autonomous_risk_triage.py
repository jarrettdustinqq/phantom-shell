"""Autonomous risk triage collector, scoring, and action suggestion."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import math


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TriageEvent:
    event_id: str
    timestamp: str
    source: str
    connector_id: str | None
    action: str
    status: str
    details: dict[str, Any]
    severity: int
    message: str


@dataclass
class ActionCandidate:
    event_id: str
    title: str
    impact: str
    effort: str
    suggested_action: str
    mitigation: str


class AutonomousRiskTriage:
    """Collects audit data, scores risks, and produces action packets."""

    def __init__(self, state_dir: Path, log_path: Path) -> None:
        self.state_dir = state_dir
        self.log_path = log_path

    def _read_json_state(self, name: str) -> dict[str, Any]:
        path = self.state_dir / name
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _parse_audit_log(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _event_id(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"evt-{digest}"

    def collect_inventory(self) -> dict[str, Any]:
        return {
            "universal_agent": self._read_json_state("universal-agent-state.json"),
            "ecosystem_hub": self._read_json_state("ecosystem-hub-state.json"),
            "mission_control": self._read_json_state("chatgpt-mission-control.json"),
        }

    def score_event(self, entry: dict[str, Any]) -> int:
        base = 10
        action = entry.get("action", "")
        status = entry.get("status", "")
        details = entry.get("details")
        if not isinstance(details, dict):
            details = {}
        if status not in {"ok", "healthy"}:
            base += 20
        if action == "run":
            duration_raw = details.get("duration_ms", 0)
            try:
                duration = float(duration_raw)
            except (TypeError, ValueError):
                duration = 0.0
            base += min(math.ceil(duration / 100), 5)
        if action == "health_check" and status == "unhealthy":
            base += 15
        if entry.get("connector_id"):
            base += 2
        return min(base, 100)

    def build_events(self) -> list[TriageEvent]:
        entries = self._parse_audit_log()
        events: list[TriageEvent] = []
        for entry in entries[-200:]:
            details = entry.get("details")
            if not isinstance(details, dict):
                details = {}
            timestamp = entry.get("ts_utc", utc_now_iso())
            event_id = self._event_id(
                {
                    "source": "audit_log",
                    "timestamp": timestamp,
                    "connector_id": entry.get("connector_id"),
                    "action": entry.get("action", ""),
                    "status": entry.get("status", ""),
                    "details": details,
                }
            )
            severity = self.score_event(entry)
            message = (
                f"{entry.get('action')} {entry.get('connector_id','')}"
                + f" status={entry.get('status', '')}"
            )
            events.append(
                TriageEvent(
                    event_id=event_id,
                    timestamp=timestamp,
                    source="audit_log",
                    connector_id=entry.get("connector_id"),
                    action=entry.get("action", ""),
                    status=entry.get("status", ""),
                    details=details,
                    severity=severity,
                    message=message,
                )
            )
        mission = self.collect_inventory().get("mission_control", {})
        for task in mission.get("tasks", []):
            status = task.get("status", "")
            timestamp = task.get("updated_at", utc_now_iso())
            event_id = self._event_id(
                {
                    "source": "mission_control",
                    "timestamp": timestamp,
                    "task_id": task.get("task_id", "unknown"),
                    "status": status,
                }
            )
            severity = 30 if status in {"blocked", "queued"} else 10
            events.append(
                TriageEvent(
                    event_id=event_id,
                    timestamp=timestamp,
                    source="mission_control",
                    connector_id=None,
                    action="mission_task",
                    status=status,
                    details=task,
                    severity=severity,
                    message=f"mission task {task.get('task_id','')} status={status}",
                )
            )
        return sorted(events, key=lambda e: (e.severity, e.timestamp), reverse=True)[:10]

    def find_event(self, event_id: str) -> TriageEvent | None:
        for event in self.build_events():
            if event.event_id == event_id:
                return event
        return None

    def suggest_action(self, event: TriageEvent) -> ActionCandidate:
        if event.action == "run" and event.status != "ok":
            return ActionCandidate(
                event_id=event.event_id,
                title="Connector run failure",
                impact="High",
                effort="Medium",
                suggested_action="Review connector logs and re-run health check; disable if repeated.",
                mitigation="Burst retries exist; build a temporary run block or toggle connector.",
            )
        if event.action == "health_check" and event.status != "healthy":
            return ActionCandidate(
                event_id=event.event_id,
                title="Unhealthy health check",
                impact="High",
                effort="Low",
                suggested_action="Re-run health_check and mark connector for manual inspection.",
                mitigation="Use CLI /api/connectors/health to force fresh status.",
            )
        if event.action == "mission_task":
            return ActionCandidate(
                event_id=event.event_id,
                title="Queued/blocked mission task",
                impact="Medium",
                effort="Low",
                suggested_action="Assign to a research agent or merge into intelligence digest.",
                mitigation="Attach clear impact/effort scoring before enabling.",
            )
        return ActionCandidate(
            event_id=event.event_id,
            title="Connector observation",
            impact="Low",
            effort="Low",
            suggested_action="Monitor and confirm connector health.",
            mitigation="Ensure routine health checks and stats building.",
        )

    def build_report(self) -> dict[str, Any]:
        events = self.build_events()
        actions = [asdict(self.suggest_action(evt)) for evt in events]
        return {
            "generated_at": utc_now_iso(),
            "events": [asdict(evt) for evt in events],
            "actions": actions,
        }
