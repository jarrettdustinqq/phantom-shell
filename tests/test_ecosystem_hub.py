import tempfile
import unittest
from pathlib import Path

from phantom_shell.ecosystem_hub import EcosystemHub
from phantom_shell.universal_agent import UniversalAgent


class EcosystemHubTests(unittest.TestCase):
    def test_register_and_route_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ua = UniversalAgent(
                state_path=base / "ua-state.json",
                audit_log_path=base / "ua-audit.jsonl",
            )
            ua.register_connector(
                connector_id="echo_health",
                name="Echo Health",
                connector_type="shell",
                capabilities=["readonly"],
                config={"command": "echo ok", "health_command": "echo ok"},
                enabled=True,
            )
            hub = EcosystemHub(universal_agent=ua, state_path=base / "hub-state.json")
            hub.register_agent(
                agent_id="ops_agent",
                name="Ops Agent",
                role="operations",
                allowed_connectors=["echo_health"],
                objective="check health",
            )
            routed = hub.route_task("ops_agent", "echo_health", {})
            self.assertEqual(routed["result"]["result"]["status"], "ok")

    def test_connector_permission_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ua = UniversalAgent(
                state_path=base / "ua-state.json",
                audit_log_path=base / "ua-audit.jsonl",
            )
            ua.register_connector(
                connector_id="tool_a",
                name="Tool A",
                connector_type="shell",
                capabilities=[],
                config={"command": "echo A"},
                enabled=True,
            )
            ua.register_connector(
                connector_id="tool_b",
                name="Tool B",
                connector_type="shell",
                capabilities=[],
                config={"command": "echo B"},
                enabled=True,
            )
            hub = EcosystemHub(universal_agent=ua, state_path=base / "hub-state.json")
            hub.register_agent(
                agent_id="restricted",
                name="Restricted",
                role="ops",
                allowed_connectors=["tool_a"],
                objective="run tool a only",
            )
            with self.assertRaises(PermissionError):
                hub.route_task("restricted", "tool_b", {})


if __name__ == "__main__":
    unittest.main()
