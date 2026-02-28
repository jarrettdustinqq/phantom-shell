"""Release marker automation for immutable tag + note pairing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import re
import subprocess


MAX_CHANGED_FILES_IN_NOTE = 18
MAX_BODY_LINES_IN_NOTE = 5
SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    candidate = SLUG_RE.sub("-", value.strip())
    candidate = candidate.strip("-")
    return candidate or "release-marker"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass
class CommitMetadata:
    commit: str
    short_commit: str
    author_name: str
    author_email: str
    commit_date: str
    subject: str
    body: str


class ReleaseMarkerAgent:
    """Generates one-screen release notes from immutable git refs."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.default_ledger_path = self.state_dir / "markers.jsonl"
        if not self.default_ledger_path.exists():
            self.default_ledger_path.write_text("", encoding="utf-8")

    def _git(self, repo_path: Path, args: list[str]) -> str:
        proc = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip() or "git command failed"
            raise RuntimeError(f"git {' '.join(args)} :: {err}")
        return proc.stdout

    def _repo_root(self, repo_path: Path) -> Path:
        root = self._git(repo_path, ["rev-parse", "--show-toplevel"]).strip()
        if not root:
            raise RuntimeError(f"unable to resolve repository root: {repo_path}")
        return Path(root).resolve()

    def _metadata(self, repo_root: Path, ref: str) -> CommitMetadata:
        commit = self._git(repo_root, ["rev-parse", f"{ref}^{{commit}}"]).strip()
        raw = self._git(
            repo_root,
            [
                "show",
                "-s",
                "--format=%H%n%h%n%an%n%ae%n%cI%n%s%n%b",
                commit,
            ],
        ).rstrip("\n")
        lines = raw.split("\n")
        if len(lines) < 6:
            raise RuntimeError(f"unexpected git show output for ref: {ref}")
        body = "\n".join(lines[6:]).strip()
        return CommitMetadata(
            commit=lines[0].strip(),
            short_commit=lines[1].strip(),
            author_name=lines[2].strip(),
            author_email=lines[3].strip(),
            commit_date=lines[4].strip(),
            subject=lines[5].strip(),
            body=body,
        )

    def _tags_on_commit(self, repo_root: Path, commit: str) -> list[str]:
        out = self._git(repo_root, ["tag", "--points-at", commit])
        rows = [line.strip() for line in out.splitlines() if line.strip()]
        rows.sort()
        return rows

    def _changed_files(self, repo_root: Path, commit: str) -> list[str]:
        out = self._git(repo_root, ["show", "--name-only", "--pretty=format:", commit])
        return [line.strip() for line in out.splitlines() if line.strip()]

    def _shortstat(self, repo_root: Path, commit: str) -> str:
        out = self._git(repo_root, ["show", "--shortstat", "--pretty=format:", commit])
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        if not lines:
            return "0 files changed"
        return lines[-1]

    def _default_note_path(self, repo_root: Path, marker_name: str) -> Path:
        filename = f"{slugify(marker_name)}.md"
        return repo_root / "reports" / "release-markers" / filename

    def _append_ledger(self, ledger_path: Path, row: dict[str, Any]) -> None:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")

    def _body_excerpt(self, body: str) -> list[str]:
        if not body.strip():
            return []
        lines = [line.rstrip() for line in body.splitlines() if line.strip()]
        return lines[:MAX_BODY_LINES_IN_NOTE]

    def _build_note(
        self,
        *,
        generated_at: str,
        repo_root: Path,
        requested_ref: str,
        marker_name: str,
        metadata: CommitMetadata,
        tags: list[str],
        shortstat: str,
        changed_files: list[str],
    ) -> str:
        tag_text = ", ".join(tags) if tags else "(none)"
        rows = [
            f"# Release Marker: {marker_name}",
            "",
            f"- generated_at_utc: {generated_at}",
            f"- repository: {repo_root.name}",
            f"- repo_path: {repo_root}",
            f"- requested_ref: {requested_ref}",
            f"- commit: {metadata.commit}",
            f"- short_commit: {metadata.short_commit}",
            f"- commit_date: {metadata.commit_date}",
            f"- author: {metadata.author_name} <{metadata.author_email}>",
            f"- subject: {metadata.subject}",
            f"- tags_on_commit: {tag_text}",
            f"- shortstat: {shortstat}",
            "",
            "## Changed Files",
        ]
        if changed_files:
            visible = changed_files[:MAX_CHANGED_FILES_IN_NOTE]
            rows.extend(f"- {path}" for path in visible)
            hidden = len(changed_files) - len(visible)
            if hidden > 0:
                rows.append(f"- ... (+{hidden} more)")
        else:
            rows.append("- (none)")

        excerpt = self._body_excerpt(metadata.body)
        if excerpt:
            rows.extend(["", "## Commit Body Excerpt"])
            rows.extend(f"- {line}" for line in excerpt)
            hidden_body_lines = max(0, len([line for line in metadata.body.splitlines() if line.strip()]) - len(excerpt))
            if hidden_body_lines > 0:
                rows.append(f"- ... (+{hidden_body_lines} more lines)")

        return "\n".join(rows).rstrip() + "\n"

    def capture(
        self,
        *,
        repo_path: Path,
        ref: str = "HEAD",
        marker_name: str = "",
        note_path: Path | None = None,
        ledger_path: Path | None = None,
        allow_existing_note: bool = False,
    ) -> dict[str, Any]:
        repo_root = self._repo_root(repo_path.resolve())
        clean_ref = ref.strip() or "HEAD"
        metadata = self._metadata(repo_root, clean_ref)
        tags = self._tags_on_commit(repo_root, metadata.commit)
        effective_marker = marker_name.strip()
        if not effective_marker:
            if tags:
                effective_marker = tags[0]
            else:
                date_prefix = metadata.commit_date[:10] if len(metadata.commit_date) >= 10 else "undated"
                effective_marker = f"{repo_root.name}-{date_prefix}-{metadata.short_commit}"

        final_note_path = note_path.resolve() if note_path is not None else self._default_note_path(repo_root, effective_marker)
        if final_note_path.exists() and not allow_existing_note:
            raise FileExistsError(f"release note already exists: {final_note_path}")

        changed_files = self._changed_files(repo_root, metadata.commit)
        shortstat = self._shortstat(repo_root, metadata.commit)
        generated_at = utc_now_iso()
        note_text = self._build_note(
            generated_at=generated_at,
            repo_root=repo_root,
            requested_ref=clean_ref,
            marker_name=effective_marker,
            metadata=metadata,
            tags=tags,
            shortstat=shortstat,
            changed_files=changed_files,
        )

        final_note_path.parent.mkdir(parents=True, exist_ok=True)
        final_note_path.write_text(note_text, encoding="utf-8")

        final_ledger_path = ledger_path.resolve() if ledger_path is not None else self.default_ledger_path
        row = {
            "generated_at": generated_at,
            "repo_name": repo_root.name,
            "repo_path": str(repo_root),
            "requested_ref": clean_ref,
            "marker_name": effective_marker,
            "commit": metadata.commit,
            "short_commit": metadata.short_commit,
            "subject": metadata.subject,
            "tags_on_commit": tags,
            "shortstat": shortstat,
            "changed_file_count": len(changed_files),
            "note_path": str(final_note_path),
            "note_sha256": sha256_text(note_text),
        }
        self._append_ledger(final_ledger_path, row)
        return {
            "ok": True,
            "marker": row,
            "ledger_path": str(final_ledger_path),
        }

    def status(self, ledger_path: Path | None = None) -> dict[str, Any]:
        final_ledger_path = ledger_path.resolve() if ledger_path is not None else self.default_ledger_path
        if not final_ledger_path.exists():
            return {
                "ok": True,
                "ledger_path": str(final_ledger_path),
                "marker_count": 0,
                "latest": {},
            }
        rows: list[dict[str, Any]] = []
        for line in final_ledger_path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        latest = rows[-1] if rows else {}
        return {
            "ok": True,
            "ledger_path": str(final_ledger_path),
            "marker_count": len(rows),
            "latest": latest,
        }
