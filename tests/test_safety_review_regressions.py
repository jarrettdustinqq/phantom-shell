"""Independent regressions for the safety contracts reviewed after PR #33."""

from dataclasses import asdict
import ipaddress
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from phantom_shell.http_policy import URLPolicyError, validate_outbound_url
from phantom_shell.loop_agent_engine import LoopAgentEngine
from scripts.loop_agent_console import prompt_measured_score


class MeasurementInputTests(unittest.TestCase):
    def test_nonfinite_measurements_leave_saved_and_memory_state_unchanged(self):
        for score in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(score=score), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "state.json"
                engine = LoopAgentEngine(path)
                engine.set_baseline(60, "Measured baseline")
                before_state = asdict(engine.state)
                before_bytes = path.read_bytes()
                with self.assertRaises(ValueError):
                    engine.run_cycle(measured_score=score)
                self.assertEqual(asdict(engine.state), before_state)
                self.assertEqual(path.read_bytes(), before_bytes)

    def test_rejected_first_measurement_does_not_create_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            engine = LoopAgentEngine(path)
            before = asdict(engine.state)
            with self.assertRaises(ValueError):
                engine.run_cycle(measured_score=float("nan"))
            self.assertEqual(asdict(engine.state), before)
            self.assertFalse(path.exists())

    def test_nonfinite_baselines_leave_state_unchanged(self):
        for score in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(score=score), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "state.json"
                engine = LoopAgentEngine(path)
                engine.set_baseline(60, "Measured baseline")
                before_state = asdict(engine.state)
                before_bytes = path.read_bytes()
                with self.assertRaises(ValueError):
                    engine.set_baseline(score, "Invalid baseline")
                self.assertEqual(asdict(engine.state), before_state)
                self.assertEqual(path.read_bytes(), before_bytes)

    def test_console_rejects_nonfinite_scores(self):
        for raw in ("nan", "NaN", "+inf", "-inf", "Infinity"):
            with self.subTest(raw=raw), patch("builtins.input", return_value=raw):
                with self.assertRaises(ValueError):
                    prompt_measured_score()

    def test_finite_score_and_blank_input_behavior_is_preserved(self):
        for raw, expected in (("", None), ("0", 0.0), ("60.5", 60.5), ("100", 100.0)):
            with self.subTest(raw=raw), patch("builtins.input", return_value=raw):
                self.assertEqual(prompt_measured_score(), expected)
        for score, expected in ((-1, 0), (0, 0), (60.125, 60.12), (100, 100), (101, 100)):
            with self.subTest(score=score), tempfile.TemporaryDirectory() as tmp:
                engine = LoopAgentEngine(Path(tmp) / "state.json")
                engine.set_baseline(score)
                self.assertEqual(engine.state.current_score, expected)
                cycle = engine.run_cycle(measured_score=score)
                self.assertEqual(cycle.result_delta["actual_delta"], 0)
                self.assertEqual(cycle.result_delta["mode"], "measured")

    def test_legacy_projection_history_is_preserved_when_appending_a_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            engine = LoopAgentEngine(path)
            engine.set_baseline(60, "Historical strategy")
            engine.run_cycle()
            legacy = json.loads(path.read_text())
            legacy["current_score"] = 65
            legacy["playbook"].append("Historical unsupported promotion")
            legacy["cycles"][0]["result_delta"].update(actual_delta=5, new_score=65)
            legacy["cycles"][0]["result_delta"].pop("projected_score")
            legacy["cycles"][0]["self_update"] = "Historical unsupported promotion"
            path.write_text(json.dumps(legacy))
            reloaded = LoopAgentEngine(path)
            cycle = reloaded.run_cycle()
            saved = json.loads(path.read_text())
            self.assertEqual(saved["cycles"][0], legacy["cycles"][0])
            for key in ("current_score", "baseline_score", "strategy", "playbook"):
                self.assertEqual(saved[key], legacy[key])
            self.assertIsNone(cycle.result_delta["actual_delta"])
            self.assertEqual(cycle.next_decision, "collect_measurement")


class MappedAddressPolicyTests(unittest.TestCase):
    multicast = ("::ffff:224.0.0.1", "::ffff:239.255.255.255", "::ffff:e000:1")

    def test_ipv4_mapped_multicast_literals_are_blocked(self):
        for address in self.multicast:
            with self.subTest(address=address), self.assertRaises(URLPolicyError):
                validate_outbound_url(f"https://[{address}]/")

    def test_any_mapped_multicast_dns_answer_blocks_destination(self):
        for address in self.multicast:
            for answers in ((address, "93.184.216.34"), ("93.184.216.34", address)):
                def resolver(hostname, port, *, type):
                    return [(socket.AF_INET6 if ":" in value else socket.AF_INET,
                             type, 6, "", (value, 0)) for value in answers]
                with self.subTest(answers=answers), self.assertRaises(URLPolicyError):
                    validate_outbound_url("https://mixed.example.test", resolver=resolver)

    def test_mapped_public_unicast_and_explicit_override_are_preserved(self):
        url = "https://[::ffff:93.184.216.34]/"
        self.assertEqual(validate_outbound_url(url), url)
        multicast_url = "https://[::ffff:224.0.0.1]/"
        self.assertEqual(validate_outbound_url(multicast_url, allow_private=True), multicast_url)

    def test_mapped_multicast_is_blocked_with_older_python_classification(self):
        # Python 3.12.3 only checks the IPv6 ff00::/8 prefix here. Exercise that
        # supported behavior even when CI's newer stdlib delegates to IPv4.
        legacy_classification = property(lambda address: address.packed[0] == 0xFF)
        with patch.object(ipaddress.IPv6Address, "is_multicast", legacy_classification):
            self.assertFalse(ipaddress.ip_address(self.multicast[0]).is_multicast)
            for address in self.multicast:
                with self.subTest(address=address), self.assertRaises(URLPolicyError):
                    validate_outbound_url(f"https://[{address}]/")

    def test_dns_failure_and_empty_answers_fail_closed(self):
        def failed_resolver(*args, **kwargs):
            raise socket.gaierror("fixture lookup failure")
        for resolver in (failed_resolver, lambda *args, **kwargs: []):
            with self.subTest(resolver=resolver), self.assertRaises(URLPolicyError):
                validate_outbound_url("https://unresolved.example.test", resolver=resolver)


if __name__ == "__main__":
    unittest.main()
