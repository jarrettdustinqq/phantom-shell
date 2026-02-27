"""Mission control for assigning deep research and agent-mode tasks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import uuid


VALID_MODES = {"deep_research", "agent_mode"}
VALID_STATUS = {"draft", "queued", "in_progress", "blocked", "done"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MissionTask:
    task_id: str
    created_at: str
    updated_at: str
    title: str
    objective: str
    mode: str
    assignee: str
    context: str
    acceptance_criteria: list[str]
    status: str
    result_summary: str = ""


class ChatGPTMissionControl:
    """Local task planner for ChatGPT.com manual handoff workflows."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.tasks: dict[str, MissionTask] = {}
        self.load_state()

    def load_state(self) -> None:
        if not self.state_path.exists():
            self.tasks = {}
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        rows = payload.get("tasks", [])
        self.tasks = {row["task_id"]: MissionTask(**row) for row in rows}

    def save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [asdict(row) for row in self.tasks.values()]
        rows.sort(key=lambda item: item["created_at"])
        payload = {
            "updated_at": utc_now_iso(),
            "task_count": len(rows),
            "tasks": rows,
        }
        self.state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def create_task(
        self,
        title: str,
        objective: str,
        mode: str,
        assignee: str,
        context: str,
        acceptance_criteria: list[str],
    ) -> dict[str, Any]:
        clean_mode = mode.strip()
        if clean_mode not in VALID_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(VALID_MODES))}")
        if not title.strip() or not objective.strip():
            raise ValueError("title and objective are required")
        now = utc_now_iso()
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        task = MissionTask(
            task_id=task_id,
            created_at=now,
            updated_at=now,
            title=title.strip(),
            objective=objective.strip(),
            mode=clean_mode,
            assignee=assignee.strip() or "chatgpt.com-agent",
            context=context.strip(),
            acceptance_criteria=[item.strip() for item in acceptance_criteria if item.strip()],
            status="queued",
        )
        self.tasks[task_id] = task
        self.save_state()
        return asdict(task)

    def list_tasks(self, status: str = "") -> list[dict[str, Any]]:
        rows = [asdict(item) for item in self.tasks.values()]
        rows.sort(key=lambda item: item["created_at"], reverse=True)
        if status:
            return [row for row in rows if row["status"] == status]
        return rows

    def update_task(self, task_id: str, status: str, result_summary: str = "") -> dict[str, Any]:
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError(f"unknown task_id: {task_id}")
        clean_status = status.strip()
        if clean_status not in VALID_STATUS:
            raise ValueError(f"status must be one of: {', '.join(sorted(VALID_STATUS))}")
        task.status = clean_status
        task.result_summary = result_summary.strip()
        task.updated_at = utc_now_iso()
        self.save_state()
        return asdict(task)

    def build_handoff_prompt(self, task_id: str) -> str:
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError(f"unknown task_id: {task_id}")
        criteria_lines = "\n".join(
            f"- {item}" for item in (task.acceptance_criteria or ["Return concrete findings and sources."])
        )
        return (
            f"Task ID: {task.task_id}\n"
            f"Mode: {task.mode}\n"
            f"Assignee: {task.assignee}\n"
            f"Title: {task.title}\n"
            f"Objective: {task.objective}\n"
            f"Context:\n{task.context or '(none)'}\n"
            f"Acceptance Criteria:\n{criteria_lines}\n\n"
            "Execution Requirements:\n"
            "- Use deep, source-grounded reasoning.\n"
            "- Return a concise plan, findings, risks, and next actions.\n"
            "- Include explicit assumptions and confidence level.\n"
        )

    def status(self) -> dict[str, Any]:
        counts = {key: 0 for key in sorted(VALID_STATUS)}
        for task in self.tasks.values():
            counts[task.status] = counts.get(task.status, 0) + 1
        return {
            "task_count": len(self.tasks),
            "status_counts": counts,
            "updated_at": utc_now_iso(),
            "note": "Mission control does not directly automate chatgpt.com sessions; it prepares auditable task packets.",
        }
