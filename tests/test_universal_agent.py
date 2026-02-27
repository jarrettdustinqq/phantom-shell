import tempfile
import unittest
from pathlib import Path

from phantom_shell.universal_agent import UniversalAgent


class UniversalAgentTests(unittest.TestCase):
    def test_register_run_toggle_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            agent = UniversalAgent(
                state_path=base / "state.json",
                audit_log_path=base / "audit.jsonl",
            )
            agent.register_connector(
                connector_id="echo_tool",
                name="Echo Tool",
                connector_type="shell",
                capabilities=["test"],
                config={"command": "echo hello"},
            )
            self.assertEqual(agent.status()["connector_count"], 1)

            run = agent.run_connector("echo_tool", payload={})
            self.assertEqual(run["result"]["status"], "ok")
            self.assertIn("hello", run["result"]["stdout_preview"])

            agent.toggle_connector("echo_tool", enabled=False)
            with self.assertRaises(ValueError):
                agent.run_connector("echo_tool", payload={})

    def test_openai_connector_health_without_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            agent = UniversalAgent(
                state_path=base / "state.json",
                audit_log_path=base / "audit.jsonl",
            )
            agent.register_connector(
                connector_id="openai_main",
                name="OpenAI Main",
                connector_type="openai",
            )
            health = agent.health_check("openai_main")
            self.assertIn(health["health"], {"healthy", "unhealthy"})


if __name__ == "__main__":
    unittest.main()
