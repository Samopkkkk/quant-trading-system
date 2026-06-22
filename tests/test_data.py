import pandas as pd
import pytest

from agent.data import _normalize_ohlcv, synthetic_ohlcv


def test_normalize_ohlcv_handles_prefixed_columns():
    # e.g. the plotly AAPL dataset uses 'AAPL.Open' etc., dates out of order.
    df = pd.DataFrame({
        "Date": ["2020-01-02", "2020-01-03", "2020-01-01"],
        "AAPL.Open": [1.0, 2.0, 3.0],
        "AAPL.High": [2.0, 3.0, 4.0],
        "AAPL.Low": [0.5, 1.0, 1.5],
        "AAPL.Close": [1.5, 2.5, 3.5],
        "AAPL.Volume": [100, 200, 300],
        "AAPL.Adjusted": [1.5, 2.5, 3.5],
    })
    out = _normalize_ohlcv(df)
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert out.index.name == "date"
    assert out.index.is_monotonic_increasing            # sorted ascending
    assert out["close"].iloc[0] == 3.5                  # 2020-01-01 row sorts first


def test_normalize_ohlcv_plain_columns_and_default_volume():
    df = pd.DataFrame({"date": ["2020-01-01"], "Open": [1.0], "High": [2.0],
                       "Low": [0.5], "Close": [1.5]})            # no volume
    out = _normalize_ohlcv(df)
    assert out["volume"].iloc[0] == 0.0


def test_normalize_ohlcv_missing_ohlc_raises():
    with pytest.raises(ValueError):
        _normalize_ohlcv(pd.DataFrame({"date": ["2020-01-01"], "foo": [1]}))


def test_synthetic_is_well_formed():
    df = synthetic_ohlcv(days=30, seed=1)
    assert len(df) == 30
    assert (df["high"] >= df["low"]).all()
    assert (df["high"] >= df["close"]).all() and (df["close"] >= df["low"]).all()
