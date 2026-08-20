from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_workspace_system_check.sh"


def test_workspace_system_check_has_valid_shell_syntax():
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_workspace_system_check_fails_closed_on_missing_required_assets():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "Missing required phantom test files:" in text
    assert 'failures+=("continuity checkout")' in text
    assert "No phantom tests found; skipping." not in text
    assert "python3 -m pip install" not in text


def test_workspace_system_check_supports_explicit_directory_overrides():
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'FLEET_DIR:-' in text
    assert 'CONTINUITY_DIR:-' in text
    assert 'PHANTOM_DIR:-' in text
    assert 'REPORT_DIR:-' in text


def test_workspace_system_check_propagates_failures_through_tee(tmp_path):
    """Regression: logging through tee must not turn a failed check into success."""
    home = tmp_path / "home"
    fleet = tmp_path / "fleet"
    continuity = tmp_path / "continuity"
    phantom = tmp_path / "phantom"
    reports = tmp_path / "reports"
    for directory in (home, fleet, continuity, phantom, reports):
        directory.mkdir()

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(home),
            "FLEET_DIR": str(fleet),
            "CONTINUITY_DIR": str(continuity),
            "PHANTOM_DIR": str(phantom),
            "REPORT_DIR": str(reports),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    assert "summary=fail" in result.stdout
    report_paths = list(reports.glob("workspace-system-check-*.log"))
    assert len(report_paths) == 1
    report = report_paths[0].read_text(encoding="utf-8")
    assert "summary=fail" in report
    assert "failed_checks=" in report
