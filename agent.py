from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel

from phantom_shell.http_policy import (
    URLPolicyError,
    bounded_timeout,
    safe_display_url,
    safe_response_headers,
    validate_outbound_url,
)

app = FastAPI(title="Phantom Shell Python Agent")
ALLOWED_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}
MAX_RESPONSE_PREVIEW_BYTES = 1000


def _get_openai_client() -> Optional[OpenAI]:
    """Return an OpenAI client if a key is configured, otherwise None."""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    return OpenAI(api_key=api_key)


class AgentRequest(BaseModel):
    instruction: str
    context: Optional[Dict[str, Any]] = None
    tool_specs: Optional[List[Dict[str, Any]]] = None


class AgentResponse(BaseModel):
    result: str
    raw_tool_outputs: Optional[List[Dict[str, Any]]] = None


def _private_targets_allowed() -> bool:
    return os.getenv("PHANTOM_ALLOW_PRIVATE_HTTP_TARGETS") == "1"


def _network_error_name(exc: Exception) -> str:
    """Return a diagnostic error class without echoing URL/header secrets."""

    return type(exc).__name__


def _run_http_request(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a policy-preflighted HTTP request to an external HTTPS API."""

    params = spec.get("params", {}) or {}
    raw_url = params.get("url")
    method = str(params.get("method") or "GET").upper()
    headers = params.get("headers")
    json_payload = params.get("json")
    data = params.get("data")

    if not raw_url:
        return {
            "tool": "http_request",
            "status": "skipped",
            "reason": "No URL provided",
            "method": method,
        }

    if method not in ALLOWED_HTTP_METHODS:
        return {
            "tool": "http_request",
            "status": "blocked",
            "reason": f"Unsupported HTTP method: {method}",
            "method": method,
        }

    try:
        url = validate_outbound_url(str(raw_url), allow_private=_private_targets_allowed())
    except URLPolicyError as exc:
        return {
            "tool": "http_request",
            "status": "blocked",
            "reason": str(exc),
            "method": method,
        }

    timeout = bounded_timeout(params.get("timeout", 10))
    display_url = safe_display_url(url)

    try:
        with httpx.stream(
            method=method,
            url=url,
            headers=headers,
            json=json_payload,
            data=data,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as response:
            preview = bytearray()
            truncated = False
            for chunk in response.iter_raw():
                remaining = MAX_RESPONSE_PREVIEW_BYTES - len(preview)
                if len(chunk) > remaining:
                    preview.extend(chunk[:remaining])
                    truncated = True
                    break
                preview.extend(chunk)
                if len(preview) == MAX_RESPONSE_PREVIEW_BYTES:
                    truncated = True
                    break

            status_code = response.status_code
            response_headers = safe_response_headers(response.headers)

        return {
            "tool": "http_request",
            "status": status_code,
            "method": method,
            "url": display_url,
            "response_preview": bytes(preview).decode("utf-8", errors="replace"),
            "response_truncated": truncated,
            "headers": response_headers,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "tool": "http_request",
            "status": "error",
            "method": method,
            "url": display_url,
            "error": _network_error_name(exc),
        }


def _run_slack_webhook(spec: Dict[str, Any], default_message: str) -> Dict[str, Any]:
    """Send a message to Slack via an incoming webhook if configured."""

    params = spec.get("params", {}) or {}
    webhook_url = params.get("webhook_url") or os.getenv("SLACK_WEBHOOK_URL")
    message = params.get("message") or default_message

    if not webhook_url:
        return {
            "tool": "slack_webhook",
            "status": "skipped",
            "reason": "No webhook URL provided; set SLACK_WEBHOOK_URL or pass params.webhook_url",
            "message": message,
        }

    try:
        safe_webhook_url = validate_outbound_url(str(webhook_url), allow_private=_private_targets_allowed())
    except URLPolicyError as exc:
        return {
            "tool": "slack_webhook",
            "status": "blocked",
            "reason": str(exc),
            "message": message,
        }

    try:
        response = httpx.post(
            safe_webhook_url,
            json={"text": message},
            timeout=bounded_timeout(params.get("timeout", 10)),
            follow_redirects=False,
            trust_env=False,
        )
        return {
            "tool": "slack_webhook",
            "status": response.status_code,
            "message": message,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "tool": "slack_webhook",
            "status": "error",
            "message": message,
            "error": _network_error_name(exc),
        }


def run_tools(instruction: str, context: Optional[Dict[str, Any]], tool_specs: Optional[List[Dict[str, Any]]]):
    """Extend this function with your own tooling logic.

    The default catalog includes:
    - http_request: make an HTTP call to an external HTTPS app/API after policy preflight.
    - slack_webhook: send a message to Slack using an incoming webhook URL after policy preflight.
    - echo: always present to reflect the instruction/context for tracing.
    """

    outputs: List[Dict[str, Any]] = []
    specs = tool_specs or []

    if not specs:
        specs = [{"name": "echo", "params": {}}]

    for spec in specs:
        name = (spec.get("name") or "").lower()
        if name == "http_request":
            outputs.append(_run_http_request(spec))
        elif name == "slack_webhook":
            outputs.append(_run_slack_webhook(spec, default_message=instruction))
        else:
            outputs.append(
                {
                    "tool": "echo",
                    "instruction": instruction,
                    "context": context or {},
                    "tool_specs": tool_specs or [],
                }
            )

    return outputs


def run_openai_reasoning(instruction: str, tool_outputs: List[Dict[str, Any]]) -> str:
    """Use OpenAI to produce a consolidated answer and next-step guidance."""

    client = _get_openai_client()

    if client is None:
        summary_lines = [
            "OpenAI key not set – returning offline summary.",
            f"Instruction: {instruction}",
            f"Observed tool outputs ({len(tool_outputs)}): {tool_outputs}",
            "Set an OPENAI_API_KEY environment variable (or .env secret) locally to enable live reasoning.",
        ]
        return "\n".join(summary_lines)

    messages = [
        {
            "role": "system",
            "content": "You are a senior orchestrator that summarises tool outputs and recommends the next action.",
        },
        {
            "role": "user",
            "content": f"Instruction: {instruction}\n\nTool outputs: {tool_outputs}",
        },
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=300,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        fallback_lines = [
            "OpenAI call failed – returning offline summary.",
            f"Reason: {exc}",
            f"Instruction: {instruction}",
            f"Observed tool outputs ({len(tool_outputs)}): {tool_outputs}",
            "Verify your OPENAI_API_KEY is set locally and that networking allows access to the OpenAI endpoint.",
        ]
        return "\n".join(fallback_lines)


@app.post("/agent", response_model=AgentResponse)
async def execute_agent(request: AgentRequest):
    if not request.instruction:
        raise HTTPException(status_code=400, detail="Instruction is required")

    tool_outputs = run_tools(request.instruction, request.context, request.tool_specs)
    reasoning = run_openai_reasoning(request.instruction, tool_outputs)

    return AgentResponse(result=reasoning, raw_tool_outputs=tool_outputs)


@app.get("/healthz")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        reload=True,
    )
