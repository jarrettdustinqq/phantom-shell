import subprocess
import tempfile
import unittest
from pathlib import Path

from phantom_shell.release_marker_agent import ReleaseMarkerAgent


def run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "command failed")
    return proc.stdout.strip()


class ReleaseMarkerAgentTests(unittest.TestCase):
    def _init_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        run(["git", "init"], cwd=repo)
        run(["git", "config", "user.name", "Test User"], cwd=repo)
        run(["git", "config", "user.email", "test@example.com"], cwd=repo)
        (repo / "app.txt").write_text("v1\n", encoding="utf-8")
        run(["git", "add", "app.txt"], cwd=repo)
        run(["git", "commit", "-m", "Initial commit"], cwd=repo)
        return repo

    def test_capture_writes_note_and_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._init_repo(root)
            run(["git", "tag", "-a", "v1.0.0", "-m", "release"], cwd=repo)

            agent = ReleaseMarkerAgent(state_dir=root / "state")
            payload = agent.capture(repo_path=repo, ref="v1.0.0", marker_name="v1.0.0")

            note_path = Path(payload["marker"]["note_path"])
            self.assertTrue(note_path.exists())
            note_text = note_path.read_text(encoding="utf-8")
            self.assertIn("Release Marker: v1.0.0", note_text)
            self.assertIn("Initial commit", note_text)
            self.assertIn(payload["marker"]["commit"], note_text)

            status = agent.status()
            self.assertEqual(status["marker_count"], 1)
            self.assertEqual(status["latest"]["marker_name"], "v1.0.0")

    def test_capture_rejects_existing_note_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._init_repo(root)
            agent = ReleaseMarkerAgent(state_dir=root / "state")

            first = agent.capture(repo_path=repo, ref="HEAD", marker_name="head-marker")
            self.assertTrue(Path(first["marker"]["note_path"]).exists())

            with self.assertRaises(FileExistsError):
                agent.capture(repo_path=repo, ref="HEAD", marker_name="head-marker")

            second = agent.capture(
                repo_path=repo,
                ref="HEAD",
                marker_name="head-marker",
                allow_existing_note=True,
            )
            self.assertEqual(second["marker"]["marker_name"], "head-marker")


if __name__ == "__main__":
    unittest.main()
