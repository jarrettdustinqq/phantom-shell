#!/usr/bin/env bash
set -euo pipefail

host="${HOST:-127.0.0.1}"
port="${PORT:-8787}"
base_url="http://${host}:${port}"

api_post() {
  local path="$1"
  local body="$2"
  curl -sS -X POST "${base_url}${path}" \
    -H "Content-Type: application/json" \
    -d "${body}"
}

pretty_json() {
  python3 -m json.tool
}

echo "Bootstrapping ecosystem agents against ${base_url} ..."

api_post "/api/agents/register" '{
  "agent_id":"ops_commander",
  "name":"Ops Commander",
  "role":"operations",
  "allowed_connectors":["shell_readonly_health"],
  "objective":"Operate health checks and safe diagnostics",
  "enabled":true
}' | pretty_json

api_post "/api/agents/register" '{
  "agent_id":"integration_broker",
  "name":"Integration Broker",
  "role":"integration",
  "allowed_connectors":["webhook_staging_template"],
  "objective":"Route external app events through vetted webhooks",
  "enabled":false
}' | pretty_json

api_post "/api/agents/register" '{
  "agent_id":"ai_analyst",
  "name":"AI Analyst",
  "role":"analysis",
  "allowed_connectors":["ai_openai_template"],
  "objective":"Perform structured analysis tasks and summaries",
  "enabled":false
}' | pretty_json

echo "Current agents:"
curl -sS "${base_url}/api/agents" | pretty_json
