#!/usr/bin/env python3
"""Universal Agent dashboard with JSON API and lightweight UI."""

from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
import argparse
import json
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.autonomous_risk_triage import AutonomousRiskTriage
from phantom_shell.ecosystem_hub import EcosystemHub
from phantom_shell.universal_agent import UniversalAgent


def html_page() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Universal Agent Dashboard</title>
  <style>
    :root {
      --bg: #f2f0ea;
      --ink: #102022;
      --muted: #4f6168;
      --card: #ffffff;
      --accent: #0f766e;
      --line: #dce4e8;
    }
    body { margin: 0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif; background: linear-gradient(160deg,#f5efe6,#e5f3f6); color: var(--ink); }
    .wrap { max-width: 1080px; margin: 0 auto; padding: 24px; }
    .hero { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
    .grid { margin-top: 18px; display: grid; grid-template-columns: 1.3fr 1fr; gap: 14px; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px; box-shadow: 0 8px 24px rgba(8, 18, 26, 0.08); }
    h1, h2 { margin: 0 0 8px 0; }
    .muted { color: var(--muted); font-size: 14px; }
    label, input, select, textarea, button { width: 100%; font-size: 14px; }
    input, select, textarea { margin: 5px 0 9px 0; border: 1px solid var(--line); border-radius: 10px; padding: 8px; box-sizing: border-box; }
    button { border: 0; background: var(--accent); color: white; padding: 10px; border-radius: 10px; cursor: pointer; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 8px 6px; font-size: 13px; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    pre { background: #0a1015; color: #d5f3f0; border-radius: 10px; padding: 10px; min-height: 120px; overflow: auto; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div>
        <h1>Universal Agent Dashboard</h1>
        <div class="muted">One control plane for programs, apps, AI connectors, and tools.</div>
      </div>
      <button onclick="refresh()">Refresh</button>
    </div>
    <div class="grid">
      <div class="card">
        <h2>Connectors</h2>
        <table id="connectorTable">
          <thead><tr><th>ID</th><th>Type</th><th>Enabled</th><th>Health</th><th>Action</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
      <div class="card">
        <h2>Status</h2>
        <pre id="statusOut"></pre>
      </div>
      <div class="card">
        <h2>Register Connector</h2>
        <div class="row">
          <div><label>ID</label><input id="id" placeholder="github_cli" /></div>
          <div><label>Name</label><input id="name" placeholder="GitHub CLI" /></div>
        </div>
        <div class="row">
          <div>
            <label>Type</label>
            <select id="ctype">
              <option>shell</option><option>webhook</option><option>openai</option><option>mcp</option><option>custom</option>
            </select>
          </div>
          <div><label>Enabled</label><select id="enabled"><option value="true">true</option><option value="false">false</option></select></div>
        </div>
        <label>Capabilities (comma separated)</label>
        <input id="caps" placeholder="chat,analysis,deploy" />
        <label>Config JSON</label>
        <textarea id="cfg" rows="5">{}</textarea>
        <button onclick="registerConnector()">Register</button>
      </div>
      <div class="card">
        <h2>Run Connector</h2>
        <label>Connector ID</label><input id="runId" />
        <label>Payload JSON</label><textarea id="payload" rows="5">{}</textarea>
        <div class="row">
          <button onclick="runConnector()">Run</button>
          <button onclick="healthConnector()">Health Check</button>
        </div>
        <label>Toggle Connector</label>
        <div class="row">
          <input id="toggleId" placeholder="connector id" />
          <select id="toggleEnabled"><option value="true">enable</option><option value="false">disable</option></select>
        </div>
        <button onclick="toggleConnector()">Apply Toggle</button>
      </div>
      <div class="card" style="grid-column: 1 / -1;">
        <h2>Output</h2>
        <pre id="out"></pre>
      </div>
      <div class="card" style="grid-column: 1 / -1;">
        <h2>Autonomous Risk Triage</h2>
        <table id="triageTable">
          <thead><tr><th>Event</th><th>Severity</th><th>Action</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>
<script>
async function api(path, method="GET", body=null){
  const init = { method, headers: {"Content-Type":"application/json"} };
  if (body) init.body = JSON.stringify(body);
  const r = await fetch(path, init);
  const data = await r.json();
  if(!r.ok){ throw new Error(JSON.stringify(data)); }
  return data;
}
function renderConnectors(rows){
  const tbody = document.querySelector("#connectorTable tbody");
  tbody.innerHTML = "";
  rows.forEach(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${row.connector_id}</td><td>${row.connector_type}</td><td>${row.enabled}</td><td>${row.last_health}</td><td><button onclick="quickRun('${row.connector_id}')">Run</button></td>`;
    tbody.appendChild(tr);
  });
}
function renderTriage(rows){
  const tbody = document.querySelector("#triageTable tbody");
  tbody.innerHTML = "";
  rows.forEach(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${row.message}</td><td>${row.severity}</td><td><button onclick="mitigateEvent('${row.event_id}')">Mitigate</button></td>`;
    tbody.appendChild(tr);
  });
}
async function refresh(){
  const status = await api("/api/status");
  const connectors = await api("/api/connectors");
  document.getElementById("statusOut").textContent = JSON.stringify(status, null, 2);
  renderConnectors(connectors.connectors);
  const triage = await api("/api/triage");
  renderTriage(triage.events.slice(0, 5));
}
async function registerConnector(){
  const body = {
    connector_id: document.getElementById("id").value.trim(),
    name: document.getElementById("name").value.trim(),
    connector_type: document.getElementById("ctype").value,
    enabled: document.getElementById("enabled").value === "true",
    capabilities: document.getElementById("caps").value.split(",").map(x=>x.trim()).filter(Boolean),
    config: JSON.parse(document.getElementById("cfg").value || "{}")
  };
  const data = await api("/api/connectors/register", "POST", body);
  document.getElementById("out").textContent = JSON.stringify(data, null, 2);
  await refresh();
}
async function runConnector(){
  const body = { connector_id: document.getElementById("runId").value.trim(), payload: JSON.parse(document.getElementById("payload").value || "{}") };
  const data = await api("/api/connectors/run", "POST", body);
  document.getElementById("out").textContent = JSON.stringify(data, null, 2);
  await refresh();
}
async function quickRun(connectorId){
  const data = await api("/api/connectors/run", "POST", { connector_id: connectorId, payload: {} });
  document.getElementById("out").textContent = JSON.stringify(data, null, 2);
  await refresh();
}
async function healthConnector(){
  const body = { connector_id: document.getElementById("runId").value.trim() };
  const data = await api("/api/connectors/health", "POST", body);
  document.getElementById("out").textContent = JSON.stringify(data, null, 2);
  await refresh();
}
async function toggleConnector(){
  const body = {
    connector_id: document.getElementById("toggleId").value.trim(),
    enabled: document.getElementById("toggleEnabled").value === "true"
  };
  const data = await api("/api/connectors/toggle", "POST", body);
  document.getElementById("out").textContent = JSON.stringify(data, null, 2);
  await refresh();
}
async function mitigateEvent(eventId){
  const data = await api("/api/triage/mitigate", "POST", { event_id: eventId });
  document.getElementById("out").textContent = JSON.stringify(data, null, 2);
}
refresh().catch(err => document.getElementById("out").textContent = String(err));
</script>
</body>
</html>
"""


def json_response(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def page_response(handler: BaseHTTPRequestHandler, text: str) -> None:
    raw = text.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json body: {exc}") from exc


def build_handler(agent: UniversalAgent, hub: EcosystemHub, triage: AutonomousRiskTriage) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/":
                page_response(self, html_page())
                return
            if self.path == "/api/status":
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "status": {
                            "universal_agent": agent.status(),
                            "ecosystem_hub": hub.status(),
                        },
                    },
                )
                return
            if self.path == "/api/connectors":
                json_response(self, 200, {"ok": True, "connectors": agent.list_connectors()})
                return
            if self.path == "/api/agents":
                json_response(self, 200, {"ok": True, "agents": hub.list_agents()})
                return
            if self.path == "/api/triage":
                report = triage.build_report()
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "events": report["events"],
                        "actions": report["actions"],
                    },
                )
                return
            json_response(self, 404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = read_json(self)
                if self.path == "/api/connectors/register":
                    row = agent.register_connector(
                        connector_id=str(payload.get("connector_id", "")),
                        name=str(payload.get("name", "")),
                        connector_type=str(payload.get("connector_type", "")),
                        capabilities=list(payload.get("capabilities", [])),
                        config=dict(payload.get("config", {})),
                        enabled=bool(payload.get("enabled", True)),
                    )
                    json_response(self, 200, {"ok": True, "connector": row})
                    return
                if self.path == "/api/connectors/toggle":
                    row = agent.toggle_connector(
                        connector_id=str(payload.get("connector_id", "")),
                        enabled=bool(payload.get("enabled", True)),
                    )
                    json_response(self, 200, {"ok": True, "connector": row})
                    return
                if self.path == "/api/connectors/run":
                    result = agent.run_connector(
                        connector_id=str(payload.get("connector_id", "")),
                        payload=dict(payload.get("payload", {})),
                    )
                    json_response(self, 200, {"ok": True, "result": result})
                    return
                if self.path == "/api/connectors/health":
                    result = agent.health_check(connector_id=str(payload.get("connector_id", "")))
                    json_response(self, 200, {"ok": True, "result": result})
                    return
                if self.path == "/api/agents/register":
                    row = hub.register_agent(
                        agent_id=str(payload.get("agent_id", "")),
                        name=str(payload.get("name", "")),
                        role=str(payload.get("role", "")),
                        allowed_connectors=list(payload.get("allowed_connectors", [])),
                        objective=str(payload.get("objective", "")),
                        enabled=bool(payload.get("enabled", True)),
                    )
                    json_response(self, 200, {"ok": True, "agent": row})
                    return
                if self.path == "/api/agents/toggle":
                    row = hub.toggle_agent(
                        agent_id=str(payload.get("agent_id", "")),
                        enabled=bool(payload.get("enabled", True)),
                    )
                    json_response(self, 200, {"ok": True, "agent": row})
                    return
                if self.path == "/api/agents/suggest":
                    objective = str(payload.get("objective", ""))
                    json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "objective": objective,
                            "suggested_connectors": hub.suggest_connectors(objective),
                        },
                    )
                    return
                if self.path == "/api/agents/route":
                    result = hub.route_task(
                        agent_id=str(payload.get("agent_id", "")),
                        connector_id=str(payload.get("connector_id", "")),
                        payload=dict(payload.get("payload", {})),
                    )
                    json_response(self, 200, {"ok": True, "result": result})
                    return
                if self.path == "/api/agents/workflow":
                    result = hub.run_workflow(
                        agent_id=str(payload.get("agent_id", "")),
                        steps=list(payload.get("steps", [])),
                    )
                    json_response(self, 200, {"ok": True, "result": result})
                    return
                if self.path == "/api/triage/mitigate":
                    event_id = str(payload.get("event_id", ""))
                    event = triage.find_event(event_id)
                    if event is None:
                        json_response(self, 404, {"ok": False, "error": "event_id not found"})
                        return
                    action = triage.suggest_action(event)
                    json_response(self, 200, {"ok": True, "mitigation": asdict(action)})
                    return
                json_response(self, 404, {"ok": False, "error": "not found"})
            except Exception as exc:  # noqa: BLE001
                json_response(self, 400, {"ok": False, "error": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal Agent dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--state-path", default=".loop-agent/universal-agent-state.json")
    parser.add_argument("--audit-log", default="logs/universal_agent_audit.log")
    parser.add_argument("--hub-state", default=".loop-agent/ecosystem-hub-state.json")
    args = parser.parse_args()

    agent = UniversalAgent(
        state_path=Path(args.state_path),
        audit_log_path=Path(args.audit_log),
    )
    hub = EcosystemHub(
        universal_agent=agent,
        state_path=Path(args.hub_state),
    )
    triage = AutonomousRiskTriage(
        state_dir=Path(args.state_path).parent,
        log_path=Path(args.audit_log),
    )
    handler = build_handler(agent, hub, triage)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"universal-agent-dashboard listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
