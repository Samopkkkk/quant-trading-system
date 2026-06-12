"""Monte-Carlo risk simulator.

This module exists to answer the question behind "I want 100% in a month"
*honestly* and quantitatively, instead of pretending a backtest can promise it.

Given an assumed edge (annual drift) and volatility, and a leverage multiplier,
it simulates many one-month paths and reports the full distribution of outcomes:
how often you'd double, how often you'd lose half, and how often you'd be ruined.

The universal result: pushing the probability of doubling in a month up to
something meaningful drags the probability of catastrophic loss up with it.
There is no leverage setting that gives a high chance of +100% and a low chance
of ruin. That tradeoff is mathematics, not pessimism.

Outcomes are illustrative (daily-normal returns, end-of-month equity floored at
zero); real markets have fat tails and gaps that make the downside *worse*.
"""
from __future__ import annotations

import numpy as np

TRADING_DAYS_PER_MONTH = 21
TRADING_DAYS_PER_YEAR = 252


def simulate_monthly_returns(
    annual_drift: float = 0.10,
    annual_vol: float = 0.20,
    leverage: float = 1.0,
    days: int = TRADING_DAYS_PER_MONTH,
    n_paths: int = 50_000,
    seed: int | None = 0,
) -> np.ndarray:
    """Return an array of simulated one-month total returns (e.g. 0.5 == +50%)."""
    rng = np.random.default_rng(seed)
    dt = 1.0 / TRADING_DAYS_PER_YEAR
    mu, sigma = annual_drift * dt, annual_vol * np.sqrt(dt)
    daily = rng.normal(mu, sigma, size=(n_paths, days)) * leverage
    equity = np.cumprod(1.0 + daily, axis=1)[:, -1]
    return np.maximum(equity, 0.0) - 1.0          # floor a wipeout at -100%


def summarize(returns: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(returns.mean()),
        "median": float(np.median(returns)),
        "p5": float(np.percentile(returns, 5)),
        "p95": float(np.percentile(returns, 95)),
        "p_double": float((returns >= 1.0).mean()),       # >= +100%
        "p_lose_half": float((returns <= -0.5).mean()),   # <= -50%
        "p_ruin": float((returns <= -0.95).mean()),       # near-total loss
    }


def report(annual_drift: float, annual_vol: float, leverage: float,
           seed: int | None = 0) -> str:
    s = summarize(simulate_monthly_returns(annual_drift, annual_vol, leverage, seed=seed))
    return (
        f"drift={annual_drift:.0%}/yr vol={annual_vol:.0%}/yr leverage={leverage:.0f}x | "
        f"median={s['median']:+.1%} p5={s['p5']:+.1%} p95={s['p95']:+.1%} | "
        f"P(double)={s['p_double']:.1%} P(lose half)={s['p_lose_half']:.1%} "
        f"P(ruin)={s['p_ruin']:.1%}"
    )


if __name__ == "__main__":
    print("One-month outcome distributions (assume a generous 30%/yr edge):\n")
    for lev in (1, 3, 5, 10, 20):
        print("  " + report(annual_drift=0.30, annual_vol=0.40, leverage=lev))
    print(
        "\nNote how the only way to lift P(double) is to crank leverage, which "
        "simultaneously lifts P(lose half) and P(ruin). That is the real cost of "
        "chasing +100% in a month."
    )
