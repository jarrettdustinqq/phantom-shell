from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI(title="Phantom Shell Python Agent")


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


def _run_http_request(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a simple HTTP request to connect with external apps/APIs.

    The spec should include at least a `url`. Optional fields:
    - method: HTTP verb (default GET)
    - headers: dict of headers
    - json/body/query params depending on your target API
    """

    params = spec.get("params", {}) or {}
    url = params.get("url")
    method = (params.get("method") or "GET").upper()
    headers = params.get("headers")
    json_payload = params.get("json")
    data = params.get("data")
    timeout = params.get("timeout", 10)

    if not url:
        return {
            "tool": "http_request",
            "status": "skipped",
            "reason": "No URL provided",
            "method": method,
        }

    try:
        response = httpx.request(
            method=method,
            url=url,
            headers=headers,
            json=json_payload,
            data=data,
            timeout=timeout,
        )
        return {
            "tool": "http_request",
            "status": response.status_code,
            "method": method,
            "url": url,
            "response_preview": response.text[:1000],
            "headers": dict(response.headers),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "tool": "http_request",
            "status": "error",
            "method": method,
            "url": url,
            "error": str(exc),
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
        response = httpx.post(webhook_url, json={"text": message}, timeout=params.get("timeout", 10))
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
            "error": str(exc),
        }


def run_tools(instruction: str, context: Optional[Dict[str, Any]], tool_specs: Optional[List[Dict[str, Any]]]):
    """Extend this function with your own tooling logic.

    The default catalog includes:
    - http_request: make an HTTP call to any app/API to fetch or post data.
    - slack_webhook: send a message to Slack using an incoming webhook URL.
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

    # Provide an offline-friendly summary when no OpenAI key is configured.
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
        return response.choices[0].message.content
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
