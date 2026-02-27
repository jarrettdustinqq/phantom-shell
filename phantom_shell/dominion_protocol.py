"""DominionOS protocol primitives for safe autonomous optimization.

This module implements high-leverage scaffolding for:
- mission anchors and mode governance
- structured handoffs and checkpoint memory
- event bus coordination
- risk containment (irreversible-action consent + circuit breakers)
- publish-diff guardrails with immutable sections
- dual-LLM verification adapter surface
- Project Ark backups and Phoenix-style restore scaffolding
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
import difflib
import json
import math
import re
import shlex
import subprocess
import tarfile
import tempfile
import uuid


MISSION_PILLARS = [
    "survive_minimize_risk",
    "financial_legal_buffer",
    "passive_income_independence",
    "long_term_community_impact",
]

CONTINUITY_MODES = [
    "iron_frame",
    "forge_engine",
    "ghost_market",
    "veil_engine",
    "vault_mode",
    "revenant_mode",
    "shadow_ops",
    "self_improvement_loop",
    "loop_watchdog",
]

DOMINION_AGENTS = [
    {
        "agent_id": "reclaimor",
        "purpose": "Discover unclaimed/recoverable balances and flag opportunities.",
        "triggers": ["daily_tick", "fund_scan_requested"],
        "outputs": ["fund_found"],
    },
    {
        "agent_id": "mutator",
        "purpose": "Run controlled upgrades and A/B operational experiments.",
        "triggers": ["strategy_update", "tuning_instruction"],
        "outputs": ["mutation_proposed", "mutation_merged"],
    },
    {
        "agent_id": "ghost_writer",
        "purpose": "Draft content packets and publishing plans.",
        "triggers": ["new_trend", "publish_schedule_tick"],
        "outputs": ["content_draft_ready", "content_published"],
    },
    {
        "agent_id": "fund_tracker",
        "purpose": "Track revenue events across connected ledgers/processors.",
        "triggers": ["transaction_seen", "daily_tick"],
        "outputs": ["sale_event"],
    },
    {
        "agent_id": "identity_forge",
        "purpose": "Manage pseudonymous profile metadata and redaction rules.",
        "triggers": ["persona_rotation_tick", "identity_scrub_requested"],
        "outputs": ["persona_rotated", "identity_scrubbed"],
    },
    {
        "agent_id": "tactician",
        "purpose": "Identify high-leverage opportunities and trend signals.",
        "triggers": ["hourly_tick", "research_refresh"],
        "outputs": ["new_trend"],
    },
    {
        "agent_id": "dominion_guard",
        "purpose": "Backups, health checks, and recovery orchestration.",
        "triggers": ["hourly_tick", "health_alert", "backup_tick"],
        "outputs": ["backup_complete", "agent_restarted", "recovery_event"],
    },
]

HANDOFF_REQUIRED_KEYS = {
    "schema_version",
    "from_agent",
    "to_agent",
    "created_at",
    "mode_tags",
    "objective",
    "history",
    "parameters",
    "next_actions",
}

IMMUTABLE_SECTION_RE = re.compile(
    r"<!--\s*IMMUTABLE:START\s+([a-zA-Z0-9_.-]+)\s*-->(.*?)<!--\s*IMMUTABLE:END\s+\1\s*-->",
    flags=re.DOTALL,
)

TOKEN_RE = re.compile(r"[a-z0-9_]{2,}", flags=re.IGNORECASE)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_tokens(text: str) -> Counter[str]:
    return Counter(TOKEN_RE.findall(text.lower()))


def _cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[tok] * b[tok] for tok in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _safe_json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _safe_read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


@dataclass
class HandoffPacket:
    schema_version: int
    from_agent: str
    to_agent: str
    created_at: str
    mode_tags: list[str]
    objective: str
    history: list[str]
    parameters: dict[str, Any]
    next_actions: list[str]
    prime_pillars: list[str] = field(default_factory=list)


@dataclass
class TranscendenceState:
    archive_published_and_indexed: bool = False
    external_collaborator_interacted: bool = False
    deep_research_no_improvement_cycles: int = 0
    revenue_stream_usd_monthly: float = 0.0
    publish_sync_full_cycles: int = 0


@dataclass
class SafetyDecision:
    allowed: bool
    reason: str
    requires_operator_confirmation: bool


@dataclass
class VerificationResult:
    status: str
    primary_model: str
    secondary_model: str
    generation: str
    validation: str
    agreed: bool
    failover_used: bool


@dataclass
class SnapshotInfo:
    snapshot_path: str
    created_at: str
    retention_days: int
    included_paths: list[str]
    restore_test_passed: bool
    offsite_sync_attempted: bool
    offsite_sync_succeeded: bool


@dataclass
class TuningInstruction:
    instruction_id: str
    created_at: str
    source: str
    cpu_pct: float
    memory_pct: float
    queue_depth: int
    action: str
    rationale: str
    risk_level: str


@dataclass
class CatalystItem:
    item_id: str
    title: str
    hypothesis: str
    metric: str
    baseline: float
    candidate: float
    status: str
    created_at: str
    updated_at: str


class CheckpointMemory:
    """Vector-lite checkpoint memory with cosine retrieval over token counts."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.rows: list[dict[str, Any]] = _safe_json_load(self.state_path, [])
        if not isinstance(self.rows, list):
            self.rows = []

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.rows, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def add_checkpoint(
        self,
        summary: str,
        mode_tags: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "checkpoint_id": f"ckpt-{len(self.rows) + 1:05d}",
            "created_at": utc_now_iso(),
            "summary": summary.strip(),
            "mode_tags": sorted({tag for tag in mode_tags if tag}),
            "metadata": dict(metadata or {}),
        }
        self.rows.append(row)
        self.save()
        return row

    def query(self, text: str, limit: int = 5) -> list[dict[str, Any]]:
        qv = _normalize_tokens(text)
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in self.rows:
            sv = _normalize_tokens(str(row.get("summary", "")))
            score = _cosine_similarity(qv, sv)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, row in scored[: max(1, limit)]:
            out = dict(row)
            out["score"] = round(score, 4)
            results.append(out)
        return results


class DominionMessageBus:
    """JSONL message bus with append-only event log semantics."""

    def __init__(self, event_log_path: Path) -> None:
        self.event_log_path = event_log_path

    def emit(self, event_type: str, source: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "event_id": f"evt-{uuid.uuid4().hex}",
            "event_type": event_type,
            "source": source,
            "payload": payload,
            "created_at": utc_now_iso(),
        }
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
        return event

    def tail(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.event_log_path.exists():
            return []
        out: deque[dict[str, Any]] = deque(maxlen=max(1, limit))
        with self.event_log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return list(out)


class DominionPolicyEngine:
    """Mission/mode classification, transcendence gating, and safety decisions."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.state = _safe_json_load(
            self.state_path,
            {
                "current_mode": "structured",
                "wild_mode_approved_by": "",
                "wild_mode_reason": "",
                "trade_window_events": [],
                "post_window_events": [],
            },
        )
        if not isinstance(self.state, dict):
            self.state = {
                "current_mode": "structured",
                "wild_mode_approved_by": "",
                "wild_mode_reason": "",
                "trade_window_events": [],
                "post_window_events": [],
            }
        self.save()

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def classify_modes(self, task_text: str) -> list[str]:
        text = task_text.lower()
        tags = set()
        keyword_map = {
            "iron_frame": ["daily", "execution", "discipline", "routine"],
            "forge_engine": ["asset", "build", "pipeline", "product"],
            "ghost_market": ["funnel", "market", "affiliate", "audience"],
            "veil_engine": ["privacy", "pseudonym", "redaction", "identity"],
            "vault_mode": ["backup", "snapshot", "archive", "retention"],
            "revenant_mode": ["restore", "recovery", "phoenix", "failover"],
            "shadow_ops": ["covert", "stealth", "sensitive", "high-risk"],
            "self_improvement_loop": ["optimize", "improve", "loop", "tune"],
            "loop_watchdog": ["monitor", "alert", "watchdog", "triage"],
        }
        for mode, words in keyword_map.items():
            if any(word in text for word in words):
                tags.add(mode)
        if not tags:
            tags.add("self_improvement_loop")
        return sorted(tags)

    def map_pillars(self, task_text: str) -> list[str]:
        text = task_text.lower()
        pillars = set()
        if any(token in text for token in ("risk", "secure", "incident", "recover", "survive")):
            pillars.add("survive_minimize_risk")
        if any(token in text for token in ("legal", "buffer", "compliance", "cash", "reserve")):
            pillars.add("financial_legal_buffer")
        if any(token in text for token in ("passive", "income", "revenue", "monetize")):
            pillars.add("passive_income_independence")
        if any(token in text for token in ("community", "public", "impact", "archive", "education")):
            pillars.add("long_term_community_impact")
        return sorted(pillars)

    def evaluate_transcendence(self, state: TranscendenceState) -> dict[str, Any]:
        checks = {
            "archive_published_and_indexed": state.archive_published_and_indexed,
            "external_collaborator_interacted": state.external_collaborator_interacted,
            "deep_research_no_improvement_cycles>=3": state.deep_research_no_improvement_cycles >= 3,
            "revenue_stream_usd_monthly>=1000": state.revenue_stream_usd_monthly >= 1000.0,
            "publish_sync_full_cycles>=3": state.publish_sync_full_cycles >= 3,
        }
        return {
            "eligible": all(checks.values()),
            "checks": checks,
        }

    def set_mode(
        self,
        mode: str,
        approved_by: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        clean = mode.strip().lower()
        if clean not in {"structured", "wild"}:
            raise ValueError("mode must be 'structured' or 'wild'")
        if clean == "wild" and not approved_by.strip():
            raise ValueError("wild mode requires explicit approved_by")
        self.state["current_mode"] = clean
        self.state["wild_mode_approved_by"] = approved_by.strip()
        self.state["wild_mode_reason"] = reason.strip()
        self.save()
        return {
            "current_mode": self.state["current_mode"],
            "wild_mode_approved_by": self.state["wild_mode_approved_by"],
            "wild_mode_reason": self.state["wild_mode_reason"],
        }

    def auto_revert_if_risky(self, risk_score: float, threshold: float = 0.6) -> dict[str, Any]:
        mode = self.state.get("current_mode", "structured")
        reverted = False
        if mode == "wild" and risk_score >= threshold:
            self.state["current_mode"] = "structured"
            reverted = True
            self.save()
        return {
            "reverted": reverted,
            "current_mode": self.state.get("current_mode", "structured"),
            "risk_score": risk_score,
            "threshold": threshold,
        }

    def _prune_window(self, events: list[str], seconds: int) -> list[str]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        keep = []
        for value in events:
            try:
                ts = datetime.fromisoformat(value)
            except ValueError:
                continue
            if ts >= cutoff:
                keep.append(value)
        return keep

    def _record_window_event(self, key: str) -> int:
        rows = list(self.state.get(key, []))
        rows = self._prune_window(rows, seconds=3600)
        rows.append(utc_now_iso())
        self.state[key] = rows
        self.save()
        return len(rows)

    def decide_action(
        self,
        action_type: str,
        irreversible: bool = False,
        preapproved: bool = False,
        trade_position_pct: float = 0.0,
        drawdown_pct: float = 0.0,
    ) -> SafetyDecision:
        if irreversible and not preapproved:
            return SafetyDecision(
                allowed=False,
                reason="Irreversible action requires explicit operator confirmation.",
                requires_operator_confirmation=True,
            )
        if action_type == "trade":
            if drawdown_pct > 5.0:
                return SafetyDecision(
                    allowed=False,
                    reason="Trade blocked: drawdown exceeds 5% portfolio guardrail.",
                    requires_operator_confirmation=False,
                )
            if trade_position_pct > 2.5 and not preapproved:
                return SafetyDecision(
                    allowed=False,
                    reason="Trade >2.5% requires explicit pre-approval + dual verification.",
                    requires_operator_confirmation=True,
                )
            count = self._record_window_event("trade_window_events")
            if count > 12:
                return SafetyDecision(
                    allowed=False,
                    reason="Trade circuit breaker tripped: too many trades in one hour.",
                    requires_operator_confirmation=False,
                )
        if action_type == "post":
            count = self._record_window_event("post_window_events")
            if count > 20:
                return SafetyDecision(
                    allowed=False,
                    reason="Post circuit breaker tripped: too many publishes in one hour.",
                    requires_operator_confirmation=False,
                )
        return SafetyDecision(
            allowed=True,
            reason="Action allowed by current policy.",
            requires_operator_confirmation=False,
        )


class HandoffValidator:
    """Strict schema validator for inter-agent handoff packets."""

    def validate(self, payload: dict[str, Any]) -> HandoffPacket:
        missing = sorted(HANDOFF_REQUIRED_KEYS - set(payload))
        if missing:
            raise ValueError(f"handoff missing required key(s): {', '.join(missing)}")
        if payload.get("schema_version") != 1:
            raise ValueError("handoff schema_version must be 1")
        mode_tags = payload.get("mode_tags")
        if not isinstance(mode_tags, list) or not mode_tags:
            raise ValueError("handoff mode_tags must be a non-empty list")
        for tag in mode_tags:
            if tag not in CONTINUITY_MODES:
                raise ValueError(f"unknown mode tag in handoff: {tag}")
        history = payload.get("history")
        next_actions = payload.get("next_actions")
        params = payload.get("parameters")
        if not isinstance(history, list) or not isinstance(next_actions, list):
            raise ValueError("handoff history and next_actions must be lists")
        if not isinstance(params, dict):
            raise ValueError("handoff parameters must be a mapping")
        for key in ("from_agent", "to_agent", "objective"):
            if not str(payload.get(key, "")).strip():
                raise ValueError(f"handoff {key} must be non-empty")
        return HandoffPacket(
            schema_version=1,
            from_agent=str(payload["from_agent"]).strip(),
            to_agent=str(payload["to_agent"]).strip(),
            created_at=str(payload["created_at"]).strip(),
            mode_tags=[str(item) for item in mode_tags],
            objective=str(payload["objective"]).strip(),
            history=[str(item) for item in history],
            parameters=dict(params),
            next_actions=[str(item) for item in next_actions],
            prime_pillars=[str(item) for item in payload.get("prime_pillars", [])],
        )


class PublishGuard:
    """Immutable section + alignment checks before public sync/publish."""

    def immutable_sections(self, text: str) -> dict[str, str]:
        sections = {}
        for match in IMMUTABLE_SECTION_RE.finditer(text):
            name = match.group(1)
            body = match.group(2)
            sections[name] = body
        return sections

    def compute_diff(self, original_text: str, updated_text: str) -> list[str]:
        return list(
            difflib.unified_diff(
                original_text.splitlines(),
                updated_text.splitlines(),
                fromfile="original",
                tofile="updated",
                lineterm="",
            )
        )

    def check_alignment(self, text: str) -> list[str]:
        issues = []
        lower = text.lower()
        if "real name" in lower or "home address" in lower:
            issues.append("Sensitive identity phrase detected in candidate publish text.")
        secret_markers = (
            "-----begin private key-----",
            "xoxb-",
            "ghp_",
            "sk-",
            "api_key=",
            "secret_key=",
            "authorization: bearer ",
        )
        if any(marker in lower for marker in secret_markers):
            issues.append("Potential secret/token marker detected in candidate publish text.")
        if "guaranteed profit" in lower:
            issues.append("High-risk claim detected: 'guaranteed profit'.")
        return issues

    def evaluate(
        self,
        baseline_path: Path,
        candidate_path: Path,
    ) -> dict[str, Any]:
        baseline = _safe_read(baseline_path)
        candidate = _safe_read(candidate_path)
        immutable_base = self.immutable_sections(baseline)
        immutable_cand = self.immutable_sections(candidate)
        immutable_violations = []
        for key, base_body in immutable_base.items():
            if key not in immutable_cand:
                immutable_violations.append(f"Missing immutable section: {key}")
            elif immutable_cand[key] != base_body:
                immutable_violations.append(f"Immutable section modified: {key}")
        alignment_issues = self.check_alignment(candidate)
        diff = self.compute_diff(baseline, candidate)
        return {
            "baseline_path": str(baseline_path),
            "candidate_path": str(candidate_path),
            "immutable_violations": immutable_violations,
            "alignment_issues": alignment_issues,
            "allowed_to_publish": not immutable_violations and not alignment_issues,
            "diff_preview": diff[:120],
            "checked_at": utc_now_iso(),
        }


class DualLLMVerifier:
    """Two-model generation + validation protocol with failover-compatible output."""

    def verify(
        self,
        prompt: str,
        draft: str,
        primary_model: str = "gpt-5",
        secondary_model: str = "claude-opus",
        secondary_available: bool = True,
    ) -> VerificationResult:
        # Offline-friendly scaffold:
        # - generation is provided by `draft`
        # - validation uses deterministic checks
        # - if secondary is unavailable, fail over to a strict local validator
        generation = draft.strip()
        checks = []
        if len(generation) < 30:
            checks.append("Draft is too short for high-confidence verification.")
        if "TODO" in generation:
            checks.append("Draft contains TODO markers.")
        if not re.search(r"[.!?]$", generation):
            checks.append("Draft does not end with sentence punctuation.")

        if secondary_available:
            validation = (
                "secondary-validator: pass"
                if not checks
                else f"secondary-validator: issues={'; '.join(checks)}"
            )
            agreed = not checks
            failover_used = False
        else:
            validation = (
                "local-failover-validator: pass"
                if not checks
                else f"local-failover-validator: issues={'; '.join(checks)}"
            )
            agreed = not checks
            failover_used = True
        status = "approved" if agreed else "needs_revision"
        return VerificationResult(
            status=status,
            primary_model=primary_model,
            secondary_model=secondary_model,
            generation=generation,
            validation=validation,
            agreed=agreed,
            failover_used=failover_used,
        )


class ProjectArkManager:
    """Layered snapshot/retention workflow with restore-test and phoenix scaffold."""

    def __init__(self, snapshots_dir: Path) -> None:
        self.snapshots_dir = snapshots_dir

    def _snapshot_name(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"project-ark-{stamp}.tar.gz"

    def _run_offsite_sync(self, command_template: str, snapshot_path: Path) -> bool:
        command = command_template.replace("{snapshot_path}", str(snapshot_path))
        argv = shlex.split(command)
        if not argv:
            return False
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return proc.returncode == 0

    @staticmethod
    def _safe_members(tar: tarfile.TarFile, destination: Path) -> list[tarfile.TarInfo]:
        root = destination.resolve()
        safe: list[tarfile.TarInfo] = []
        for member in tar.getmembers():
            name = member.name
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"unsafe archive member path: {name}")
            if member.issym() or member.islnk():
                raise ValueError(f"unsafe archive link member: {name}")
            target = (root / name).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"path traversal detected in archive member: {name}") from exc
            safe.append(member)
        return safe

    def create_snapshot(
        self,
        include_paths: Iterable[Path],
        retention_days: int = 7,
        offsite_copy_command: str = "",
    ) -> SnapshotInfo:
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.snapshots_dir / self._snapshot_name()
        include = [Path(item) for item in include_paths]

        with tarfile.open(snapshot_path, "w:gz") as tar:
            for path in include:
                if path.exists():
                    tar.add(path, arcname=path.name)

        restore_ok = self.restore_test(snapshot_path)
        offsite_attempted = False
        offsite_succeeded = False
        if offsite_copy_command.strip():
            offsite_attempted = True
            offsite_succeeded = self._run_offsite_sync(
                command_template=offsite_copy_command,
                snapshot_path=snapshot_path,
            )
        self.prune(retention_days=retention_days)
        return SnapshotInfo(
            snapshot_path=str(snapshot_path),
            created_at=utc_now_iso(),
            retention_days=retention_days,
            included_paths=[str(item) for item in include],
            restore_test_passed=restore_ok,
            offsite_sync_attempted=offsite_attempted,
            offsite_sync_succeeded=offsite_succeeded,
        )

    def list_snapshots(self) -> list[Path]:
        if not self.snapshots_dir.exists():
            return []
        rows = sorted(self.snapshots_dir.glob("project-ark-*.tar.gz"))
        return rows

    def prune(self, retention_days: int = 7) -> list[str]:
        removed = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        for path in self.list_snapshots():
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                path.unlink(missing_ok=True)
                removed.append(str(path))
        return removed

    def restore_test(self, snapshot_path: Path) -> bool:
        if not snapshot_path.exists():
            return False
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "restore-test"
            target.mkdir(parents=True, exist_ok=True)
            try:
                with tarfile.open(snapshot_path, "r:gz") as tar:
                    members = self._safe_members(tar, target)
                    tar.extractall(path=target, members=members)
            except (tarfile.TarError, OSError, ValueError):
                return False
            return any(target.iterdir())

    def phoenix_redeploy(self, snapshot_path: Path, destination: Path) -> dict[str, Any]:
        if not snapshot_path.exists():
            raise FileNotFoundError(f"snapshot not found: {snapshot_path}")
        destination.mkdir(parents=True, exist_ok=True)
        with tarfile.open(snapshot_path, "r:gz") as tar:
            members = self._safe_members(tar, destination)
            tar.extractall(path=destination, members=members)
        return {
            "event": "recovery_event",
            "snapshot": str(snapshot_path),
            "destination": str(destination),
            "restored_at": utc_now_iso(),
        }


class DominionOrchestrator:
    """Top-level facade combining policy, memory, bus, guard, and backup managers."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.policy = DominionPolicyEngine(state_dir / "dominion-policy.json")
        self.memory = CheckpointMemory(state_dir / "dominion-memory.json")
        self.bus = DominionMessageBus(state_dir / "dominion-events.jsonl")
        self.handoffs = HandoffValidator()
        self.publish_guard = PublishGuard()
        self.verifier = DualLLMVerifier()
        self.ark = ProjectArkManager(state_dir / "project-ark")
        self.tuner = AutoTuneEngine(state_dir / "dominion-autotune.json")
        self.catalyst = CatalystBoard(state_dir / "dominion-catalyst.json")

    def status(self) -> dict[str, Any]:
        recent = self.bus.tail(limit=10)
        return {
            "generated_at": utc_now_iso(),
            "mission_pillars": MISSION_PILLARS,
            "continuity_modes": CONTINUITY_MODES,
            "dominion_agents": DOMINION_AGENTS,
            "current_mode": self.policy.state.get("current_mode", "structured"),
            "checkpoint_count": len(self.memory.rows),
            "recent_event_count": len(recent),
            "recent_events": recent[-5:],
        }

    def bootstrap_events(self) -> list[dict[str, Any]]:
        events = []
        for definition in DOMINION_AGENTS:
            events.append(
                self.bus.emit(
                    event_type="agent_bootstrapped",
                    source="dominion_orchestrator",
                    payload={
                        "agent_id": definition["agent_id"],
                        "purpose": definition["purpose"],
                        "triggers": definition["triggers"],
                        "outputs": definition["outputs"],
                    },
                )
            )
        return events

    def run_cycle(self, objective: str) -> dict[str, Any]:
        mode_tags = self.policy.classify_modes(objective)
        pillars = self.policy.map_pillars(objective)
        checkpoint = self.memory.add_checkpoint(
            summary=objective,
            mode_tags=mode_tags,
            metadata={"pillars": pillars},
        )
        event = self.bus.emit(
            event_type="self_improvement_cycle",
            source="dominion_orchestrator",
            payload={
                "objective": objective,
                "mode_tags": mode_tags,
                "pillars": pillars,
                "checkpoint_id": checkpoint["checkpoint_id"],
            },
        )
        recommendations = []
        if not pillars:
            recommendations.append(
                "Objective does not map to prime pillars clearly; refine the objective statement."
            )
        if "self_improvement_loop" not in mode_tags:
            recommendations.append("Add explicit self_improvement_loop mode tagging.")
        return {
            "checkpoint": checkpoint,
            "event": event,
            "recommendations": recommendations,
        }

    def build_handoff(self, payload: dict[str, Any]) -> dict[str, Any]:
        packet = self.handoffs.validate(payload)
        self.bus.emit(
            event_type="handoff_created",
            source=packet.from_agent,
            payload=asdict(packet),
        )
        return asdict(packet)


class AutoTuneEngine:
    """Heuristic tuner for CPU/memory/queue metrics."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.state = _safe_json_load(self.state_path, {"instructions": []})
        if not isinstance(self.state, dict):
            self.state = {"instructions": []}
        self.save()

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def evaluate(self, cpu_pct: float, memory_pct: float, queue_depth: int) -> TuningInstruction:
        if cpu_pct < 50.0 and memory_pct < 70.0 and queue_depth > 10:
            action = "increase_concurrency"
            rationale = "CPU headroom available while queue backlog is high."
            risk = "low"
        elif memory_pct > 80.0:
            action = "throttle_tasks"
            rationale = "Memory pressure is high; reduce parallel load."
            risk = "medium"
        elif cpu_pct > 90.0:
            action = "cooldown_and_scale_out"
            rationale = "CPU saturation detected; add workers or reduce duty cycle."
            risk = "medium"
        else:
            action = "hold_configuration"
            rationale = "Metrics within target band."
            risk = "low"

        row = TuningInstruction(
            instruction_id=f"tune-{len(self.state.get('instructions', [])) + 1:05d}",
            created_at=utc_now_iso(),
            source="auto_tune_engine",
            cpu_pct=round(cpu_pct, 2),
            memory_pct=round(memory_pct, 2),
            queue_depth=int(queue_depth),
            action=action,
            rationale=rationale,
            risk_level=risk,
        )
        instructions = list(self.state.get("instructions", []))
        instructions.append(asdict(row))
        self.state["instructions"] = instructions[-500:]
        self.save()
        return row

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = list(self.state.get("instructions", []))
        return rows[-max(1, limit) :]


class CatalystBoard:
    """Evolution sprint board for proposing, validating, and merging upgrades."""

    VALID_STATUS = {"proposed", "sandbox_validated", "merged", "rejected"}

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.state = _safe_json_load(self.state_path, {"items": []})
        if not isinstance(self.state, dict):
            self.state = {"items": []}
        self.save()

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def list_items(self) -> list[dict[str, Any]]:
        return list(self.state.get("items", []))

    def propose(
        self,
        title: str,
        hypothesis: str,
        metric: str,
        baseline: float,
        candidate: float,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        row = CatalystItem(
            item_id=f"cat-{len(self.state.get('items', [])) + 1:05d}",
            title=title.strip(),
            hypothesis=hypothesis.strip(),
            metric=metric.strip(),
            baseline=float(baseline),
            candidate=float(candidate),
            status="proposed",
            created_at=now,
            updated_at=now,
        )
        items = list(self.state.get("items", []))
        items.append(asdict(row))
        self.state["items"] = items
        self.save()
        return asdict(row)

    def update_status(self, item_id: str, status: str) -> dict[str, Any]:
        if status not in self.VALID_STATUS:
            raise ValueError(f"invalid catalyst status: {status}")
        items = list(self.state.get("items", []))
        for item in items:
            if item.get("item_id") == item_id:
                item["status"] = status
                item["updated_at"] = utc_now_iso()
                self.state["items"] = items
                self.save()
                return item
        raise KeyError(f"unknown catalyst item: {item_id}")

    def merge_if_improved(self, item_id: str) -> dict[str, Any]:
        items = list(self.state.get("items", []))
        for item in items:
            if item.get("item_id") != item_id:
                continue
            baseline = float(item.get("baseline", 0.0))
            candidate = float(item.get("candidate", 0.0))
            improved = candidate > baseline
            item["status"] = "merged" if improved else "rejected"
            item["updated_at"] = utc_now_iso()
            self.state["items"] = items
            self.save()
            return {
                "item_id": item_id,
                "metric": item.get("metric"),
                "baseline": baseline,
                "candidate": candidate,
                "improved": improved,
                "status": item["status"],
            }
        raise KeyError(f"unknown catalyst item: {item_id}")
