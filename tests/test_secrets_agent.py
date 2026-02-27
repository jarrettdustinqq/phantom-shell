import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "secrets_agent.py"
SPEC = spec_from_file_location("secrets_agent", MODULE_PATH)
sa = module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = sa
SPEC.loader.exec_module(sa)


def test_compute_plan_id_stable_order():
    a = sa.compute_plan_id("mock", ["b", "a"])
    b = sa.compute_plan_id("mock", ["a", "b", "a"])
    assert a == b


def test_confirm_token_deterministic():
    token1 = sa.build_confirm_token("abc123", "salt")
    token2 = sa.build_confirm_token("abc123", "salt")
    assert token1 == token2
    assert len(token1) == 12


def test_key_audit_detects_missing_owner_and_stale(monkeypatch, capsys):
    class Args:
        backend = "mock"
        stale_days = 90

    fixed_now = sa.dt.datetime(2026, 2, 26, tzinfo=sa.dt.timezone.utc)
    monkeypatch.setattr(sa, "utc_now", lambda: fixed_now)

    code = sa.cmd_key_audit(Args())
    out = capsys.readouterr().out

    assert code == 0
    assert "svc-db-002" in out
    assert "missing_owner_tag_item_ids" in out
