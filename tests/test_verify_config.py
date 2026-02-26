import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VerifyConfigSmokeTest(unittest.TestCase):
    def test_verify_config_script(self) -> None:
        proc = subprocess.run(
            [sys.executable, "scripts/verify_config.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + "\n" + proc.stderr)


if __name__ == "__main__":
    unittest.main()
