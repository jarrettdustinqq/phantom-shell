# Autonomous AI Ecosystem Plan

## Goal
Build a resilient, multi-app autonomous workflow that:
- Launches actions directly in your IDE (Windsurf), terminal, and browser.
- Self-heals when protocol handlers or extensions fail.
- Orchestrates tasks across services with clear observability and fallback paths.

---

# Quick Start: Get Everything Connected (Checklist)

> Complete these in order. Each step either confirms connectivity or installs a missing bridge.

## 0) One-command bootstrap (optional, recommended)
Run the bootstrap script to install local prerequisites (curl/git/task runner/Playwright):
```bash
./scripts/setup_ecosystem.sh
```

## 1) Core runtime (required)
- [ ] **OS + IDE**: Install and open **Windsurf IDE**.
- [ ] **Extension**: Install/enable the **OpenAI/ChatGPT extension** inside Windsurf.
- [ ] **Protocol handler**: Verify `windsurf:` links open the IDE (not a blank page).
  - If this fails, use the fallback matrix below.

## 2) Terminal automation (required)
- [ ] Pick a task runner: **`just`** (recommended) or **Makefile**.
- [ ] Create a single entrypoint task: `just run` or `make run`.
- [ ] Ensure your agent can run the task from the repo root.

## 3) Browser automation (required)
- [ ] Install Playwright (or confirm it’s already available).
- [ ] Confirm you can run a scripted login for one target web app.

## 4) Knowledge base (recommended)
- [ ] Choose a docs system: **Notion** or **Google Docs**.
- [ ] Create a “Runbook” doc with login steps, key URLs, and recovery paths.

## 5) Tasks + calendar (recommended)
- [ ] Pick a task system: **Linear**, **Jira**, or **Todoist**.
- [ ] Connect your calendar (Google Calendar) for scheduled runs.

## 6) Observability (recommended)
- [ ] Set up a shared log: **Notion table**, **Google Sheet**, or **Datadog**.
- [ ] Log every connector failure with timestamp and recovery action.

---

# Step-by-Step Connection Guide

## A) IDE Deep Links (Windsurf)
1. Install Windsurf IDE and open it once.
2. Install/enable the OpenAI/ChatGPT extension in Windsurf.
3. Test the protocol handler by opening a `windsurf:` link.
4. If it opens a blank page, **register the handler** by reinstalling the extension
   or using the OS “Open with” dialog to associate `windsurf:` with Windsurf.

### Fallbacks
- Primary: `windsurf:`
- Secondary: `vscode:` (if VS Code is installed)
- Tertiary: web IDE

### User-friendly handoff (copy/paste)
1. **Open Windsurf** once so the OS registers it.
2. **Install the OpenAI/ChatGPT extension** from the Windsurf marketplace.
3. Click a `windsurf:` link. If it opens a blank tab, re-open the IDE and retry.
4. If it still fails, install VS Code and use `vscode:` as a fallback.

## B) Terminal Task Runner
1. Add a `justfile` or `Makefile` with a single command entrypoint.
2. Require that all automation flows call **only** that entrypoint.

### User-friendly handoff (copy/paste)
```bash
cat <<'EOF' > justfile
run:
\t@echo \"Run your primary automation entrypoint here\"
EOF
```

## C) Browser Automation (Playwright)
1. Install Playwright.
2. Create a login script for your most critical web app.
3. Store cookies/session tokens securely (avoid hardcoding).

### User-friendly handoff (copy/paste)
```bash
python3 -m playwright install
```

## D) Docs + Knowledge Base
1. Create a runbook.
2. Add a “Recovery” section for each connector.
3. Link the runbook from your orchestrator.

## E) Tasks + Calendar
1. Add a “Recurring Runs” schedule.
2. Link tasks to runbook steps and connector status.

## F) Observability
1. Create a logging endpoint (sheet/table/api).
2. Log all protocol failures and fallback usage.

---

# Architecture Overview
- **Orchestrator Agent**: Central brain that coordinates tasks and routes actions to tools.
- **Connectors**: Bridges to apps (IDE, terminal, browser, docs, tasks, calendar).
- **Health & Observability**: Monitors link handlers, extensions, auth status, and logs.
- **Fallbacks**: Auto-switch when a connector fails (e.g., `windsurf:` → `vscode:` → web IDE).

---

# Recommended Workflow (Phased)

## Phase 1 — Baseline Integration
1. **IDE Deep Link Handling**
   - Register and validate `windsurf:` handler.
   - Add `vscode:` as fallback when Windsurf is unavailable.
2. **Terminal Automation**
   - Standardize on a task runner (Makefile or `just` recommended).
   - Add a single “run task” entrypoint for automation.
3. **Browser Actions**
   - Use a browser automation layer (Playwright) for deterministic UI workflows.

## Phase 2 — Autonomous Reliability
1. **Health Checks**
   - Confirm protocol handlers are registered and active.
   - Verify IDE extension state before routing requests.
2. **Self-Healing**
   - On failure, retry with alternative handler.
   - Log failures and surface recovery steps.

## Phase 3 — Multi-App Weaving
1. **Docs + Knowledge Base**
   - Sync a docs system (Notion/Google Docs) for specs and runbooks.
2. **Tasks + Calendar**
   - Connect task tracking to schedule execution and reminders.
3. **Observability**
   - Central log view for all tool invocations and failures.

---

# Immediate Next Actions
- Confirm your OS, Windsurf version, and whether the OpenAI extension is installed.
- Decide on your preferred fallback IDE (VS Code or a web IDE).
- Identify which external apps you want to connect first (docs, tasks, calendar, CRM).

--- 

# Sudo-mode installs (what the script runs)
If you want to run the installs manually, this is the same logic as `scripts/setup_ecosystem.sh`:
```bash
sudo apt-get update -y
sudo apt-get install -y curl git just
python3 -m pip install --upgrade pip
python3 -m pip install playwright
python3 -m playwright install
```

---

# Fallback Matrix (Example)
| Action | Primary | Secondary | Tertiary |
|---|---|---|---|
| Open IDE | `windsurf:` | `vscode:` | web IDE |
| Run task | IDE task runner | local terminal | remote runner |
| Open doc | Notion | Google Docs | local markdown |

---

# Notes
- Treat protocol links as “fast paths,” not hard dependencies.
- Always provide at least one fallback connector for critical actions.
