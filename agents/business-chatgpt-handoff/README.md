# Business ChatGPT Handoff Agent

Exports Linux chat history into a package you can upload to your Business ChatGPT profile.

## Run

From `projects/phantom-shell`:

```bash
scripts/run_business_chatgpt_handoff.sh
```

## Output

Each run creates a timestamped folder under:

`~/work-organizer/business-chatgpt-handoff/`

Inside the run folder:

- `manifest.json` (event counts, source stats, hashes)
- `normalized-history.jsonl` (full normalized timeline)
- `chunks/chat-history-*.md` (upload-ready chunk files)
- `handoff_prompt.txt` (paste into Business ChatGPT)
- `UPLOAD_INSTRUCTIONS.md` (exact upload flow)
- `<timestamp>.zip` (created by runner for convenience)

## Useful options

```bash
python3 scripts/export_linux_chat_history.py --since-days 30
python3 scripts/export_linux_chat_history.py --no-shell-snapshots
python3 scripts/export_linux_chat_history.py --no-redact
python3 scripts/export_linux_chat_history.py --max-chars-per-chunk 70000
```
