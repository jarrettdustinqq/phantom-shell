import tempfile
import unittest
from pathlib import Path

from phantom_shell.dominion_protocol import (
    DominionOrchestrator,
    DominionPolicyEngine,
    HandoffValidator,
    ProjectArkManager,
    PublishGuard,
    TranscendenceState,
)


def valid_handoff() -> dict:
    return {
        "schema_version": 1,
        "from_agent": "jarrett_prime",
        "to_agent": "mutator",
        "created_at": "2026-02-27T00:00:00+00:00",
        "mode_tags": ["forge_engine", "self_improvement_loop"],
        "objective": "Ship one measurable upgrade.",
        "history": ["Baseline set"],
        "parameters": {"kpi": "throughput"},
        "next_actions": ["Run test", "Measure delta"],
    }


class DominionProtocolTests(unittest.TestCase):
    def test_mode_classification_and_pillars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = DominionPolicyEngine(Path(tmp) / "policy.json")
            text = "Improve passive income funnel while minimizing risk with backups"
            modes = policy.classify_modes(text)
            pillars = policy.map_pillars(text)
            self.assertIn("ghost_market", modes)
            self.assertIn("vault_mode", modes)
            self.assertIn("passive_income_independence", pillars)
            self.assertIn("survive_minimize_risk", pillars)

    def test_transcendence_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = DominionPolicyEngine(Path(tmp) / "policy.json")
            state = TranscendenceState(
                archive_published_and_indexed=True,
                external_collaborator_interacted=True,
                deep_research_no_improvement_cycles=3,
                revenue_stream_usd_monthly=1200.0,
                publish_sync_full_cycles=3,
            )
            result = policy.evaluate_transcendence(state)
            self.assertTrue(result["eligible"])

    def test_action_safety_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = DominionPolicyEngine(Path(tmp) / "policy.json")
            blocked = policy.decide_action(action_type="trade", trade_position_pct=3.0)
            self.assertFalse(blocked.allowed)
            approved = policy.decide_action(
                action_type="trade",
                trade_position_pct=2.0,
                drawdown_pct=1.5,
                preapproved=True,
            )
            self.assertTrue(approved.allowed)

    def test_handoff_validation(self) -> None:
        validator = HandoffValidator()
        packet = validator.validate(valid_handoff())
        self.assertEqual(packet.schema_version, 1)
        bad = valid_handoff()
        bad.pop("next_actions")
        with self.assertRaises(ValueError):
            validator.validate(bad)

    def test_publish_guard_immutable_and_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.md"
            cand = Path(tmp) / "cand.md"
            base.write_text(
                "# Doc\n<!-- IMMUTABLE:START prime -->A<!-- IMMUTABLE:END prime -->\n",
                encoding="utf-8",
            )
            cand.write_text(
                "# Doc\n<!-- IMMUTABLE:START prime -->B<!-- IMMUTABLE:END prime -->\n",
                encoding="utf-8",
            )
            guard = PublishGuard()
            report = guard.evaluate(base, cand)
            self.assertFalse(report["allowed_to_publish"])
            self.assertTrue(report["immutable_violations"])

    def test_project_ark_snapshot_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "a.txt").write_text("hello\n", encoding="utf-8")
            ark = ProjectArkManager(root / "snapshots")
            info = ark.create_snapshot(include_paths=[src], retention_days=7)
            self.assertTrue(Path(info.snapshot_path).exists())
            self.assertTrue(info.restore_test_passed)
            restored = ark.phoenix_redeploy(
                snapshot_path=Path(info.snapshot_path),
                destination=root / "restore",
            )
            self.assertEqual(restored["event"], "recovery_event")

    def test_orchestrator_cycle_and_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dom = DominionOrchestrator(Path(tmp))
            result = dom.run_cycle("Improve backup reliability and passive income process")
            self.assertIn("checkpoint", result)
            self.assertIn("event", result)
            query = dom.memory.query("backup reliability", limit=3)
            self.assertTrue(query)

    def test_autotune_and_catalyst(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dom = DominionOrchestrator(Path(tmp))
            tune = dom.tuner.evaluate(cpu_pct=35.0, memory_pct=45.0, queue_depth=20)
            self.assertEqual(tune.action, "increase_concurrency")
            item = dom.catalyst.propose(
                title="Increase worker concurrency",
                hypothesis="More parallelism improves throughput",
                metric="throughput",
                baseline=100.0,
                candidate=120.0,
            )
            self.assertEqual(item["status"], "proposed")
            merged = dom.catalyst.merge_if_improved(item["item_id"])
            self.assertTrue(merged["improved"])
            self.assertEqual(merged["status"], "merged")

    def test_dual_verify_failover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dom = DominionOrchestrator(Path(tmp))
            result = dom.verifier.verify(
                prompt="Check this text",
                draft="This is a complete sentence.",
                secondary_available=False,
            )
            self.assertTrue(result.failover_used)
            self.assertIn(result.status, {"approved", "needs_revision"})


if __name__ == "__main__":
    unittest.main()
