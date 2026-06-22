"""Market data loading.

Three sources, in order of realism:
  1. fetch_yahoo  - real daily/intraday OHLCV from Yahoo Finance (no API key).
  2. load_csv     - your own cached history.
  3. synthetic_ohlcv - geometric-Brownian-motion candles for offline tests.

The synthetic generator is for TESTS and demos only. Never evaluate a strategy
on synthetic data and claim it as a real backtest result.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

_OHLCV = ["open", "high", "low", "close", "volume"]


def _empty() -> pd.DataFrame:
    df = pd.DataFrame(columns=_OHLCV)
    df.index = pd.DatetimeIndex([], name="date")
    return df


def synthetic_ohlcv(
    days: int = 252,
    start_price: float = 100.0,
    annual_vol: float = 0.25,
    annual_drift: float = 0.08,
    seed: int | None = 42,
    start: datetime | None = None,
) -> pd.DataFrame:
    """Generate deterministic GBM OHLCV bars for testing.

    Deterministic when `seed` is set, so unit tests are stable.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0 / 252.0
    mu, sigma = annual_drift, annual_vol
    shocks = rng.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), size=days)
    close = start_price * np.exp(np.cumsum(shocks))
    prev_close = np.concatenate([[start_price], close[:-1]])
    open_ = prev_close
    # Intrabar range proportional to daily vol.
    rang = np.abs(close - open_) + start_price * sigma * np.sqrt(dt) * 0.5
    high = np.maximum(open_, close) + rang * rng.uniform(0, 0.5, size=days)
    low = np.minimum(open_, close) - rang * rng.uniform(0, 0.5, size=days)
    volume = rng.integers(1_000_000, 10_000_000, size=days).astype(float)

    start = start or (datetime.utcnow() - timedelta(days=days))
    idx = pd.bdate_range(start=start, periods=days, name="date")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def load_csv(path: str) -> pd.DataFrame:
    """Load OHLCV from a CSV with a 'date' column and open/high/low/close[/volume]."""
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    df.columns = [c.lower() for c in df.columns]
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[_OHLCV].sort_index()


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Map an arbitrary CSV to OHLCV. Tolerates prefixed names like 'AAPL.Open'."""
    date_col = next((c for c in df.columns
                     if c.lower() in ("date", "datetime", "time", "timestamp")),
                    df.columns[0])
    out: dict[str, pd.Series] = {}
    for field in _OHLCV:
        match = next((c for c in df.columns if c.lower() == field
                      or c.lower().endswith(("." + field, "_" + field, " " + field))), None)
        if match is not None:
            out[field] = pd.to_numeric(df[match], errors="coerce")
    if not {"open", "high", "low", "close"}.issubset(out):
        raise ValueError(f"CSV missing OHLC columns; saw {list(df.columns)[:10]}")
    out.setdefault("volume", pd.Series(0.0, index=df.index))
    res = pd.DataFrame(out)
    res.index = pd.to_datetime(df[date_col])
    res.index.name = "date"
    return res.dropna(subset=["close"]).sort_index()


def fetch_csv_url(url: str, timeout: float = 20.0) -> pd.DataFrame:
    """Fetch and normalize an OHLCV CSV from a URL.

    Useful in restricted environments where dedicated market-data APIs are not on
    the egress allowlist but a CSV host (e.g. raw.githubusercontent.com) is.
    """
    import requests

    resp = requests.get(url, headers={"User-Agent": "quant-agent/1.0"}, timeout=timeout)
    resp.raise_for_status()
    import io
    return _normalize_ohlcv(pd.read_csv(io.StringIO(resp.text)))


def fetch_yahoo(
    symbol: str,
    range_: str = "1y",
    interval: str = "1d",
    timeout: float = 15.0,
) -> pd.DataFrame:
    """Fetch real OHLCV from Yahoo Finance. Returns empty DataFrame on failure.

    Yahoo rejects the default urllib User-Agent, so a browser-like UA is sent.
    """
    import requests

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": range_, "interval": interval, "includePrePost": "false"}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; quant-agent/1.0)"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        result = payload["chart"]["result"][0]
        ts = result["timestamp"]
        q = result["indicators"]["quote"][0]
        df = pd.DataFrame(
            {
                "open": q["open"],
                "high": q["high"],
                "low": q["low"],
                "close": q["close"],
                "volume": q["volume"],
            },
            index=pd.to_datetime(ts, unit="s"),
        )
        df.index.name = "date"
        return df.dropna(subset=["close"]).sort_index()
    except Exception as exc:  # network error, rate limit, bad symbol, schema drift
        import logging

        logging.getLogger(__name__).warning("Yahoo fetch failed for %s: %s", symbol, exc)
        return _empty()


def get_history(symbol: str, range_: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Best-effort real history. Raises if no data could be obtained."""
    df = fetch_yahoo(symbol, range_=range_, interval=interval)
    if df.empty:
        raise RuntimeError(
            f"Could not fetch history for {symbol}. Check connectivity or supply a CSV."
        )
    return df
