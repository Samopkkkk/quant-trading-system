import numpy as np
import pandas as pd

from agent.indicators import (
    average_dollar_volume, chaikin_money_flow, money_flow_index, obv_series,
)
from agent.screener import screen_universe, select_symbols
from agent.strategies import Momentum, MoneyFlowConfirmed, MoneyFlowStrategy


def _bars(closes, highs=None, lows=None, vols=None):
    n = len(closes)
    idx = pd.bdate_range("2025-01-01", periods=n, name="date")
    closes = pd.Series(closes, index=idx, dtype=float)
    highs = pd.Series(highs if highs is not None else closes * 1.01, index=idx, dtype=float)
    lows = pd.Series(lows if lows is not None else closes * 0.99, index=idx, dtype=float)
    vols = pd.Series(vols if vols is not None else [1e6] * n, index=idx, dtype=float)
    return pd.DataFrame({"open": closes, "high": highs, "low": lows,
                         "close": closes, "volume": vols}, index=idx)


# ----- indicators -----
def test_cmf_extremes():
    # close == high every bar -> all buying pressure -> CMF = +1
    df = _bars([100] * 25, highs=[100] * 25, lows=[90] * 25)
    assert abs(chaikin_money_flow(df, 20) - 1.0) < 1e-9
    # close == low every bar -> all selling pressure -> CMF = -1
    df2 = _bars([100] * 25, highs=[110] * 25, lows=[100] * 25)
    assert abs(chaikin_money_flow(df2, 20) + 1.0) < 1e-9


def test_mfi_bounds():
    rising = _bars(list(np.linspace(100, 130, 30)))
    assert money_flow_index(rising, 14) == 100.0          # only positive money flow
    falling = _bars(list(np.linspace(130, 100, 30)))
    assert money_flow_index(falling, 14) == 0.0           # only negative money flow


def test_obv_and_dollar_volume():
    df = _bars([100, 101, 100, 102], vols=[10, 20, 30, 40])
    obv = obv_series(df)
    assert obv.iloc[-1] == 20 - 30 + 40                   # +up, -down, +up (first=0)
    assert average_dollar_volume(df, window=4) > 0


# ----- money-flow strategy -----
def test_money_flow_long_requires_inflow():
    up = list(np.linspace(100, 200, 80))
    inflow = _bars(up, highs=[c * 1.001 for c in up], lows=[c * 0.97 for c in up])  # close near high
    sig = MoneyFlowStrategy(10, 30, cmf_period=20).evaluate("X", inflow)
    assert sig.target == 1.0                              # uptrend + inflow -> long


def test_money_flow_vetoes_uptrend_on_outflow():
    up = list(np.linspace(100, 200, 80))
    outflow = _bars(up, highs=[c * 1.03 for c in up], lows=[c * 0.999 for c in up])  # close near low
    sig = MoneyFlowStrategy(10, 30, cmf_period=20).evaluate("X", outflow)
    assert sig.target == 0.0                              # uptrend but money flowing OUT


def test_money_flow_confirmed_wrapper():
    up = list(np.linspace(100, 200, 120))
    inflow = _bars(up, highs=[c * 1.001 for c in up], lows=[c * 0.97 for c in up])
    outflow = _bars(up, highs=[c * 1.03 for c in up], lows=[c * 0.999 for c in up])
    base = Momentum(lookback=60)
    assert base.evaluate("X", inflow).target == 1.0       # base alone is long either way
    assert MoneyFlowConfirmed(base, min_cmf=0.05).evaluate("X", inflow).target == 1.0
    assert MoneyFlowConfirmed(base, min_cmf=0.05).evaluate("X", outflow).target == 0.0  # vetoed


# ----- screener -----
def test_screener_filters_and_ranks():
    strong = _bars(list(np.linspace(100, 180, 200)))      # strong uptrend, liquid
    weak = _bars(list(np.linspace(100, 95, 200)))         # downtrend, liquid
    illiquid = _bars(list(np.linspace(100, 200, 200)), vols=[1] * 200)  # no volume
    short = _bars(list(np.linspace(100, 200, 50)))        # too little history

    results = screen_universe({"STRONG": strong, "WEAK": weak,
                               "ILLIQUID": illiquid, "SHORT": short},
                              momentum_lookback=90, min_dollar_volume=1e6, min_history=120)
    syms = [r.symbol for r in results]
    assert "ILLIQUID" not in syms and "SHORT" not in syms  # filtered out
    assert syms[0] == "STRONG"                             # best score first
    assert select_symbols({"STRONG": strong, "WEAK": weak}, top_n=1) == ["STRONG"]
