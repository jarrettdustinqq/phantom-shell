import tempfile
import unittest
from pathlib import Path

from phantom_shell.autonomous_risk_triage import AutonomousRiskTriage


class AutonomousRiskTriageTests(unittest.TestCase):
    def test_build_report_with_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            log_path = base / "logs" / "universal_agent_audit.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                '{"ts_utc":"2026-02-26T23:00:00Z","action":"run","connector_id":"test","status":"error","details":{}}\n',
                encoding="utf-8",
            )
            (base / ".loop-agent").mkdir(parents=True)
            triage = AutonomousRiskTriage(state_dir=base / ".loop-agent", log_path=log_path)
            report = triage.build_report()
            self.assertTrue(report["events"])
            self.assertTrue(report["actions"])
            self.assertEqual(report["events"][0]["status"], "error")

    def test_event_id_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            log_path = base / "logs" / "universal_agent_audit.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                '{"ts_utc":"2026-02-26T23:00:00Z","action":"run","connector_id":"test","status":"ok","details":{"duration_ms":101}}\n',
                encoding="utf-8",
            )
            (base / ".loop-agent").mkdir(parents=True)
            triage = AutonomousRiskTriage(state_dir=base / ".loop-agent", log_path=log_path)
            first = [evt.event_id for evt in triage.build_events()]
            second = [evt.event_id for evt in triage.build_events()]
            self.assertEqual(first, second)

    def test_score_event_handles_bad_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            triage = AutonomousRiskTriage(state_dir=base / ".loop-agent", log_path=base / "no.log")
            score_null = triage.score_event({"action": "run", "status": "ok", "details": None})
            score_str = triage.score_event({"action": "run", "status": "ok", "details": {"duration_ms": "x"}})
            self.assertIsInstance(score_null, int)
            self.assertIsInstance(score_str, int)


if __name__ == "__main__":
    unittest.main()
