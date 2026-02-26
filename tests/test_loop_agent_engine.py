import tempfile
import unittest
from pathlib import Path

from phantom_shell.loop_agent_engine import LoopAgentEngine


class LoopAgentEngineTests(unittest.TestCase):
    def test_cycle_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            engine = LoopAgentEngine(state_path=state_path)
            engine.set_objective("Improve CI velocity and code quality")
            engine.set_baseline(60, "Run tests each iteration")

            cycle = engine.run_cycle(note="speed up feedback", measured_score=63)
            self.assertEqual(cycle.cycle_number, 1)
            self.assertEqual(cycle.result_delta["mode"], "measured")
            self.assertEqual(cycle.result_delta["actual_delta"], 3.0)
            self.assertTrue(cycle.recommended_tools["tools"])
            self.assertEqual(engine.status()["cycle_count"], 1)

            reloaded = LoopAgentEngine(state_path=state_path)
            self.assertEqual(reloaded.status()["cycle_count"], 1)
            self.assertEqual(reloaded.state.current_score, 63.0)

    def test_shell_risk_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            engine = LoopAgentEngine(state_path=state_path)
            self.assertIsNotNone(engine.shell_risk("rm -rf /tmp/foo"))
            self.assertIsNone(engine.shell_risk("ls -la"))

    def test_export_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state_path = base / "state.json"
            report_path = base / "report.md"
            engine = LoopAgentEngine(state_path=state_path)
            engine.set_objective("Improve operations automation")
            engine.run_cycle(note="first run", measured_score=55)
            exported = engine.export_markdown_report(report_path)
            self.assertEqual(exported, report_path)
            self.assertTrue(report_path.exists())
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("Loop Agent Report", text)
            self.assertIn("Cycle 1", text)


if __name__ == "__main__":
    unittest.main()
