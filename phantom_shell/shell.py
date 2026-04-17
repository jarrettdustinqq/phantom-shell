from dataclasses import dataclass
from subprocess import PIPE, TimeoutExpired, run
from typing import List, Optional


@dataclass
class CommandResult:
    """Result of executing a command."""
    returncode: int
    stdout: str
    stderr: str


def run_command(cmd: List[str], timeout: Optional[float] = None) -> CommandResult:
    """Run a command and capture its output."""
    completed = run(
        cmd,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
