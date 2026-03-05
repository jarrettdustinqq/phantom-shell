import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReinstallAssetsTests(unittest.TestCase):
    def test_reinstall_script_exists_and_is_executable(self) -> None:
        script = ROOT / "scripts" / "reinstall_lennox_kodex_terminal.sh"
        self.assertTrue(script.exists())
        self.assertTrue(os.access(script, os.X_OK))

    def test_reinstall_script_has_stable_help_output(self) -> None:
        proc = subprocess.run(
            ["bash", "-n", "scripts/reinstall_lennox_kodex_terminal.sh"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + "\n" + proc.stderr)


if __name__ == "__main__":
    unittest.main()
