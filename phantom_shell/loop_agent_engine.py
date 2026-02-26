"""Loop Agent engine with recursive improvement cycles and interactive tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request


DANGEROUS_SHELL_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\{:\|:\&\};:",
]


TOOL_CATALOG = [
    {
        "name": "Codex CLI",
        "setup_cost": "Low",
        "risk": "Low-Medium",
        "expected_gain": "High",
        "reason": "Fast code iteration, file ops, and terminal-native workflows.",
        "tags": {"coding", "automation", "terminal", "agent"},
    },
    {
        "name": "OpenAI Responses API Agents",
        "setup_cost": "Medium",
        "risk": "Medium",
        "expected_gain": "High",
        "reason": "Production-grade agent orchestration with structured tool use.",
        "tags": {"agent", "api", "automation", "integration"},
    },
    {
        "name": "LangGraph",
        "setup_cost": "Medium",
        "risk": "Medium",
        "expected_gain": "High",
        "reason": "Stateful graphs for recursive loops and checkpoints.",
        "tags": {"agent", "workflow", "state", "orchestration"},
    },
    {
        "name": "AutoGen",
        "setup_cost": "Medium",
        "risk": "Medium",
        "expected_gain": "Medium-High",
        "reason": "Multi-agent collaboration patterns for decomposition.",
        "tags": {"agent", "multi-agent", "orchestration", "experiments"},
    },
    {
        "name": "CrewAI",
        "setup_cost": "Low-Medium",
        "risk": "Medium",
        "expected_gain": "Medium-High",
        "reason": "Role-based delegation and fast team-like automation.",
        "tags": {"agent", "roles", "automation", "ops"},
    },
    {
        "name": "GitHub Actions",
        "setup_cost": "Low",
        "risk": "Low-Medium",
        "expected_gain": "High",
        "reason": "Automates verification and continuous loop execution in CI.",
        "tags": {"ci", "automation", "testing", "devops"},
    },
    {
        "name": "Docker",
        "setup_cost": "Medium",
        "risk": "Low-Medium",
        "expected_gain": "Medium-High",
        "reason": "Reproducible runtime isolation for autonomous experiments.",
        "tags": {"containers", "reproducibility", "devops", "ops"},
    },
    {
        "name": "OpenTelemetry",
        "setup_cost": "Medium",
        "risk": "Low",
        "expected_gain": "Medium-High",
        "reason": "Metrics/traces to measure loop quality and latency over time.",
        "tags": {"observability", "metrics", "telemetry", "monitoring"},
    },
    {
        "name": "Prefect",
        "setup_cost": "Medium",
        "risk": "Low-Medium",
        "expected_gain": "Medium",
        "reason": "Reliable scheduled workflows with retries and state tracking.",
        "tags": {"workflow", "scheduling", "automation", "ops"},
    },
    {
        "name": "N8N",
        "setup_cost": "Low-Medium",
        "risk": "Low-Medium",
        "expected_gain": "Medium",
        "reason": "No-code/low-code integration hub for quick loop expansion.",
        "tags": {"automation", "integration", "ops", "workflow"},
    },
]


TARGET_CATALOG = [
    {
        "target": "Code quality and release cadence",
        "reason": "Recursive loops compound quickly with tests, linting, and CI.",
    },
    {
        "target": "Incident response and runbook hardening",
        "reason": "Short feedback cycles reduce response time and missed steps.",
    },
    {
        "target": "Sales funnel conversion",
        "reason": "A/B loops produce measurable growth on copy and landing flow.",
    },
    {
        "target": "Operations automation backlog",
        "reason": "Continuous elimination of repetitive tasks yields quick ROI.",
    },
    {
        "target": "Knowledge base maintenance",
        "reason": "Looping on doc quality improves onboarding and execution speed.",
    },
]


DEFAULT_PLAYBOOK = [
    "Prefer the smallest change that can prove or falsify a hypothesis.",
    "Measure every cycle with objective metrics before changing direction.",
    "Promote winning patterns into the default operating checklist.",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, round(value, 2)))


def score_fit(value: float) -> str:
    if value >= 5:
        return "High"
    if value >= 3:
        return "Medium"
    return "Low"


@dataclass
class ToolRecommendation:
    name: str
    fit: str
    setup_cost: str
    risk: str
    expected_gain: str
    reason: str


@dataclass
class LoopCycle:
    cycle_number: int
    timestamp: str
    objective: str
    baseline: dict[str, Any]
    change_applied: str
    result_delta: dict[str, Any]
    self_update: str
    recommended_tools: dict[str, Any]
    next_decision: str


@dataclass
class LoopAgentState:
    objective: str = ""
    baseline_score: float = 50.0
    current_score: float = 50.0
    strategy: str = "Define one KPI and run fast measured experiments."
    playbook: list[str] = field(default_factory=lambda: list(DEFAULT_PLAYBOOK))
    cycles: list[LoopCycle] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now_iso)


class LoopAgentEngine:
    """Stateful loop engine with recursive improvement and utility tools."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.state = LoopAgentState()
        self.load_state()

    def load_state(self) -> None:
        if not self.state_path.exists():
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        cycles = [LoopCycle(**item) for item in payload.get("cycles", [])]
        self.state = LoopAgentState(
            objective=payload.get("objective", ""),
            baseline_score=float(payload.get("baseline_score", 50.0)),
            current_score=float(payload.get("current_score", 50.0)),
            strategy=payload.get(
                "strategy", "Define one KPI and run fast measured experiments."
            ),
            playbook=list(payload.get("playbook", list(DEFAULT_PLAYBOOK))),
            cycles=cycles,
            updated_at=payload.get("updated_at", utc_now_iso()),
        )

    def save_state(self) -> None:
        self.state.updated_at = utc_now_iso()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self.state)
        self.state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def reset_state(self) -> None:
        self.state = LoopAgentState()
        self.save_state()

    def status(self) -> dict[str, Any]:
        return {
            "objective": self.state.objective or "(not set)",
            "baseline_score": self.state.baseline_score,
            "current_score": self.state.current_score,
            "cycle_count": len(self.state.cycles),
            "strategy": self.state.strategy,
            "updated_at": self.state.updated_at,
        }

    def set_objective(self, objective: str) -> None:
        self.state.objective = objective.strip()
        self.save_state()

    def set_baseline(self, score: float, strategy: str = "") -> None:
        clean_score = clamp_score(score)
        self.state.baseline_score = clean_score
        self.state.current_score = clean_score
        if strategy.strip():
            self.state.strategy = strategy.strip()
        self.save_state()

    def cycle_history(self, limit: int | None = None) -> list[LoopCycle]:
        if limit is None or limit >= len(self.state.cycles):
            return list(self.state.cycles)
        return self.state.cycles[-limit:]

    def _candidate_improvements(self, note: str) -> list[str]:
        objective = self.state.objective.lower()
        note_text = note.lower()
        candidates = [
            "Define one primary KPI and a 48-hour measurable target.",
            "Automate one repetitive step with script or API integration.",
            "Instrument the loop with explicit metrics and a quick review checkpoint.",
        ]
        if any(token in objective for token in ("code", "dev", "repo", "test", "ci")):
            candidates.append(
                "Run tests plus static checks for every iteration before scoring."
            )
        if any(
            token in objective for token in ("sales", "funnel", "marketing", "growth")
        ):
            candidates.append(
                "Create one A/B experiment and promote only statistically better copy."
            )
        if any(
            token in objective
            for token in ("incident", "security", "response", "forensics")
        ):
            candidates.append(
                "Convert critical response steps into a timed deterministic checklist."
            )
        if any(token in note_text for token in ("slow", "latency", "blocked")):
            candidates.append(
                "Trim work-in-progress and parallelize independent tasks to reduce delay."
            )
        if any(token in note_text for token in ("quality", "bug", "regression")):
            candidates.append(
                "Add a targeted regression test for the current highest-risk failure path."
            )
        unique = []
        seen = set()
        for item in candidates:
            if item not in seen:
                unique.append(item)
                seen.add(item)
        return unique

    def _projected_delta(self, change_applied: str, cycle_number: int) -> float:
        material = f"{self.state.objective}|{change_applied}|{cycle_number}"
        raw = sum(ord(ch) for ch in material) % 700
        return round((raw / 700.0) * 8.0 - 1.5, 2)

    def recommend_tools(self, limit: int = 6) -> list[ToolRecommendation]:
        objective_terms = set(re.findall(r"[a-z0-9]+", self.state.objective.lower()))

        def rank(entry: dict[str, Any]) -> tuple[float, int]:
            overlap = len(objective_terms.intersection(entry["tags"]))
            cycle_bonus = 1 if len(self.state.cycles) >= 2 else 0
            automation_bonus = 1 if "automation" in entry["tags"] else 0
            score = float(overlap + cycle_bonus + automation_bonus + 1)
            setup_rank = 0 if entry["setup_cost"].lower().startswith("low") else 1
            return score, -setup_rank

        ranked = sorted(TOOL_CATALOG, key=rank, reverse=True)
        recommendations = []
        for entry in ranked[: max(1, limit)]:
            fit_raw, _ = rank(entry)
            recommendations.append(
                ToolRecommendation(
                    name=entry["name"],
                    fit=score_fit(fit_raw),
                    setup_cost=entry["setup_cost"],
                    risk=entry["risk"],
                    expected_gain=entry["expected_gain"],
                    reason=entry["reason"],
                )
            )
        return recommendations

    def recommend_targets(self, limit: int = 4) -> list[dict[str, str]]:
        return TARGET_CATALOG[: max(1, limit)]

    def run_cycle(self, note: str = "", measured_score: float | None = None) -> LoopCycle:
        if not self.state.objective:
            self.state.objective = "Increase execution throughput with recursive loops."

        cycle_number = len(self.state.cycles) + 1
        baseline = {
            "score": self.state.current_score,
            "strategy": self.state.strategy,
            "note": note.strip(),
        }
        candidates = self._candidate_improvements(note)
        selected = candidates[0]
        projected_delta = self._projected_delta(selected, cycle_number)
        previous_score = self.state.current_score
        if measured_score is None:
            updated_score = clamp_score(previous_score + projected_delta)
            measurement_mode = "projected"
        else:
            updated_score = clamp_score(measured_score)
            measurement_mode = "measured"
        delta = round(updated_score - previous_score, 2)
        self.state.current_score = updated_score
        self.state.strategy = selected

        if delta >= 2.0:
            self_update = (
                f"Promote pattern to playbook default: {selected} "
                "(evidence: positive delta >= 2.0)."
            )
        elif delta >= 0.0:
            self_update = (
                f"Keep change as optional tactic and collect one more data point: {selected}."
            )
        else:
            fallback = candidates[1] if len(candidates) > 1 else candidates[0]
            self_update = (
                f"Demote current tactic and test alternate next cycle: {fallback}."
            )

        if self_update not in self.state.playbook:
            self.state.playbook.append(self_update)

        recommended_tools = {
            "tools": [asdict(item) for item in self.recommend_tools()],
            "targets": self.recommend_targets(),
        }
        if delta > 0.5:
            next_decision = "continue"
        elif delta >= 0.0:
            next_decision = "continue_with_alternate_candidate"
        else:
            next_decision = "reframe_objective_or_switch_strategy"

        cycle = LoopCycle(
            cycle_number=cycle_number,
            timestamp=utc_now_iso(),
            objective=self.state.objective,
            baseline=baseline,
            change_applied=selected,
            result_delta={
                "mode": measurement_mode,
                "projected_delta": projected_delta,
                "actual_delta": delta,
                "new_score": updated_score,
            },
            self_update=self_update,
            recommended_tools=recommended_tools,
            next_decision=next_decision,
        )
        self.state.cycles.append(cycle)
        self.save_state()
        return cycle

    def shell_risk(self, command: str) -> str | None:
        lowered = command.lower()
        for pattern in DANGEROUS_SHELL_PATTERNS:
            if re.search(pattern, lowered):
                return pattern
        return None

    def run_shell(self, command: str, timeout_seconds: int = 60) -> dict[str, Any]:
        proc = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    def run_python(self, snippet: str, timeout_seconds: int = 60) -> dict[str, Any]:
        proc = subprocess.run(
            [sys.executable, "-c", snippet],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    def _fetch_url(self, url: str, timeout_seconds: int = 20) -> str:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
        return body.decode("utf-8", errors="ignore")

    def fetch_web_preview(
        self, url: str, timeout_seconds: int = 20, char_limit: int = 4000
    ) -> str:
        html = self._fetch_url(url, timeout_seconds=timeout_seconds)
        text = re.sub(r"<script.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:char_limit]

    def search_web(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote_plus(query)}"
        html = self._fetch_url(url, timeout_seconds=20)
        matches = re.findall(
            r'<a rel="nofollow" href="([^"]+)">(.+?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        results = []
        for href, title in matches:
            clean_title = re.sub(r"<[^>]+>", "", unescape(title)).strip()
            if not clean_title:
                continue
            results.append({"title": clean_title, "url": href})
            if len(results) >= limit:
                break
        return results

    def export_markdown_report(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Loop Agent Report",
            "",
            f"- Generated: {utc_now_iso()}",
            f"- Objective: {self.state.objective or '(not set)'}",
            f"- Baseline score: {self.state.baseline_score}",
            f"- Current score: {self.state.current_score}",
            f"- Cycle count: {len(self.state.cycles)}",
            "",
            "## Playbook",
            "",
        ]
        for item in self.state.playbook:
            lines.append(f"- {item}")
        lines.extend(["", "## Cycles", ""])
        for cycle in self.state.cycles:
            lines.extend(
                [
                    f"### Cycle {cycle.cycle_number}",
                    f"- Timestamp: {cycle.timestamp}",
                    f"- Baseline score: {cycle.baseline.get('score')}",
                    f"- Strategy: {cycle.baseline.get('strategy')}",
                    f"- Change applied: {cycle.change_applied}",
                    f"- Delta: {cycle.result_delta.get('actual_delta')}",
                    f"- New score: {cycle.result_delta.get('new_score')}",
                    f"- Self update: {cycle.self_update}",
                    f"- Next decision: {cycle.next_decision}",
                    "",
                    "Recommended tools:",
                ]
            )
            for tool in cycle.recommended_tools.get("tools", []):
                lines.append(
                    "- {name} | fit={fit} | setup={setup_cost} | risk={risk} | gain={expected_gain}".format(
                        **tool
                    )
                )
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return path
