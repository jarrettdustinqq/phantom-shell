"""Ecosystem hub for multi-agent orchestration over registered connectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from .universal_agent import UniversalAgent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EcosystemAgent:
    agent_id: str
    name: str
    role: str
    allowed_connectors: list[str]
    objective: str
    created_at: str
    updated_at: str
    enabled: bool = True


class EcosystemHub:
    """Manages agent profiles and routes their actions through UniversalAgent."""

    def __init__(
        self,
        universal_agent: UniversalAgent,
        state_path: Path,
    ) -> None:
        self.universal_agent = universal_agent
        self.state_path = state_path
        self.agents: dict[str, EcosystemAgent] = {}
        self.load_state()

    def load_state(self) -> None:
        if not self.state_path.exists():
            self.agents = {}
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        rows = payload.get("agents", [])
        self.agents = {row["agent_id"]: EcosystemAgent(**row) for row in rows}

    def save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [asdict(agent) for agent in self.agents.values()]
        rows.sort(key=lambda item: item["agent_id"])
        payload = {"updated_at": utc_now_iso(), "agents": rows}
        self.state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def status(self) -> dict[str, Any]:
        enabled = sum(1 for item in self.agents.values() if item.enabled)
        return {
            "agent_count": len(self.agents),
            "enabled_agent_count": enabled,
            "connector_count": len(self.universal_agent.list_connectors()),
            "updated_at": utc_now_iso(),
        }

    def list_agents(self) -> list[dict[str, Any]]:
        rows = [asdict(agent) for agent in self.agents.values()]
        rows.sort(key=lambda item: item["agent_id"])
        return rows

    def register_agent(
        self,
        agent_id: str,
        name: str,
        role: str,
        allowed_connectors: list[str],
        objective: str,
        enabled: bool = True,
    ) -> dict[str, Any]:
        clean_id = agent_id.strip()
        if not clean_id:
            raise ValueError("agent_id is required")
        unknown = sorted(set(allowed_connectors) - {c["connector_id"] for c in self.universal_agent.list_connectors()})
        if unknown:
            raise ValueError(f"unknown connector(s): {', '.join(unknown)}")
        now = utc_now_iso()
        row = EcosystemAgent(
            agent_id=clean_id,
            name=name.strip() or clean_id,
            role=role.strip() or "generalist",
            allowed_connectors=sorted(set(allowed_connectors)),
            objective=objective.strip(),
            created_at=now,
            updated_at=now,
            enabled=enabled,
        )
        self.agents[clean_id] = row
        self.save_state()
        return asdict(row)

    def toggle_agent(self, agent_id: str, enabled: bool) -> dict[str, Any]:
        row = self.agents.get(agent_id)
        if row is None:
            raise KeyError(f"unknown agent_id: {agent_id}")
        row.enabled = enabled
        row.updated_at = utc_now_iso()
        self.save_state()
        return asdict(row)

    def route_task(
        self,
        agent_id: str,
        connector_id: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = self.agents.get(agent_id)
        if row is None:
            raise KeyError(f"unknown agent_id: {agent_id}")
        if not row.enabled:
            raise ValueError("agent is disabled")
        if connector_id not in row.allowed_connectors:
            raise PermissionError(f"agent {agent_id} is not allowed to run connector {connector_id}")
        result = self.universal_agent.run_connector(connector_id=connector_id, payload=payload or {})
        return {
            "agent_id": agent_id,
            "connector_id": connector_id,
            "result": result,
            "routed_at": utc_now_iso(),
        }

    def run_workflow(
        self,
        agent_id: str,
        steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        outputs: list[dict[str, Any]] = []
        for step in steps:
            connector_id = str(step.get("connector_id", "")).strip()
            payload = dict(step.get("payload", {}))
            outputs.append(self.route_task(agent_id=agent_id, connector_id=connector_id, payload=payload))
        return {
            "agent_id": agent_id,
            "step_count": len(outputs),
            "outputs": outputs,
            "completed_at": utc_now_iso(),
        }

    def suggest_connectors(self, objective: str) -> list[str]:
        text = objective.lower()
        connectors = self.universal_agent.list_connectors()
        ranked: list[tuple[int, str]] = []
        for row in connectors:
            score = 0
            ctype = row.get("connector_type", "")
            caps = [str(x).lower() for x in row.get("capabilities", [])]
            if "notify" in text and "notify" in caps:
                score += 3
            if "analy" in text and ("analysis" in caps or ctype == "openai"):
                score += 3
            if ("run" in text or "execute" in text) and ctype == "shell":
                score += 2
            if "api" in text and ctype == "webhook":
                score += 2
            if row.get("enabled"):
                score += 1
            ranked.append((score, row["connector_id"]))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[1] for item in ranked if item[0] > 0][:5]
