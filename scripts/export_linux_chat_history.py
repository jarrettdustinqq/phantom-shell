#!/usr/bin/env python3
"""Export Linux chat history into a Business ChatGPT handoff package."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
import re
import shutil
import socket
from pathlib import Path
from typing import Any

UTC = dt.timezone.utc

ZSH_LINE_RE = re.compile(r"^: (\d+):\d+;(.*)$")
KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password)\b(\s*[:=]\s*)([^\s\"'`]+)"
)
URL_CREDENTIAL_RE = re.compile(r"(https?://[^/\s:@]+:)[^@\s/]+@")
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
GITHUB_PAT_RE = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")
GITHUB_FINE_GRAINED_RE = re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")
AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a chunked Linux chat history handoff package for Business ChatGPT."
    )
    parser.add_argument(
        "--home-dir",
        default=str(Path.home()),
        help="Home directory to scan for shell history files.",
    )
    parser.add_argument(
        "--codex-home",
        default="~/.codex",
        help="Codex home directory that contains sessions/history.",
    )
    parser.add_argument(
        "--output-dir",
        default="~/work-organizer/business-chatgpt-handoff",
        help="Output root directory. A timestamped run folder is created inside it.",
    )
    parser.add_argument(
        "--max-chars-per-chunk",
        type=int,
        default=90000,
        help="Maximum approximate characters per chunk file.",
    )
    parser.add_argument(
        "--since-days",
        type=float,
        default=None,
        help="Optional lookback window. If omitted, exports full history.",
    )
    parser.add_argument(
        "--session-limit",
        type=int,
        default=0,
        help="Optional cap on newest Codex session files to parse (0 means no cap).",
    )
    parser.add_argument(
        "--shell-history",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include ~/.bash_history, ~/.zsh_history, and fish history when present.",
    )
    parser.add_argument(
        "--codex-history",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include ~/.codex/history.jsonl when present.",
    )
    parser.add_argument(
        "--codex-sessions",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include ~/.codex/sessions/**/*.jsonl when present.",
    )
    parser.add_argument(
        "--shell-snapshots",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include ~/.codex/shell_snapshots/*.sh when present.",
    )
    parser.add_argument(
        "--redact",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Apply basic secret redaction to exported text.",
    )
    parser.add_argument(
        "--emit-zip",
        action="store_true",
        help="Also create a zip archive for easier upload.",
    )
    return parser.parse_args()


def now_utc() -> dt.datetime:
    return dt.datetime.now(tz=UTC)


def iso_from_epoch(raw: Any) -> str | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        try:
            return dt.datetime.fromtimestamp(float(raw), tz=UTC).isoformat()
        except (ValueError, OSError):
            return None
    if isinstance(raw, str) and raw.isdigit():
        return iso_from_epoch(int(raw))
    return None


def parse_iso(raw: Any) -> dt.datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    candidate = raw
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(candidate).astimezone(UTC)
    except ValueError:
        return None


def file_mtime_iso(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def redact_text(text: str) -> str:
    if not text:
        return text
    out = text
    out = KEY_VALUE_SECRET_RE.sub(r"\1\2[REDACTED]", out)
    out = URL_CREDENTIAL_RE.sub(r"\1[REDACTED]@", out)
    out = OPENAI_KEY_RE.sub("[REDACTED_OPENAI_KEY]", out)
    out = GITHUB_PAT_RE.sub("[REDACTED_GITHUB_TOKEN]", out)
    out = GITHUB_FINE_GRAINED_RE.sub("[REDACTED_GITHUB_TOKEN]", out)
    out = AWS_ACCESS_KEY_RE.sub("[REDACTED_AWS_ACCESS_KEY]", out)
    out = JWT_RE.sub("[REDACTED_JWT]", out)
    return out


def event(
    source: str,
    text: str,
    *,
    timestamp: str | None = None,
    role: str | None = None,
    session_id: str | None = None,
    path: str | None = None,
    estimated_timestamp: bool = False,
) -> dict[str, Any]:
    return {
        "source": source,
        "timestamp": timestamp,
        "timestamp_estimated": estimated_timestamp,
        "session_id": session_id,
        "role": role,
        "path": path,
        "text": text,
    }


def parse_bash_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    fallback_ts = file_mtime_iso(path)
    pending_epoch: int | None = None
    for raw_line in read_text(path).splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith("#") and line[1:].isdigit():
            pending_epoch = int(line[1:])
            continue
        ts = iso_from_epoch(pending_epoch) if pending_epoch is not None else fallback_ts
        events.append(
            event(
                "bash_history",
                line,
                timestamp=ts,
                role="shell_command",
                path=str(path),
                estimated_timestamp=pending_epoch is None,
            )
        )
        pending_epoch = None
    return events


def parse_zsh_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    fallback_ts = file_mtime_iso(path)
    for raw_line in read_text(path).splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        match = ZSH_LINE_RE.match(line)
        if match:
            ts = iso_from_epoch(match.group(1)) or fallback_ts
            cmd = match.group(2)
            estimated = False
        else:
            ts = fallback_ts
            cmd = line
            estimated = True
        events.append(
            event(
                "zsh_history",
                cmd,
                timestamp=ts,
                role="shell_command",
                path=str(path),
                estimated_timestamp=estimated,
            )
        )
    return events


def decode_fish_cmd(raw: str) -> str:
    out = raw.replace("\\n", "\n")
    out = out.replace("\\t", "\t")
    out = out.replace("\\\\", "\\")
    return out


def parse_fish_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    fallback_ts = file_mtime_iso(path)
    pending_cmd: str | None = None
    pending_when: int | None = None

    def flush_pending() -> None:
        nonlocal pending_cmd, pending_when
        if pending_cmd is None:
            return
        ts = iso_from_epoch(pending_when) or fallback_ts
        events.append(
            event(
                "fish_history",
                pending_cmd,
                timestamp=ts,
                role="shell_command",
                path=str(path),
                estimated_timestamp=pending_when is None,
            )
        )
        pending_cmd = None
        pending_when = None

    for line in read_text(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("- cmd:"):
            flush_pending()
            cmd_raw = stripped[len("- cmd:") :].lstrip()
            pending_cmd = decode_fish_cmd(cmd_raw)
        elif stripped.startswith("when:"):
            raw_when = stripped[len("when:") :].strip()
            pending_when = int(raw_when) if raw_when.isdigit() else None
    flush_pending()
    return events


def text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text_value = item.get("text")
        if isinstance(text_value, str) and text_value.strip():
            parts.append(text_value.strip())
    return "\n".join(parts).strip()


def parse_function_call_arguments(raw: Any) -> str:
    if isinstance(raw, dict):
        return json.dumps(raw, sort_keys=True)
    if not isinstance(raw, str):
        return ""
    candidate = raw.strip()
    if not candidate:
        return ""
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return candidate
    if isinstance(parsed, dict):
        cmd = parsed.get("cmd")
        if isinstance(cmd, str) and cmd.strip():
            workdir = parsed.get("workdir")
            if isinstance(workdir, str) and workdir.strip():
                return f"cmd={cmd.strip()} | workdir={workdir.strip()}"
            return cmd.strip()
    return json.dumps(parsed, sort_keys=True)


def parse_codex_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        text_value = payload.get("text")
        if not isinstance(text_value, str) or not text_value.strip():
            continue
        events.append(
            event(
                "codex_history",
                text_value.strip(),
                timestamp=iso_from_epoch(payload.get("ts")),
                role="user",
                session_id=str(payload.get("session_id")) if payload.get("session_id") else None,
                path=str(path),
            )
        )
    return events


def iter_session_files(codex_home: Path, limit: int) -> list[Path]:
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.exists():
        return []
    files = sorted(sessions_dir.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if limit > 0:
        files = files[-limit:]
    return files


def parse_codex_session_file(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    fallback_ts = file_mtime_iso(path)
    current_session_id: str | None = None

    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        top_ts = row.get("timestamp")
        parsed_top_ts = parse_iso(top_ts)
        ts = parsed_top_ts.isoformat() if parsed_top_ts else fallback_ts
        estimated = parsed_top_ts is None

        if row.get("type") == "session_meta":
            payload = row.get("payload", {})
            if isinstance(payload, dict):
                sid = payload.get("id")
                if isinstance(sid, str) and sid:
                    current_session_id = sid
            continue

        if row.get("type") != "response_item":
            continue
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            continue

        item_type = payload.get("type")
        if item_type == "message":
            msg = text_from_content(payload.get("content"))
            if not msg:
                continue
            role = payload.get("role")
            role_value = str(role) if role is not None else "unknown"
            events.append(
                event(
                    "codex_session_message",
                    msg,
                    timestamp=ts,
                    role=role_value,
                    session_id=current_session_id,
                    path=str(path),
                    estimated_timestamp=estimated,
                )
            )
        elif item_type == "function_call":
            args_text = parse_function_call_arguments(payload.get("arguments"))
            if not args_text:
                continue
            tool_name = payload.get("name")
            prefix = f"tool={tool_name} | " if isinstance(tool_name, str) and tool_name else ""
            events.append(
                event(
                    "codex_tool_call",
                    f"{prefix}{args_text}",
                    timestamp=ts,
                    role="tool_call",
                    session_id=current_session_id,
                    path=str(path),
                    estimated_timestamp=estimated,
                )
            )
        elif item_type == "function_call_output":
            output_value = payload.get("output")
            if not isinstance(output_value, str) or not output_value.strip():
                continue
            events.append(
                event(
                    "codex_tool_output",
                    output_value.strip(),
                    timestamp=ts,
                    role="tool_output",
                    session_id=current_session_id,
                    path=str(path),
                    estimated_timestamp=estimated,
                )
            )

    return events


def parse_codex_sessions(codex_home: Path, limit: int) -> tuple[list[dict[str, Any]], int]:
    files = iter_session_files(codex_home, limit=limit)
    events: list[dict[str, Any]] = []
    for path in files:
        events.extend(parse_codex_session_file(path))
    return events, len(files)


def parse_shell_snapshots(codex_home: Path) -> tuple[list[dict[str, Any]], int]:
    snapshots_dir = codex_home / "shell_snapshots"
    if not snapshots_dir.exists():
        return [], 0
    files = sorted(snapshots_dir.glob("*.sh"), key=lambda p: p.stat().st_mtime)
    events: list[dict[str, Any]] = []
    for path in files:
        text = read_text(path).strip()
        if not text:
            continue
        events.append(
            event(
                "codex_shell_snapshot",
                text,
                timestamp=file_mtime_iso(path),
                role="shell_snapshot",
                session_id=path.stem,
                path=str(path),
            )
        )
    return events, len(files)


def apply_since_filter(events: list[dict[str, Any]], since_days: float | None) -> list[dict[str, Any]]:
    if since_days is None:
        return events
    cutoff = now_utc() - dt.timedelta(days=since_days)
    filtered: list[dict[str, Any]] = []
    for item in events:
        parsed = parse_iso(item.get("timestamp"))
        if parsed is None or parsed >= cutoff:
            filtered.append(item)
    return filtered


def sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = [(idx, item) for idx, item in enumerate(events)]

    def key_fn(entry: tuple[int, dict[str, Any]]) -> tuple[int, float, int]:
        idx, item = entry
        parsed = parse_iso(item.get("timestamp"))
        if parsed is None:
            return (1, 0.0, idx)
        return (0, parsed.timestamp(), idx)

    indexed.sort(key=key_fn)
    out: list[dict[str, Any]] = []
    for sequence, (_, item) in enumerate(indexed, start=1):
        item["sequence"] = sequence
        out.append(item)
    return out


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in events:
            handle.write(json.dumps(item, sort_keys=False) + "\n")


def render_event_block(item: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"--- EVENT {item['sequence']:07d} ---")
    lines.append(f"source: {item.get('source', 'unknown')}")
    timestamp = item.get("timestamp")
    if isinstance(timestamp, str) and timestamp:
        lines.append(f"timestamp: {timestamp}")
    if item.get("timestamp_estimated"):
        lines.append("timestamp_estimated: true")
    session_id = item.get("session_id")
    if isinstance(session_id, str) and session_id:
        lines.append(f"session_id: {session_id}")
    role = item.get("role")
    if isinstance(role, str) and role:
        lines.append(f"role: {role}")
    source_path = item.get("path")
    if isinstance(source_path, str) and source_path:
        lines.append(f"path: {source_path}")
    lines.append("text:")
    lines.append(item.get("text", ""))
    lines.append("")
    return "\n".join(lines)


def chunk_strings(blocks: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0
    for block in blocks:
        block_len = len(block)
        if current_parts and current_len + block_len > max_chars:
            chunks.append("".join(current_parts))
            current_parts = [block]
            current_len = block_len
        else:
            current_parts.append(block)
            current_len += block_len
    if current_parts:
        chunks.append("".join(current_parts))
    return chunks


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_handoff_prompt(path: Path, manifest: dict[str, Any]) -> None:
    text = f"""I am handing off my complete Linux chat history export package.

Please process all attached files in this exact order:
1. `manifest.json`
2. `normalized-history.jsonl`
3. Every file in `chunks/` sorted by filename

Hard requirements:
1. Confirm the total ingested event count equals `{manifest["event_count"]}`.
2. Do not skip any chunk file.
3. If any file cannot be parsed, call it out explicitly.
4. After ingesting, produce:
- Active workstreams
- Open blockers and risks
- The top next actions in strict priority order
- Any security-sensitive follow-ups
5. End your reply with `HANDOFF COMPLETE` and UTC timestamp.
"""
    path.write_text(text, encoding="utf-8")


def write_upload_instructions(
    path: Path,
    run_dir: Path,
    manifest: dict[str, Any],
    zip_path: Path | None,
) -> None:
    chunk_list = "\n".join(f"- chunks/{name}" for name in manifest["chunk_files"])
    zip_lines = ""
    if zip_path is not None:
        zip_lines = (
            "Recommended first try:\n"
            f"- Upload `{zip_path.name}` from `{zip_path.parent}`\n\n"
        )
    text = f"""# Business ChatGPT Upload Instructions

## 1) Open your Business profile
Open ChatGPT and switch to your Business profile/workspace.

## 2) Start a new handoff chat
Suggested title: `Linux Chat History Handoff - {manifest["generated_at"]}`.

## 3) Upload files from this folder
Run folder: `{run_dir}`

{zip_lines}If zip upload is not supported, upload in this order:
- `manifest.json`
- `normalized-history.jsonl`
{chunk_list}

## 4) Paste and send
Paste the full contents of `handoff_prompt.txt` into the chat and send.

## 5) Confirm completion
Make sure the response includes:
- `HANDOFF COMPLETE`
- UTC timestamp
- Event count `{manifest["event_count"]}`
"""
    path.write_text(text, encoding="utf-8")


def update_latest_symlink(output_root: Path, run_dir: Path) -> None:
    latest = output_root / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(run_dir.name, target_is_directory=True)
    except OSError:
        # Symlink support can vary; ignore this convenience feature on failure.
        return


def create_run_dir(output_root: Path) -> Path:
    stamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "chunks").mkdir(parents=True, exist_ok=True)
    return run_dir


def main() -> int:
    args = parse_args()
    home_dir = Path(args.home_dir).expanduser().resolve()
    codex_home = Path(args.codex_home).expanduser().resolve()
    output_root = Path(args.output_dir).expanduser().resolve()
    run_dir = create_run_dir(output_root)

    all_events: list[dict[str, Any]] = []
    source_stats: dict[str, int] = {
        "bash_history": 0,
        "zsh_history": 0,
        "fish_history": 0,
        "codex_history": 0,
        "codex_sessions": 0,
        "codex_shell_snapshots": 0,
        "codex_session_files": 0,
        "codex_snapshot_files": 0,
    }

    if args.shell_history:
        bash_events = parse_bash_history(home_dir / ".bash_history")
        zsh_events = parse_zsh_history(home_dir / ".zsh_history")
        fish_events = parse_fish_history(home_dir / ".local/share/fish/fish_history")
        all_events.extend(bash_events)
        all_events.extend(zsh_events)
        all_events.extend(fish_events)
        source_stats["bash_history"] = len(bash_events)
        source_stats["zsh_history"] = len(zsh_events)
        source_stats["fish_history"] = len(fish_events)

    if args.codex_history:
        codex_history_events = parse_codex_history(codex_home / "history.jsonl")
        all_events.extend(codex_history_events)
        source_stats["codex_history"] = len(codex_history_events)

    if args.codex_sessions:
        codex_session_events, session_file_count = parse_codex_sessions(
            codex_home,
            limit=args.session_limit,
        )
        all_events.extend(codex_session_events)
        source_stats["codex_sessions"] = len(codex_session_events)
        source_stats["codex_session_files"] = session_file_count

    if args.shell_snapshots:
        snapshot_events, snapshot_file_count = parse_shell_snapshots(codex_home)
        all_events.extend(snapshot_events)
        source_stats["codex_shell_snapshots"] = len(snapshot_events)
        source_stats["codex_snapshot_files"] = snapshot_file_count

    all_events = apply_since_filter(all_events, args.since_days)

    if args.redact:
        for item in all_events:
            item["text"] = redact_text(item.get("text", ""))

    ordered_events = sort_events(all_events)

    normalized_path = run_dir / "normalized-history.jsonl"
    write_jsonl(normalized_path, ordered_events)

    blocks = [render_event_block(item) for item in ordered_events]
    chunks = chunk_strings(blocks, max_chars=max(8000, args.max_chars_per_chunk))
    chunk_files: list[Path] = []
    generated_at = now_utc().isoformat()
    total_chunks = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        chunk_name = f"chat-history-{idx:04d}.md"
        chunk_path = run_dir / "chunks" / chunk_name
        header = (
            f"# Linux Chat History Chunk {idx}/{total_chunks}\n"
            f"generated_at: {generated_at}\n\n"
        )
        chunk_path.write_text(header + chunk, encoding="utf-8")
        chunk_files.append(chunk_path)

    source_counts: dict[str, int] = {}
    for item in ordered_events:
        key = str(item.get("source") or "unknown")
        source_counts[key] = source_counts.get(key, 0) + 1

    file_hashes = {
        "normalized-history.jsonl": sha256_of_file(normalized_path),
        **{f"chunks/{p.name}": sha256_of_file(p) for p in chunk_files},
    }

    manifest = {
        "generated_at": generated_at,
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "home_dir": str(home_dir),
        "codex_home": str(codex_home),
        "run_dir": str(run_dir),
        "redaction_enabled": bool(args.redact),
        "max_chars_per_chunk": args.max_chars_per_chunk,
        "since_days": args.since_days,
        "event_count": len(ordered_events),
        "chunk_count": len(chunk_files),
        "chunk_files": [p.name for p in chunk_files],
        "source_stats": source_stats,
        "source_counts": source_counts,
        "file_sha256": file_hashes,
    }

    manifest_path = run_dir / "manifest.json"
    write_json(manifest_path, manifest)

    prompt_path = run_dir / "handoff_prompt.txt"
    write_handoff_prompt(prompt_path, manifest)

    zip_path: Path | None = None
    if args.emit_zip:
        archive_base = run_dir.parent / run_dir.name
        zip_created = shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=str(run_dir.parent),
            base_dir=run_dir.name,
        )
        zip_path = Path(zip_created)

    upload_path = run_dir / "UPLOAD_INSTRUCTIONS.md"
    write_upload_instructions(upload_path, run_dir, manifest, zip_path=zip_path)
    update_latest_symlink(output_root, run_dir)

    print(f"Run directory: {run_dir}")
    print(f"Events exported: {len(ordered_events)}")
    print(f"Chunk files: {len(chunk_files)}")
    print(f"Manifest: {manifest_path}")
    print(f"Normalized timeline: {normalized_path}")
    print(f"Handoff prompt: {prompt_path}")
    print(f"Upload guide: {upload_path}")
    if zip_path:
        print(f"Zip archive: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
