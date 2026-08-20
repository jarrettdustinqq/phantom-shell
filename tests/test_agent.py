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
    seen = {}

    def fake_stream(
        method,
        url,
        headers=None,
        json=None,
        data=None,
        timeout=10,
        follow_redirects=True,
        trust_env=True,
    ):  # noqa: ANN001
        seen.update(
            method=method,
            url=url,
            timeout=timeout,
            follow_redirects=follow_redirects,
            trust_env=trust_env,
        )

        class Response:
            status_code = 202
            headers = {
                "content-type": "text/plain",
                "set-cookie": "session=secret",
            }

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):  # noqa: ANN001
                return False

            def iter_raw(self):
                yield b"synthetic response"

        return Response()

    monkeypatch.setattr("agent.httpx.stream", fake_stream)

    client = TestClient(app)
    response = client.post(
        "/agent",
        json={
            "instruction": "call api",
            "tool_specs": [
                {
                    "name": "http_request",
                    "params": {"url": "https://example.com/api", "timeout": 500},
                }
            ],
        },
    )

    assert response.status_code == 200
    first_tool = response.json()["raw_tool_outputs"][0]
    assert first_tool["tool"] == "http_request"
    assert first_tool["status"] == 202
    assert first_tool["url"] == "https://example.com/api"
    assert first_tool["response_preview"] == "synthetic response"
    assert first_tool["response_truncated"] is False
    assert first_tool["headers"] == {"content-type": "text/plain"}
    assert seen["timeout"] == 30.0
    assert seen["follow_redirects"] is False
    assert seen["trust_env"] is False


def test_agent_stops_reading_oversized_http_response(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "agent.validate_outbound_url",
        lambda raw_url, *, allow_private: "https://example.com/large",
    )
    chunks_read = []

    class Response:
        status_code = 200
        headers = {"content-type": "application/octet-stream"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):  # noqa: ANN001
            return False

        def iter_raw(self):
            for chunk in (b"a" * 700, b"b" * 700, b"unreachable"):
                chunks_read.append(len(chunk))
                yield chunk

    monkeypatch.setattr("agent.httpx.stream", lambda **kwargs: Response())

    client = TestClient(app)
    response = client.post(
        "/agent",
        json={
            "instruction": "read bounded response",
            "tool_specs": [
                {"name": "http_request", "params": {"url": "https://example.com/large"}}
            ],
        },
    )

    assert response.status_code == 200
    output = response.json()["raw_tool_outputs"][0]
    assert len(output["response_preview"].encode("utf-8")) == 1000
    assert output["response_preview"] == ("a" * 700) + ("b" * 300)
    assert output["response_truncated"] is True
    assert chunks_read == [700, 700]


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


def test_agent_blocks_loopback_http_target(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PHANTOM_ALLOW_PRIVATE_HTTP_TARGETS", raising=False)
    client = TestClient(app)
    response = client.post(
        "/agent",
        json={
            "instruction": "read local service",
            "tool_specs": [
                {"name": "http_request", "params": {"url": "https://127.0.0.1/admin"}}
            ],
        },
    )
    output = response.json()["raw_tool_outputs"][0]
    assert output["status"] == "blocked"
    assert "private" in output["reason"].lower()


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
