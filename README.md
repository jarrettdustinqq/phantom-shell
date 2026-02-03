# Phantom Shell n8n AI Ecosystem

This repository provides a starter template for wiring up an n8n automation that orchestrates OpenAI models with a Python microservice acting as a tool-execution agent. The goal is to combine multiple AI assistance capabilities (planning, tool execution, result summarisation) into a cohesive flow you can import into your n8n instance.

## Components

- **n8n Workflow (`workflows/ai-ecosystem.json`)**: An importable workflow that connects a webhook trigger to OpenAI for intent parsing, routes tasks to a Python agent for tool execution, and sends a summarised result back to the caller.
- **Python Agent (`agent.py`)**: A lightweight FastAPI service that can be invoked from n8n to run custom Python tooling and call OpenAI. Extend this file with your own tools or retrieval logic.
- **OpenAI Integration**: The workflow uses n8n's built-in OpenAI node for orchestration and the Python agent uses the `openai` Python SDK for downstream calls (e.g., function/tool calling, long-form responses).

## Prerequisites

- Python 3.10+
- n8n (self-hosted or cloud) with access to the OpenAI node
- An OpenAI API key with access to the models you need (update `model` fields as desired)

Install Python dependencies locally:

```bash
pip install -r requirements.txt
```

Run the fast checks locally:

```bash
pytest
```

## Running the Python Agent

1. Export your OpenAI key:
   ```bash
   export OPENAI_API_KEY=sk-...
   ```
2. Start the service (falls back to an offline summary if no key is configured):
   ```bash
   uvicorn agent:app --host 0.0.0.0 --port 5000
   ```
3. The agent will expose `POST /agent` for task execution. The n8n workflow is configured to call `http://host.docker.internal:5000/agent` (adjust to match your deployment).

You can also run the service directly with Python:

```bash
python agent.py  # listens on 0.0.0.0:5000 with auto-reload
```

## Importing the n8n Workflow

1. Open n8n and create a new workflow.
2. Choose **Import from File** and select `workflows/ai-ecosystem.json`.
3. Add an **OpenAI** credential in n8n and select it in both OpenAI nodes.
4. For the **HTTP Request** node, adjust the URL to reach your Python agent (e.g., `http://localhost:5000/agent` if running n8n locally).
5. Activate the workflow and hit the webhook URL shown in the **Webhook** node to start the flow.

## How the Flow Works

1. **Webhook** receives an incoming JSON payload with `task` and optional `context`.
2. **Intent Planner (OpenAI)** interprets the task and prepares a structured request for the Python agent, including suggested tools/parameters.
3. **Python Agent (HTTP Request)** forwards the structured task to the FastAPI service (`POST /agent`) where custom Python tools can run and where another OpenAI call can be made if needed.
4. **Result Summariser (OpenAI)** takes the agent output and crafts a user-friendly response.
5. **Return Response (Webhook Response)** returns the summary to the caller.

## Extending the Agent

- Use the built-in tool catalog in `run_tools` to connect multiple apps without editing the workflow:
  - `http_request`: call any HTTP API (CRM, project tracker, DB proxy, webhook). Provide `params.url`, optional `params.method`, `params.headers`, `params.json`, or `params.data`.
  - `slack_webhook`: send a message to Slack using `params.webhook_url` or the `SLACK_WEBHOOK_URL` environment variable, with an optional `params.message` (defaults to the instruction text).
  - `echo`: always emitted so you can trace what the agent saw.
- Add your own functions in `run_tools` for other systems (Notion, Jira, Airtable, search, vector DBs); the n8n planner passes `tool_specs` so you can route dynamically.
- Use OpenAI's tool/function-calling in `run_openai_reasoning` to decide which tool to run based on the incoming `tool_specs`.
- Update the n8n workflow with downstream delivery nodes (e.g., Slack/Email/HTTP) after the summariser to push results to your preferred channels.

### Example `tool_specs` payloads

Add these in the webhook payload (`tool_specs`) or via the Intent Planner node response in n8n:

```json
{
  "task": "capture today’s status and post to Slack",
  "context": {"project": "alpha"},
  "tool_specs": [
    {
      "name": "http_request",
      "params": {
        "url": "https://status.internal/api/today",
        "method": "GET",
        "headers": {"Authorization": "Bearer <token>"}
      }
    },
    {
      "name": "slack_webhook",
      "params": {
        "message": "Status posted from Phantom Shell agent",
        "webhook_url": "https://hooks.slack.com/services/..."  
      }
    }
  ]
}
```

The agent will fetch data from your API, summarize it, and post the summary to Slack—all within one request.

## Security Notes

- Keep your OpenAI key secret. In production, inject it via environment variables or a secrets manager.
- Validate and sanitise any user-provided input in `agent.py` before running local tools.
- When calling external systems, enforce timeouts in both n8n and the Python agent to avoid runaway tasks.

### Safely providing your OpenAI API key

You never need to share your key with anyone else to run this stack. Follow these steps instead:

1. **Local env var (preferred):**
   ```bash
   # Do this only on your own machine/VM; never paste the key into chats or logs
   export OPENAI_API_KEY=sk-...
   ```
   The FastAPI agent reads this variable at runtime and does not log it.

2. **.env file for local dev (keep private):**
   ```bash
   echo "OPENAI_API_KEY=sk-..." > .env
   ```
   Load it with a tool like `direnv` or `python-dotenv` and ensure `.env` stays uncommitted.

3. **Docker / n8n containers:** pass the key as an environment variable or Docker secret (e.g., `-e OPENAI_API_KEY=...` or `--env-file .env`). Inside n8n, create an **OpenAI** credential rather than hard-coding the key in nodes.

4. **Rotation:** if a key is ever exposed, rotate it in the OpenAI dashboard and update the env var/secret—no code changes required.

These steps keep the key on machines you control while enabling live OpenAI responses end-to-end.

## Troubleshooting

- If the HTTP Request node cannot reach the Python agent, confirm the hostname/port and that Docker networking allows access (`host.docker.internal` works for Docker Desktop; otherwise use the agent container IP or a bridge network alias).
- For long responses, adjust `max_tokens` in the OpenAI nodes and `run_openai_reasoning`.
- Use n8n's **Execution Log** to inspect the JSON exchanged between nodes.
- Without an `OPENAI_API_KEY`, the agent returns an offline-friendly summary so you can test the full flow without an API call.
