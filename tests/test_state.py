from datetime import datetime

from agent.config import RiskConfig
from agent.risk import RiskManager
from agent.state import StateStore


def test_risk_state_roundtrip(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    rm = RiskManager(RiskConfig(), store=store)
    rm.initialize(100_000.0, now=datetime(2026, 1, 5))
    rm.update_equity(120_000.0, now=datetime(2026, 1, 5))   # peak now 120k

    reloaded = StateStore(str(tmp_path / "state.json")).load_risk_state()
    assert reloaded is not None
    assert reloaded.peak_equity == 120_000.0


def test_kill_switch_survives_restart(tmp_path):
    """The core safety property: a restart must not forget the prior peak."""
    path = str(tmp_path / "state.json")
    cfg = RiskConfig(max_drawdown_limit_fraction=0.15)

    rm1 = RiskManager(cfg, store=StateStore(path))
    rm1.initialize(100_000.0, now=datetime(2026, 1, 5))
    rm1.update_equity(150_000.0, now=datetime(2026, 1, 5))   # peak watermark = 150k
    assert not rm1.state.kill_switch_active

    # Process restarts. Equity is now 120k. Without persistence, initialize() would
    # reset the peak to 120k and the kill switch would never fire. With persistence,
    # the peak is restored as 150k => 120k is a 20% drawdown => kill switch trips.
    rm2 = RiskManager(cfg, store=StateStore(path))
    rm2.initialize(120_000.0, now=datetime(2026, 1, 6))
    assert rm2.state.peak_equity == 150_000.0
    rm2.update_equity(120_000.0, now=datetime(2026, 1, 6))
    assert rm2.state.kill_switch_active


def test_kill_switch_flag_persists(tmp_path):
    path = str(tmp_path / "state.json")
    cfg = RiskConfig(max_drawdown_limit_fraction=0.10)
    rm = RiskManager(cfg, store=StateStore(path))
    rm.initialize(100_000.0, now=datetime(2026, 1, 5))
    rm.update_equity(85_000.0, now=datetime(2026, 1, 5))     # -15% -> trips
    assert rm.state.kill_switch_active
    # A fresh manager reloads the tripped switch (stays halted until manual reset).
    rm2 = RiskManager(cfg, store=StateStore(path))
    rm2.initialize(85_000.0, now=datetime(2026, 1, 6))
    assert rm2.state.kill_switch_active
    assert not rm2.can_open_new_risk()


def test_no_store_starts_fresh():
    rm = RiskManager(RiskConfig())
    rm.initialize(100_000.0, now=datetime(2026, 1, 5))
    assert rm.state.peak_equity == 100_000.0      # nothing to restore


def test_missing_file_returns_none(tmp_path):
    assert StateStore(str(tmp_path / "nope.json")).load_risk_state() is None
