import tempfile
import unittest
from pathlib import Path

from phantom_shell.ecosystem_intelligence_agent import EcosystemIntelligenceAgent


class StubEcosystemIntelligenceAgent(EcosystemIntelligenceAgent):
    def search_web(self, query: str) -> list[dict[str, str]]:
        return [
            {"title": f"Result for {query}", "url": "https://example.com/a"},
            {"title": "Another result", "url": "https://example.com/b"},
        ]


class EcosystemIntelligenceAgentTests(unittest.TestCase):
    def test_analysis_output_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".loop-agent").mkdir(parents=True)
            (root / "scripts").mkdir()
            (root / "tests").mkdir()
            (root / "docs").mkdir()
            (root / "requirements.txt").write_text("PyYAML==6.0.2\n", encoding="utf-8")
            (root / "scripts" / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (root / "docs" / "readme.md").write_text("x\n", encoding="utf-8")
            (root / ".loop-agent" / "universal-agent-state.json").write_text(
                '{"connectors":[{"connector_id":"c1","connector_type":"shell","enabled":true,"capabilities":["readonly"]}]}',
                encoding="utf-8",
            )
            (root / ".loop-agent" / "ecosystem-hub-state.json").write_text(
                '{"agents":[{"agent_id":"a1","enabled":true}]}',
                encoding="utf-8",
            )
            (root / ".loop-agent" / "chatgpt-mission-control.json").write_text(
                '{"tasks":[{"task_id":"t1","status":"queued"}]}',
                encoding="utf-8",
            )

            agent = StubEcosystemIntelligenceAgent(root, root / ".loop-agent", max_sources_per_query=2)
            inventory = agent.collect_local_inventory()
            queries = agent.build_queries(inventory)
            research = agent.run_research(queries)
            recs = agent.synthesize_recommendations(inventory, research)
            report = agent.build_markdown_report(inventory, research, recs)
            report_path = root / "reports" / "report.md"
            json_path = root / "reports" / "report.json"
            agent.write_outputs(report, inventory, research, recs, report_path, json_path)

            self.assertTrue(report_path.exists())
            self.assertTrue(json_path.exists())
            self.assertIn("Improvement Recommendations", report_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(recs), 4)

    def test_email_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = EcosystemIntelligenceAgent(Path(tmp), Path(tmp))
            with self.assertRaises(ValueError):
                agent.send_email("subject", "body", ["user@example.com"])


if __name__ == "__main__":
    unittest.main()
