"""Universal agent with connector registry and metadata-only audit logging."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request


CONNECTOR_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
SUPPORTED_CONNECTOR_TYPES = {
    "shell",
    "webhook",
    "openai",
    "mcp",
    "custom",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


@dataclass
class Connector:
    connector_id: str
    name: str
    connector_type: str
    enabled: bool
    capabilities: list[str]
    config: dict[str, str]
    created_at: str
    updated_at: str
    last_health: str = "unknown"
    last_error: str = ""


class UniversalAgent:
    """Stateful connector orchestrator with conservative execution rules."""

    def __init__(self, state_path: Path, audit_log_path: Path) -> None:
        self.state_path = state_path
        self.audit_log_path = audit_log_path
        self.connectors: dict[str, Connector] = {}
        self.load_state()

    def load_state(self) -> None:
        if not self.state_path.exists():
            self.connectors = {}
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        rows = payload.get("connectors", [])
        self.connectors = {row["connector_id"]: Connector(**row) for row in rows}

    def save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [asdict(item) for item in self.connectors.values()]
        rows.sort(key=lambda item: item["connector_id"])
        payload = {"updated_at": utc_now_iso(), "connectors": rows}
        self.state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _append_audit(
        self,
        action: str,
        connector_id: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts_utc": utc_now_iso(),
            "action": action,
            "connector_id": connector_id,
            "status": status,
            "details": details or {},
        }
        with self.audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")

    def _validate_connector(self, connector: Connector) -> None:
        if not CONNECTOR_ID_RE.match(connector.connector_id):
            raise ValueError("connector_id must match ^[a-z0-9][a-z0-9_-]{1,63}$")
        if connector.connector_type not in SUPPORTED_CONNECTOR_TYPES:
            raise ValueError(f"unsupported connector_type: {connector.connector_type}")

    def list_connectors(self) -> list[dict[str, Any]]:
        rows = []
        for connector in sorted(self.connectors.values(), key=lambda item: item.connector_id):
            rows.append(asdict(connector))
        return rows

    def status(self) -> dict[str, Any]:
        enabled = sum(1 for item in self.connectors.values() if item.enabled)
        unhealthy = sum(1 for item in self.connectors.values() if item.last_health == "unhealthy")
        return {
            "connector_count": len(self.connectors),
            "enabled_count": enabled,
            "unhealthy_count": unhealthy,
            "supported_connector_types": sorted(SUPPORTED_CONNECTOR_TYPES),
            "updated_at": utc_now_iso(),
        }

    def register_connector(
        self,
        connector_id: str,
        name: str,
        connector_type: str,
        capabilities: list[str] | None = None,
        config: dict[str, str] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        connector = Connector(
            connector_id=connector_id.strip(),
            name=name.strip() or connector_id.strip(),
            connector_type=connector_type.strip(),
            enabled=enabled,
            capabilities=list(capabilities or []),
            config=dict(config or {}),
            created_at=now,
            updated_at=now,
        )
        self._validate_connector(connector)
        self.connectors[connector.connector_id] = connector
        self.save_state()
        self._append_audit(
            action="register",
            connector_id=connector.connector_id,
            status="ok",
            details={"connector_type": connector.connector_type, "enabled": connector.enabled},
        )
        return asdict(connector)

    def toggle_connector(self, connector_id: str, enabled: bool) -> dict[str, Any]:
        connector = self.connectors.get(connector_id)
        if connector is None:
            raise KeyError(f"unknown connector_id: {connector_id}")
        connector.enabled = enabled
        connector.updated_at = utc_now_iso()
        self.save_state()
        self._append_audit(
            action="toggle",
            connector_id=connector_id,
            status="ok",
            details={"enabled": enabled},
        )
        return asdict(connector)

    def _run_shell_connector(self, connector: Connector, payload: dict[str, Any]) -> dict[str, Any]:
        command = connector.config.get("command", "").strip()
        if not command:
            raise ValueError("shell connector missing config.command")
        timeout = int(connector.config.get("timeout_seconds", "20"))
        extra_arg = str(payload.get("arg", "")).strip()
        if extra_arg:
            command = f"{command} {extra_arg}"
        result = subprocess.run(
            ["bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "exit_code": result.returncode,
            "stdout_preview": result.stdout[:500],
            "stderr_preview": result.stderr[:500],
            "status": "ok" if result.returncode == 0 else "error",
        }

    def _run_webhook_connector(
        self, connector: Connector, payload: dict[str, Any]
    ) -> dict[str, Any]:
        url = connector.config.get("url", "").strip()
        method = connector.config.get("method", "POST").upper()
        if not url:
            raise ValueError("webhook connector missing config.url")
        body = json.dumps(payload or {}, ensure_ascii=True).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            method=method,
            data=body if method in {"POST", "PUT", "PATCH"} else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read(300)
                return {
                    "http_status": response.status,
                    "response_preview": data.decode("utf-8", errors="replace"),
                    "status": "ok" if 200 <= response.status < 300 else "error",
                }
        except urllib.error.URLError as exc:
            return {"status": "error", "error": str(exc)}

    def _run_soft_connector(self, connector: Connector) -> dict[str, Any]:
        if connector.connector_type == "openai":
            configured = bool(os.getenv("OPENAI_API_KEY"))
            return {"status": "ok" if configured else "error", "configured": configured}
        if connector.connector_type == "mcp":
            endpoint = connector.config.get("endpoint", "").strip()
            return {"status": "ok" if endpoint else "error", "endpoint_set": bool(endpoint)}
        return {"status": "ok", "note": "custom connector placeholder"}

    def run_connector(self, connector_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        connector = self.connectors.get(connector_id)
        if connector is None:
            raise KeyError(f"unknown connector_id: {connector_id}")
        if not connector.enabled:
            raise ValueError("connector is disabled")
        payload = payload or {}
        start = time.time()
        response: dict[str, Any]
        if connector.connector_type == "shell":
            response = self._run_shell_connector(connector, payload)
        elif connector.connector_type == "webhook":
            response = self._run_webhook_connector(connector, payload)
        else:
            response = self._run_soft_connector(connector)
        duration_ms = int((time.time() - start) * 1000)
        connector.updated_at = utc_now_iso()
        if response.get("status") == "ok":
            connector.last_health = "healthy"
            connector.last_error = ""
        else:
            connector.last_health = "unhealthy"
            connector.last_error = str(response.get("error", "connector execution failed"))
        self.save_state()
        self._append_audit(
            action="run",
            connector_id=connector_id,
            status=response.get("status", "unknown"),
            details={
                "duration_ms": duration_ms,
                "payload_hash": _hash_text(json.dumps(payload, ensure_ascii=True, sort_keys=True)),
            },
        )
        return {
            "connector_id": connector_id,
            "connector_type": connector.connector_type,
            "duration_ms": duration_ms,
            "result": response,
        }

    def health_check(self, connector_id: str) -> dict[str, Any]:
        connector = self.connectors.get(connector_id)
        if connector is None:
            raise KeyError(f"unknown connector_id: {connector_id}")
        if connector.connector_type == "shell":
            command = connector.config.get("health_command") or connector.config.get("command", "")
            status = "healthy"
            error = ""
            if command:
                result = subprocess.run(
                    ["bash", "-lc", command],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if result.returncode != 0:
                    status = "unhealthy"
                    error = (result.stderr or result.stdout).strip()[:200]
            connector.last_health = status
            connector.last_error = error
        elif connector.connector_type == "webhook":
            response = self._run_webhook_connector(connector, {"health_check": True})
            connector.last_health = "healthy" if response.get("status") == "ok" else "unhealthy"
            connector.last_error = str(response.get("error", ""))[:200]
        else:
            soft = self._run_soft_connector(connector)
            connector.last_health = "healthy" if soft.get("status") == "ok" else "unhealthy"
            connector.last_error = "" if connector.last_health == "healthy" else "missing configuration"
        connector.updated_at = utc_now_iso()
        self.save_state()
        self._append_audit(
            action="health_check",
            connector_id=connector_id,
            status=connector.last_health,
            details={},
        )
        return {
            "connector_id": connector_id,
            "health": connector.last_health,
            "error": connector.last_error,
            "updated_at": connector.updated_at,
        }
