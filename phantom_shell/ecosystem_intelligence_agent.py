"""Ecosystem intelligence agent with research and email digest delivery."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
import json
import os
import re
import smtplib
import ssl
import urllib.parse
import urllib.request


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def safe_read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines()]


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


@dataclass
class ResearchResult:
    query: str
    sources: list[dict[str, str]]


@dataclass
class Recommendation:
    component: str
    priority: str
    impact: str
    effort: str
    recommendation: str
    rationale: str
    source_links: list[str]


class EcosystemIntelligenceAgent:
    """Audits local autonomous ecosystem and researches improvements."""

    def __init__(
        self,
        repo_root: Path,
        state_dir: Path,
        max_sources_per_query: int = 5,
    ) -> None:
        self.repo_root = repo_root
        self.state_dir = state_dir
        self.max_sources_per_query = max_sources_per_query

    def collect_local_inventory(self) -> dict[str, Any]:
        ua_state = safe_read_json(self.state_dir / "universal-agent-state.json", {})
        hub_state = safe_read_json(self.state_dir / "ecosystem-hub-state.json", {})
        mission_state = safe_read_json(self.state_dir / "chatgpt-mission-control.json", {})
        requirements = safe_read_lines(self.repo_root / "requirements.txt")
        scripts = sorted(
            path.name
            for path in (self.repo_root / "scripts").glob("*")
            if path.is_file() and os.access(path, os.X_OK)
        )
        tests = sorted(
            path.name for path in (self.repo_root / "tests").glob("test_*.py") if path.is_file()
        )
        docs = sorted(
            path.name for path in (self.repo_root / "docs").glob("*.md") if path.is_file()
        )
        connectors = ua_state.get("connectors", [])
        agents = hub_state.get("agents", [])
        tasks = mission_state.get("tasks", [])
        return {
            "timestamp": utc_now_iso(),
            "connectors": connectors,
            "ecosystem_agents": agents,
            "mission_tasks": tasks,
            "requirements": requirements,
            "scripts": scripts,
            "tests": tests,
            "docs": docs,
        }

    def build_queries(self, inventory: dict[str, Any]) -> dict[str, list[str]]:
        connector_types = sorted(
            {str(item.get("connector_type", "")).lower() for item in inventory.get("connectors", [])}
        )
        queries = {
            "security": [
                "2026 best practices least privilege ai agent connectors",
                "2026 secure webhook design retries signing headers",
                "OpenAI API key security rotation policy best practices",
            ],
            "reliability": [
                "2026 multi-agent orchestration reliability patterns checkpoints",
                "idempotent workflow design for autonomous agents",
                "SRE practices for ai automation systems",
            ],
            "observability": [
                "OpenTelemetry for AI agents tracing 2026",
                "metrics for autonomous agent quality and drift",
            ],
            "productivity": [
                "high leverage dashboard patterns for operations control planes",
                "agent handoff packet templates deep research workflows",
            ],
        }
        if "webhook" in connector_types:
            queries["security"].append("webhook endpoint authentication signature verification python")
        if "openai" in connector_types:
            queries["reliability"].append("best retry backoff patterns OpenAI API Python")
        return queries

    def search_web(self, query: str) -> list[dict[str, str]]:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://duckduckgo.com/html/?q={encoded}"
        request = urllib.request.Request(
            url=url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ecosystem-intelligence-agent/1.0)"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            raw_html = response.read().decode("utf-8", errors="replace")
        rows: list[dict[str, str]] = []
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
            flags=re.IGNORECASE,
        )
        for match in pattern.finditer(raw_html):
            href = unescape(match.group("href"))
            title = normalize_space(re.sub(r"<.*?>", "", unescape(match.group("title"))))
            if href.startswith("//duckduckgo.com/l/?"):
                parsed = urllib.parse.urlparse("https:" + href)
                qs = urllib.parse.parse_qs(parsed.query)
                href = qs.get("uddg", [href])[0]
            if not href.startswith("http"):
                continue
            rows.append({"title": title, "url": href})
            if len(rows) >= self.max_sources_per_query:
                break
        return rows

    def run_research(self, queries_by_theme: dict[str, list[str]]) -> dict[str, list[ResearchResult]]:
        result: dict[str, list[ResearchResult]] = {}
        for theme, queries in queries_by_theme.items():
            result[theme] = []
            for query in queries:
                try:
                    sources = self.search_web(query)
                except Exception as exc:  # noqa: BLE001
                    sources = [{"title": f"search error: {exc}", "url": ""}]
                result[theme].append(ResearchResult(query=query, sources=sources))
        return result

    def _source_links(self, research_rows: list[ResearchResult], max_links: int = 3) -> list[str]:
        links: list[str] = []
        for row in research_rows:
            for source in row.sources:
                url = source.get("url", "")
                if url and url not in links:
                    links.append(url)
                    if len(links) >= max_links:
                        return links
        return links

    def synthesize_recommendations(
        self,
        inventory: dict[str, Any],
        research: dict[str, list[ResearchResult]],
    ) -> list[Recommendation]:
        connectors = inventory.get("connectors", [])
        agents = inventory.get("ecosystem_agents", [])
        mission_tasks = inventory.get("mission_tasks", [])
        disabled_connectors = [c for c in connectors if not c.get("enabled")]
        disabled_agents = [a for a in agents if not a.get("enabled")]
        recs: list[Recommendation] = [
            Recommendation(
                component="Connector Security Baseline",
                priority="P0",
                impact="High",
                effort="Medium",
                recommendation=(
                    "Add signed webhook verification, outbound domain allowlist, and per-connector secret rotation "
                    "with quarterly key expiry policy."
                ),
                rationale="Disabled templates indicate staging posture; formal controls reduce activation risk.",
                source_links=self._source_links(research.get("security", [])),
            ),
            Recommendation(
                component="Reliability Control Loop",
                priority="P1",
                impact="High",
                effort="Medium",
                recommendation=(
                    "Introduce connector-level retries with jittered backoff, idempotency keys for workflow steps, "
                    "and failure budget alerts."
                ),
                rationale="Multi-agent routing benefits from deterministic retries and explicit error budgets.",
                source_links=self._source_links(research.get("reliability", [])),
            ),
            Recommendation(
                component="Observability Layer",
                priority="P1",
                impact="High",
                effort="Medium",
                recommendation=(
                    "Add end-to-end traces (task_id, agent_id, connector_id), quality metrics, and weekly drift reports "
                    "for recommendation accuracy."
                ),
                rationale="Current audit logs are strong, but traces + scorecards unlock faster tuning.",
                source_links=self._source_links(research.get("observability", [])),
            ),
            Recommendation(
                component="Research Pipeline UX",
                priority="P2",
                impact="Medium",
                effort="Low",
                recommendation=(
                    "Auto-generate a Monday strategy digest: quick wins, strategic bets, blocked items, and "
                    "experiments-to-run-next with owner assignments."
                ),
                rationale="Mission tasks can evolve into a repeatable executive operating cadence.",
                source_links=self._source_links(research.get("productivity", [])),
            ),
        ]
        if disabled_connectors:
            recs.append(
                Recommendation(
                    component="Connector Enablement Gates",
                    priority="P0",
                    impact="High",
                    effort="Low",
                    recommendation=(
                        f"Keep {len(disabled_connectors)} connectors disabled until health checks, scope review, and "
                        "rollback test are completed in the same change window."
                    ),
                    rationale="Least-privilege posture is already in place; preserve it during scale-up.",
                    source_links=self._source_links(research.get("security", [])),
                )
            )
        if disabled_agents:
            recs.append(
                Recommendation(
                    component="Agent Permission Segmentation",
                    priority="P1",
                    impact="Medium",
                    effort="Low",
                    recommendation=(
                        f"Enable disabled agents ({len(disabled_agents)}) progressively with one connector each and "
                        "time-boxed observation windows."
                    ),
                    rationale="Gradual rollout reduces blast radius and improves root-cause speed.",
                    source_links=self._source_links(research.get("reliability", [])),
                )
            )
        if mission_tasks:
            recs.append(
                Recommendation(
                    component="Task Throughput Management",
                    priority="P2",
                    impact="Medium",
                    effort="Low",
                    recommendation=(
                        "Attach confidence scores and expected business impact to each queued mission task; "
                        "auto-prioritize by impact/effort ratio."
                    ),
                    rationale="Deep-research queue quality rises when prioritization is explicit.",
                    source_links=self._source_links(research.get("productivity", [])),
                )
            )
        return recs

    def build_markdown_report(
        self,
        inventory: dict[str, Any],
        research: dict[str, list[ResearchResult]],
        recommendations: list[Recommendation],
    ) -> str:
        lines = [
            "# AI Autonomous Ecosystem Intelligence Report",
            "",
            f"- Generated UTC: {utc_now_iso()}",
            f"- Connectors: {len(inventory.get('connectors', []))}",
            f"- Ecosystem agents: {len(inventory.get('ecosystem_agents', []))}",
            f"- Mission tasks: {len(inventory.get('mission_tasks', []))}",
            "",
            "## Improvement Recommendations",
            "",
        ]
        for idx, rec in enumerate(recommendations, start=1):
            lines.extend(
                [
                    f"### {idx}. {rec.component}",
                    f"- Priority: {rec.priority}",
                    f"- Impact: {rec.impact}",
                    f"- Effort: {rec.effort}",
                    f"- Recommendation: {rec.recommendation}",
                    f"- Rationale: {rec.rationale}",
                    "- Sources:",
                ]
            )
            if rec.source_links:
                lines.extend([f"  - {url}" for url in rec.source_links])
            else:
                lines.append("  - (none)")
            lines.append("")
        lines.extend(["## Research Queries and Results", ""])
        for theme, rows in research.items():
            lines.append(f"### Theme: {theme}")
            for row in rows:
                lines.append(f"- Query: {row.query}")
                if row.sources:
                    for source in row.sources:
                        title = source.get("title", "(untitled)")
                        url = source.get("url", "")
                        lines.append(f"  - {title} :: {url}")
                else:
                    lines.append("  - (no results)")
            lines.append("")
        lines.append(
            "## Creative Extensions\n"
            "- Add an automated experiment queue that proposes one A/B process improvement weekly.\n"
            "- Add anomaly detection for sudden connector error spikes and stale mission tasks.\n"
            "- Add executive digest mode: one-page summary + 3 decisions required this week."
        )
        lines.append("")
        return "\n".join(lines)

    def write_outputs(
        self,
        report_md: str,
        inventory: dict[str, Any],
        research: dict[str, list[ResearchResult]],
        recommendations: list[Recommendation],
        report_path: Path,
        json_path: Path,
    ) -> None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_md, encoding="utf-8")
        payload = {
            "generated_at": utc_now_iso(),
            "inventory": inventory,
            "research": {
                theme: [asdict(item) for item in rows] for theme, rows in research.items()
            },
            "recommendations": [asdict(item) for item in recommendations],
        }
        json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def send_email(
        self,
        subject: str,
        body_text: str,
        to_emails: list[str],
    ) -> None:
        host = os.getenv("EI_SMTP_HOST", "").strip()
        port = int(os.getenv("EI_SMTP_PORT", "587"))
        username = os.getenv("EI_SMTP_USER", "").strip()
        password = os.getenv("EI_SMTP_PASS", "").strip()
        sender = os.getenv("EI_SMTP_FROM", username).strip()
        if not host or not username or not password or not sender:
            raise ValueError(
                "Missing SMTP config. Set EI_SMTP_HOST, EI_SMTP_USER, EI_SMTP_PASS, EI_SMTP_FROM."
            )
        if not to_emails:
            raise ValueError("At least one recipient email is required.")
        recipients = [item.strip() for item in to_emails if item.strip()]
        if not recipients:
            raise ValueError("At least one valid recipient email is required.")
        message = (
            f"From: {sender}\r\n"
            f"To: {', '.join(recipients)}\r\n"
            f"Subject: {subject}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "\r\n"
            f"{body_text}"
        )
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=context)
            server.login(username, password)
            server.sendmail(sender, recipients, message.encode("utf-8"))
