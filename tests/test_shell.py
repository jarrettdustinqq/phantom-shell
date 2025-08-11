import os
import sys
import pytest
from subprocess import TimeoutExpired

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from phantom_shell.shell import run_command


def test_run_command_echo():
    result = run_command(["echo", "hello"])
    assert result.returncode == 0
    assert result.stdout.strip() == "hello"
    assert result.stderr == ""


def test_run_command_failure():
    result = run_command(["bash", "-c", "exit 1"])
    assert result.returncode == 1


def test_run_command_timeout():
    with pytest.raises(TimeoutExpired):
        run_command(["sleep", "5"], timeout=0.1)
