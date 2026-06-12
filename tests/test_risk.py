from datetime import datetime

from agent.config import RiskConfig
from agent.risk import RiskManager, kelly_fraction
from agent.types import Signal


def _rm(**kw):
    rm = RiskManager(RiskConfig(**kw))
    rm.initialize(100_000.0, now=datetime(2026, 1, 5))
    return rm


def test_max_position_fraction_caps_size():
    rm = _rm(max_position_fraction=0.20, target_annual_vol=None)
    shares = rm.target_shares(100_000, 100.0, Signal("X", 1.0))
    assert shares == 200  # 0.20 * 100k / 100


def test_vol_targeting_scales_down():
    rm = _rm(max_position_fraction=0.20, target_annual_vol=0.20)
    # realized vol double the target -> half the size
    shares = rm.target_shares(100_000, 100.0, Signal("X", 1.0), recent_annual_vol=0.40)
    assert shares == 100


def test_vol_targeting_cannot_exceed_position_cap():
    rm = _rm(max_position_fraction=0.20, target_annual_vol=0.20)
    # very low realized vol would scale up, but the hard cap binds at 200
    shares = rm.target_shares(100_000, 100.0, Signal("X", 1.0), recent_annual_vol=0.02)
    assert shares == 200


def test_stop_risk_cap_binds():
    rm = _rm(max_position_fraction=0.50, risk_per_trade_fraction=0.01, target_annual_vol=None)
    # cap would allow 500 shares, but risking 1% ($1000) with a $5 stop caps at 200
    shares = rm.target_shares(100_000, 100.0, Signal("X", 1.0, stop_price=95.0))
    assert shares == 200


def test_short_signal_is_negative():
    rm = _rm(max_position_fraction=0.20, target_annual_vol=None)
    assert rm.target_shares(100_000, 100.0, Signal("X", -1.0)) == -200


def test_kill_switch_trips_on_drawdown():
    rm = _rm(max_drawdown_limit_fraction=0.15)
    rm.update_equity(84_000.0, now=datetime(2026, 1, 5))  # -16% from peak
    assert rm.state.kill_switch_active
    assert not rm.can_open_new_risk()


def test_daily_loss_halt_then_new_day_resets():
    rm = _rm(daily_loss_limit_fraction=0.03, max_drawdown_limit_fraction=0.50)
    rm.update_equity(96_000.0, now=datetime(2026, 1, 5))   # -4% on the day
    assert rm.state.new_entries_halted
    assert not rm.state.kill_switch_active                 # dd 4% < 50%
    rm.update_equity(96_000.0, now=datetime(2026, 1, 6))   # new day
    assert not rm.state.new_entries_halted


def test_kelly_fraction():
    assert abs(kelly_fraction(0.6, 1.0) - 0.2) < 1e-9
    assert kelly_fraction(0.4, 1.0) == 0.0                 # no edge -> no bet
