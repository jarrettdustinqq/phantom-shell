from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import app
from fastapi.testclient import TestClient


def test_agent_offline_summary_when_no_api_key(monkeypatch):
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


def test_agent_executes_policy_checked_http_tool(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "agent.validate_outbound_url",
        lambda raw_url, *, allow_private: "https://example.com/api?token=secret",
    )

    def fake_request(method, url, headers=None, json=None, data=None, timeout=10):  # noqa: ANN001
        class Response:
            status_code = 202
            text = "synthetic response"
            headers = {
                "content-type": "text/plain",
                "set-cookie": "session=secret",
            }

        return Response()

    monkeypatch.setattr("agent.httpx.request", fake_request)

    client = TestClient(app)
    response = client.post(
        "/agent",
        json={
            "instruction": "call api",
            "tool_specs": [{"name": "http_request", "params": {"url": "https://example.com/api"}}],
        },
    )

    assert response.status_code == 200
    first_tool = response.json()["raw_tool_outputs"][0]
    assert first_tool["tool"] == "http_request"
    assert first_tool["status"] == 202
    assert first_tool["url"] == "https://example.com/api"
    assert first_tool["headers"] == {"content-type": "text/plain"}


def test_agent_blocks_unsupported_http_method(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)
    response = client.post(
        "/agent",
        json={
            "instruction": "connect",
            "tool_specs": [
                {
                    "name": "http_request",
                    "params": {"url": "https://example.com", "method": "CONNECT"},
                }
            ],
        },
    )
    output = response.json()["raw_tool_outputs"][0]
    assert output["status"] == "blocked"
    assert "Unsupported" in output["reason"]


def test_agent_slack_tool_skips_without_webhook(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

    client = TestClient(app)
    response = client.post(
        "/agent",
        json={
            "instruction": "notify",
            "tool_specs": [{"name": "slack_webhook", "params": {"message": "hello"}}],
        },
    )

    assert response.status_code == 200
    slack_output = response.json()["raw_tool_outputs"][0]
    assert slack_output["tool"] == "slack_webhook"
    assert slack_output["status"] == "skipped"
    assert "webhook" in slack_output["reason"].lower()


def test_healthcheck():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
