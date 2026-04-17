from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import app
from fastapi.testclient import TestClient


def test_agent_offline_summary_when_no_api_key(monkeypatch):
    # Ensure we operate without an OpenAI key so offline mode is exercised.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = TestClient(app)
    response = client.post(
        "/agent",
        json={"instruction": "demo instruction", "context": {"foo": "bar"}},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["raw_tool_outputs"][0]["tool"] == "echo"
    assert "offline summary" in payload["result"].lower()
    assert "demo instruction" in payload["result"]
    assert "OPENAI_API_KEY" in payload["result"]


def test_agent_executes_http_tool(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Avoid real network calls during tests.
    def fake_request(method, url, headers=None, json=None, data=None, timeout=10):  # noqa: ANN001
        class Response:  # pragma: no cover - simple stub
            status_code = 202
            text = "synthetic response"
            headers = {"x-test": "1"}

        return Response()

    monkeypatch.setattr("agent.httpx.request", fake_request)

    client = TestClient(app)
    response = client.post(
        "/agent",
        json={
            "instruction": "call api",
            "tool_specs": [{"name": "http_request", "params": {"url": "https://example.com"}}],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    first_tool = payload["raw_tool_outputs"][0]
    assert first_tool["tool"] == "http_request"
    assert first_tool["status"] == 202


def test_agent_slack_tool_skips_without_webhook(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    client = TestClient(app)
    response = client.post(
        "/agent",
        json={
            "instruction": "notify", "tool_specs": [{"name": "slack_webhook", "params": {"message": "hello"}}]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    slack_output = payload["raw_tool_outputs"][0]

    assert slack_output["tool"] == "slack_webhook"
    assert slack_output["status"] == "skipped"
    assert "webhook" in slack_output["reason"].lower()


def test_healthcheck():
    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
