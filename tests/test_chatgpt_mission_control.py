import tempfile
import unittest
from pathlib import Path

from phantom_shell.chatgpt_mission_control import ChatGPTMissionControl


class ChatGPTMissionControlTests(unittest.TestCase):
    def test_create_packet_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "mission.json"
            mc = ChatGPTMissionControl(state_path=state)
            created = mc.create_task(
                title="Research incident pattern",
                objective="Find likely root causes and mitigations",
                mode="deep_research",
                assignee="chatgpt.com-research-agent",
                context="Focus on last 30 days signals.",
                acceptance_criteria=["Include sources", "Include confidence"],
            )
            task_id = created["task_id"]
            packet = mc.build_handoff_prompt(task_id)
            self.assertIn("Task ID:", packet)
            self.assertIn("Mode: deep_research", packet)
            updated = mc.update_task(task_id=task_id, status="in_progress")
            self.assertEqual(updated["status"], "in_progress")

    def test_status_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "mission.json"
            mc = ChatGPTMissionControl(state_path=state)
            mc.create_task(
                title="A",
                objective="B",
                mode="agent_mode",
                assignee="agent",
                context="",
                acceptance_criteria=["x"],
            )
            info = mc.status()
            self.assertEqual(info["task_count"], 1)
            self.assertGreaterEqual(info["status_counts"]["queued"], 1)


if __name__ == "__main__":
    unittest.main()
