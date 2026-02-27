#!/usr/bin/env python3
"""Non-custodial secrets operations scaffold.

This CLI never reads or stores plaintext secret material. It only works with
item metadata and optional external hooks.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

LOG_PATH_DEFAULT = "logs/secrets_agent_audit.log"


class AgentError(RuntimeError):
    """Operational error for user-facing failures."""


@dataclass
class BackendResult:
    backend: str
    connected: bool
    details: Dict[str, Any]


class VaultBackend:
    name = "base"

    def status(self) -> BackendResult:
        raise NotImplementedError

    def list_items(self) -> List[Dict[str, Any]]:
        raise NotImplementedError


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _safe_run(cmd: List[str], timeout: int = 20) -> str:
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise AgentError(f"command failed: {' '.join(cmd)} :: {err}")
    return proc.stdout


def _parse_json(raw: str, origin: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentError(f"invalid JSON from {origin}") from exc


def _metadata_fields(item: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for src, dst in mapping.items():
        if src in item:
            out[dst] = item[src]
    return out


class BitwardenBackend(VaultBackend):
    name = "bitwarden"

    def status(self) -> BackendResult:
        data = _parse_json(_safe_run(["bw", "status", "--raw"]), "bw status")
        connected = data.get("status") in {"unlocked", "authenticated"}
        return BackendResult(self.name, connected, {"status": data.get("status", "unknown")})

    def list_items(self) -> List[Dict[str, Any]]:
        data = _parse_json(_safe_run(["bw", "list", "items", "--raw"]), "bw list items")
        if not isinstance(data, list):
            raise AgentError("unexpected bw list items shape")
        mapping = {
            "id": "id",
            "name": "name",
            "folderId": "folder_id",
            "revisionDate": "revision_date",
            "collectionIds": "collection_ids",
        }
        return [_metadata_fields(item, mapping) for item in data if isinstance(item, dict)]


class OnePasswordBackend(VaultBackend):
    name = "1password"

    def status(self) -> BackendResult:
        data = _parse_json(_safe_run(["op", "whoami", "--format", "json"]), "op whoami")
        acct = data.get("url") or data.get("account_uuid") or "connected"
        return BackendResult(self.name, True, {"account": acct})

    def list_items(self) -> List[Dict[str, Any]]:
        data = _parse_json(_safe_run(["op", "item", "list", "--format", "json"]), "op item list")
        if not isinstance(data, list):
            raise AgentError("unexpected op item list shape")
        mapping = {
            "id": "id",
            "title": "name",
            "category": "category",
            "vault": "vault",
            "updated_at": "updated_at",
            "last_edited_by": "last_edited_by",
            "tags": "tags",
        }
        return [_metadata_fields(item, mapping) for item in data if isinstance(item, dict)]


class MockBackend(VaultBackend):
    name = "mock"

    def status(self) -> BackendResult:
        return BackendResult(self.name, True, {"status": "mock-ready"})

    def list_items(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "svc-github-001",
                "name": "GitHub deploy key",
                "updated_at": "2026-01-05T10:00:00Z",
                "tags": ["owner:platform", "critical"],
            },
            {
                "id": "svc-db-002",
                "name": "Database API token",
                "updated_at": "2025-06-01T08:30:00Z",
                "tags": ["critical"],
            },
        ]


def resolve_backend(name: str) -> VaultBackend:
    normalized = name.strip().lower()
    if normalized in {"bitwarden", "bw"}:
        return BitwardenBackend()
    if normalized in {"1password", "op", "onepassword"}:
        return OnePasswordBackend()
    if normalized == "mock":
        return MockBackend()
    raise AgentError(f"unsupported backend: {name}")


def write_audit_log(action: str, backend: str, metadata: Dict[str, Any]) -> None:
    path = Path(os.getenv("SECRETS_AGENT_LOG_PATH", LOG_PATH_DEFAULT))
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": utc_now().isoformat(),
        "action": action,
        "backend": backend,
        "metadata": metadata,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def parse_ts(value: str) -> Optional[dt.datetime]:
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def compute_plan_id(backend: str, item_ids: Iterable[str]) -> str:
    joined = "|".join(sorted(set(item_ids)))
    digest = hashlib.sha256(f"{backend}|{joined}".encode("utf-8")).hexdigest()
    return digest[:12]


def build_confirm_token(plan_id: str, salt: str) -> str:
    if not salt:
        raise AgentError("SECRETS_AGENT_CONFIRM_SALT is required for rotate operations")
    digest = hmac.new(salt.encode("utf-8"), plan_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:12]


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def cmd_status(args: argparse.Namespace) -> int:
    backend = resolve_backend(args.backend)
    result = backend.status()
    payload = {
        "backend": result.backend,
        "connected": result.connected,
        "details": result.details,
        "time_utc": utc_now().isoformat(),
    }
    write_audit_log("status", result.backend, {"connected": result.connected})
    _print_json(payload)
    return 0


def cmd_list_items(args: argparse.Namespace) -> int:
    backend = resolve_backend(args.backend)
    items = backend.list_items()
    payload = {
        "backend": backend.name,
        "count": len(items),
        "items": items,
    }
    write_audit_log("list-items", backend.name, {"count": len(items)})
    _print_json(payload)
    return 0


def cmd_rotate_plan(args: argparse.Namespace) -> int:
    backend = resolve_backend(args.backend)
    items = backend.list_items()
    known_ids = [i.get("id") for i in items if i.get("id")]
    target_ids = args.item or known_ids
    if not target_ids:
        raise AgentError("no rotatable items found")
    missing = sorted(set(target_ids) - set(known_ids))
    if missing:
        raise AgentError(f"unknown item ids: {', '.join(missing)}")

    plan_id = compute_plan_id(backend.name, target_ids)
    salt = os.getenv("SECRETS_AGENT_CONFIRM_SALT", "")
    confirm_token = build_confirm_token(plan_id, salt)
    payload = {
        "backend": backend.name,
        "plan_id": plan_id,
        "target_item_ids": target_ids,
        "confirm_token": confirm_token,
        "steps": [
            "Rotate each target credential using your vault/provider native tooling.",
            "Update dependent services with new credential references.",
            "Validate service health/auth flows.",
            "Revoke superseded credentials after verification.",
        ],
        "note": "Use rotate-exec with --plan-id and --confirm token.",
    }
    write_audit_log("rotate-plan", backend.name, {"plan_id": plan_id, "count": len(target_ids)})
    _print_json(payload)
    return 0


def maybe_run_hook(template: str, item_id: str) -> None:
    command = template.replace("{item_id}", item_id)
    cmd = shlex.split(command)
    if not cmd:
        raise AgentError("empty hook command")
    _safe_run(cmd)


def cmd_rotate_exec(args: argparse.Namespace) -> int:
    backend = resolve_backend(args.backend)
    items = backend.list_items()
    known_ids = [i.get("id") for i in items if i.get("id")]
    target_ids = args.item or known_ids
    if not target_ids:
        raise AgentError("no rotatable items found")

    expected_plan_id = compute_plan_id(backend.name, target_ids)
    if args.plan_id != expected_plan_id:
        raise AgentError("plan-id mismatch; generate a fresh rotate-plan for these items")

    salt = os.getenv("SECRETS_AGENT_CONFIRM_SALT", "")
    expected_token = build_confirm_token(args.plan_id, salt)
    if args.confirm != expected_token:
        raise AgentError("confirmation token mismatch; refusing rotate-exec")

    rotate_hook = os.getenv("SECRETS_AGENT_ROTATE_HOOK", "").strip()
    revoke_hook = os.getenv("SECRETS_AGENT_REVOKE_HOOK", "").strip()
    executed: List[Dict[str, str]] = []

    for item_id in target_ids:
        if item_id not in known_ids:
            raise AgentError(f"unknown item id: {item_id}")
        if rotate_hook:
            maybe_run_hook(rotate_hook, item_id)
            executed.append({"action": "rotate", "item_id": item_id})
        if args.revoke:
            if not revoke_hook:
                raise AgentError("--revoke set but SECRETS_AGENT_REVOKE_HOOK is not configured")
            maybe_run_hook(revoke_hook, item_id)
            executed.append({"action": "revoke", "item_id": item_id})

    payload = {
        "backend": backend.name,
        "plan_id": args.plan_id,
        "target_item_ids": target_ids,
        "executed_actions": executed,
        "dry_run": not bool(rotate_hook),
        "note": "No plaintext secrets were read or persisted.",
    }
    write_audit_log(
        "rotate-exec",
        backend.name,
        {
            "plan_id": args.plan_id,
            "count": len(target_ids),
            "revoke": bool(args.revoke),
            "dry_run": not bool(rotate_hook),
        },
    )
    _print_json(payload)
    return 0


def cmd_key_audit(args: argparse.Namespace) -> int:
    backend = resolve_backend(args.backend)
    items = backend.list_items()
    now = utc_now()
    stale_cutoff = now - dt.timedelta(days=args.stale_days)
    stale: List[str] = []
    missing_owner: List[str] = []

    for item in items:
        item_id = item.get("id", "unknown")
        tags = item.get("tags") or []
        tag_text = [str(t).lower() for t in tags] if isinstance(tags, list) else []
        if not any(t.startswith("owner:") for t in tag_text):
            missing_owner.append(item_id)

        ts = None
        for field in ("updated_at", "revision_date"):
            if field in item and isinstance(item[field], str):
                ts = parse_ts(item[field])
                if ts:
                    break
        if ts and ts < stale_cutoff:
            stale.append(item_id)

    payload = {
        "backend": backend.name,
        "count": len(items),
        "stale_days_threshold": args.stale_days,
        "findings": {
            "stale_item_ids": stale,
            "missing_owner_tag_item_ids": missing_owner,
        },
    }
    write_audit_log(
        "key-audit",
        backend.name,
        {"count": len(items), "stale_count": len(stale), "missing_owner_count": len(missing_owner)},
    )
    _print_json(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Non-custodial password/key management scaffold")
    parser.add_argument(
        "--backend",
        default=os.getenv("SECRETS_AGENT_BACKEND", "mock"),
        help="vault backend: bitwarden, 1password, or mock",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="check backend connectivity")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list-items", help="list item metadata only")
    p_list.set_defaults(func=cmd_list_items)

    p_plan = sub.add_parser("rotate-plan", help="build a confirmed rotation plan")
    p_plan.add_argument("--item", action="append", help="target item id (repeatable)")
    p_plan.set_defaults(func=cmd_rotate_plan)

    p_exec = sub.add_parser("rotate-exec", help="execute rotation hooks after explicit confirmation")
    p_exec.add_argument("--plan-id", required=True, help="plan id from rotate-plan")
    p_exec.add_argument("--confirm", required=True, help="confirmation token from rotate-plan")
    p_exec.add_argument("--item", action="append", help="target item id (repeatable)")
    p_exec.add_argument(
        "--revoke",
        action="store_true",
        help="also run revoke hook after rotate hook for each item",
    )
    p_exec.set_defaults(func=cmd_rotate_exec)

    p_audit = sub.add_parser("key-audit", help="audit metadata for stale keys and ownership tags")
    p_audit.add_argument("--stale-days", type=int, default=90, help="stale age threshold")
    p_audit.set_defaults(func=cmd_key_audit)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except AgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        write_audit_log("error", getattr(args, "backend", "unknown"), {"message": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
