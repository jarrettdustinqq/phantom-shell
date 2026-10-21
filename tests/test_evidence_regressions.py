"""Behavioral regressions for projected metrics and independent evidence checks."""

import contextlib
import io
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import textwrap
import unittest

from phantom_shell.http_policy import URLPolicyError, validate_outbound_url
from phantom_shell.loop_agent_engine import LoopAgentEngine
from scripts.loop_agent_console import run_autopilot


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/nightly-tamper-guardrail.yml"


class ProjectionEvidenceTests(unittest.TestCase):
    def test_unmeasured_cycles_preserve_measured_state_and_playbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = LoopAgentEngine(Path(tmp) / "state.json")
            engine.set_objective("Improve execution throughput")
            engine.set_baseline(60, "Measured baseline strategy")
            playbook = list(engine.state.playbook)
            for _ in range(3):
                cycle = engine.run_cycle()
                self.assertEqual(cycle.result_delta["mode"], "projected")
                self.assertIsNone(cycle.result_delta["actual_delta"])
                self.assertEqual(cycle.result_delta["new_score"], 60)
                self.assertIsInstance(cycle.result_delta["projected_score"], float)
                self.assertEqual(cycle.next_decision, "collect_measurement")
                self.assertNotIn("Promote pattern", cycle.self_update)
            reloaded = LoopAgentEngine(Path(tmp) / "state.json")
            self.assertEqual(reloaded.state.current_score, 60)
            self.assertEqual(reloaded.state.strategy, "Measured baseline strategy")
            self.assertEqual(reloaded.state.playbook, playbook)

    def test_measurement_after_projection_uses_original_measured_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = LoopAgentEngine(Path(tmp) / "state.json")
            engine.set_baseline(60)
            engine.run_cycle()
            cycle = engine.run_cycle(measured_score=63)
            self.assertEqual(cycle.result_delta["actual_delta"], 3)
            self.assertEqual(engine.state.current_score, 63)
            self.assertIn("Promote pattern", cycle.self_update)
            self.assertIn(cycle.self_update, engine.state.playbook)

    def test_projected_report_distinguishes_proposal_and_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = LoopAgentEngine(root / "state.json")
            engine.run_cycle()
            report = engine.export_markdown_report(root / "report.md").read_text()
            self.assertIn("Measurement mode: projected", report)
            self.assertIn("Measured delta: unknown", report)
            self.assertIn("Projected score:", report)
            self.assertIn("Proposed change:", report)

    def test_autopilot_displays_projections_without_claiming_actual_gains(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = LoopAgentEngine(Path(tmp) / "state.json")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                run_autopilot(engine, ["2"])
            self.assertIn("projected_score=", out.getvalue())
            self.assertIn("recorded_score=50.0", out.getvalue())
            self.assertEqual(engine.state.current_score, 50)


class MulticastPolicyTests(unittest.TestCase):
    def test_multicast_literals_are_blocked(self):
        for url in ("https://224.0.0.1/", "https://[ff02::1]/"):
            with self.subTest(url=url), self.assertRaises(URLPolicyError):
                validate_outbound_url(url)

    def test_any_multicast_dns_answer_blocks_the_destination(self):
        for address in ("224.0.0.1", "ff02::1"):
            def resolver(hostname, port, *, type):
                return [(socket.AF_INET, type, 6, "", ("93.184.216.34", 0)),
                        (socket.AF_INET6 if ":" in address else socket.AF_INET,
                         type, 6, "", (address, 0))]
            with self.subTest(address=address), self.assertRaises(URLPolicyError):
                validate_outbound_url("https://mixed.example.test", resolver=resolver)


class TamperLogEvidenceTests(unittest.TestCase):
    timestamp = "2026-10-21T08:41:39.3047600Z"
    mismatch = "Integrity mismatch for sample.json: expected " + "a" * 64 + ", got " + "b" * 64

    def inspect_logs(self, log, *, available=True):
        # Execute the workflow's actual shell step with a local gh stub. No API calls.
        block = WORKFLOW.read_text().split(
            "      - name: Inspect export run logs for mismatch evidence\n", 1
        )[1].split("      - name: Evaluate tamper guardrail assertion\n", 1)[0]
        script = textwrap.dedent(block.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fixture.log").write_text(log)
            gh = root / "gh"
            gh.write_text("#!/bin/sh\ncat \"$TEST_LOG\"\nexit \"$TEST_GH_EXIT\"\n")
            gh.chmod(0o755)
            output = root / "outputs"
            env = {
                "PATH": str(root) + os.pathsep + os.defpath,
                "RUNNER_TEMP": str(root),
                "GITHUB_REPOSITORY": "example/repo",
                "EXPORT_RUN_ID": "123",
                "GITHUB_OUTPUT": str(output),
                "TEST_LOG": str(root / "fixture.log"),
                "TEST_GH_EXIT": "0" if available else "1",
            }
            subprocess.run(["bash", "-c", script], env=env, check=True,
                           capture_output=True, text=True, timeout=10)
            return dict(line.split("=", 1) for line in output.read_text().splitlines())

    def test_runtime_error_annotation_is_accepted(self):
        log = self.timestamp + " ##[error]" + self.mismatch + "\n"
        self.assertEqual(self.inspect_logs(log)["mismatch_found"], "true")

    def test_gh_job_and_step_prefix_are_supported(self):
        log = "export-evidence\tVerify uploaded artifact integrity\t" + self.timestamp + " ##[error]" + self.mismatch + "\n"
        self.assertEqual(self.inspect_logs(log)["mismatch_found"], "true")

    def test_echoed_source_is_not_runtime_evidence(self):
        log = self.timestamp + ' \x1b[36;1m echo "::error::Integrity mismatch for ${json_path}"\x1b[0m\n'
        self.assertEqual(self.inspect_logs(log)["mismatch_found"], "false")

    def test_unrelated_failure_plus_echoed_source_is_rejected(self):
        log = self.timestamp + ' echo "::error::' + self.mismatch + '"\n'
        log += self.timestamp + " ##[error]Invalid checksum format\n"
        self.assertEqual(self.inspect_logs(log)["mismatch_found"], "false")

    def test_missing_logs_fail_closed(self):
        log = self.timestamp + " ##[error]" + self.mismatch + "\n"
        self.assertEqual(self.inspect_logs(log, available=False)["mismatch_found"], "false")

    def test_normal_output_mentioning_mismatch_is_rejected(self):
        log = self.timestamp + " diagnostic text: " + self.mismatch + "\n"
        self.assertEqual(self.inspect_logs(log)["mismatch_found"], "false")


if __name__ == "__main__":
    unittest.main()
