# Returns and Risk — read this before risking real money

## The headline question: "a minimum 100% return in one month"

A **guaranteed minimum** 100% return in one month is not achievable, by anyone,
with any strategy. This is not a limitation of this codebase — it is a property
of markets.

- +100% per month compounds to roughly **+409,000% per year** (`2^12 − 1`).
- The best long-term track records in history (Renaissance Medallion, etc.) are
  in the tens of percent **per year**, not per month.
- A real "minimum return" — a floor below which you cannot fall — only exists for
  instruments with a contractual guarantee (T-bills, insured deposits), and those
  pay low single digits *per year*. The moment you take market risk to chase
  higher returns, the floor is gone. Your real floor is **−100%** (total loss),
  and with margin it is worse than −100%.

The only ways to make a *backtest* display "≥100% per month" are forms of
cheating that evaporate on live money:

| Trick | Why it lies |
|---|---|
| Look-ahead bias | Using data the strategy wouldn't have had yet |
| Overfitting | Tuning parameters to one lucky historical window |
| Ignoring costs | Omitting commission, slippage, borrow, market impact |
| Survivorship / cherry-picking | Testing only on the asset/period that happened to win |
| Unmodeled leverage/liquidity | Assuming fills and size you couldn't actually get |

This project **refuses to build those in.** The backtester (`agent/backtest.py`)
shows the strategy only closed bars, fills at the next bar's open with slippage
and commission, and reports whatever honest number results — including losses.

## What "I want huge returns" actually costs: the math

`python -m agent.montecarlo` simulates one-month outcomes. Assuming a *generous*
30%/yr edge and 40%/yr volatility, varying only leverage:

```
leverage  median    P(double)  P(lose half)  P(ruin)
   1x      +1.9%        0.0%        0.0%         0.0%
   3x      +1.8%        2.5%        2.2%         0.0%
   5x      -3.5%       10.2%       13.4%         0.0%
  10x     -35.5%       17.8%       41.9%         3.0%
  20x     -98.2%       11.0%       78.0%        57.7%
```

Read the table carefully:

- The **only** lever that raises the chance of doubling is leverage.
- Every notch of leverage that raises `P(double)` raises `P(lose half)` and
  `P(ruin)` *faster*. The best chance of doubling here is ~18% (at 10x) — and at
  that setting the **median** result is −35% and you lose half your money 42% of
  the time.
- Past 10x the median collapses toward total loss: more leverage now *lowers*
  your expected outcome because compounding punishes volatility (volatility drag).

So "minimum 100% in a month" decomposes into two requests: a *minimum* (a floor),
which markets cannot give above the risk-free rate, and *+100%*, which is only
reachable as a low-probability tail while accepting a high probability of ruin.

## What this system does instead

It is built to **survive and compound**, with aggressiveness as an explicit,
auditable dial — not a hidden promise:

- **Position sizing** (`agent/risk.py`): volatility targeting, per-trade stop
  risk, and a hard per-position cap.
- **Daily-loss halt**: stop opening new risk after a set daily loss.
- **Max-drawdown kill switch**: flatten everything and stop trading once drawdown
  from the peak hits a limit.
- **Leverage cap**: a hard ceiling on gross exposure.
- **Paper-first**: paper trading is the default; live trading requires explicit
  opt-in plus credentials.

If you want to pursue high returns, the honest path is: turn the risk dials up
**knowingly** (raise `max_position_fraction`, `max_gross_leverage`,
`max_drawdown_limit_fraction`), read the Monte-Carlo output for the ruin
probability that choice implies, validate on real out-of-sample data, and paper
trade it before risking a cent.

## Running with real data / live (environment note)

This repository was developed in a sandbox whose **network egress allowlist only
permits PyPI**. Yahoo Finance, Stooq, and all Webull hosts return
`403 Host not in allowlist`. Therefore, in that sandbox:

- ✅ Unit tests, synthetic backtests, and paper simulation run fully offline.
- ❌ Real-data backtests and live Webull trading cannot run there.

To use real data or trade live you must run where those hosts are reachable:

1. **Locally**, or in an environment without the egress restriction; or
2. Add the hosts to your environment's network egress settings
   (`query1.finance.yahoo.com` for data; `api.webull.com` or the UAT host
   `us-openapi-alb.uat.webullbroker.com` for trading). See
   https://code.claude.com/docs/en/claude-code-on-the-web for network policy.

Live trading also requires `pip install webull-python-sdk-core
webull-python-sdk-trade` and the env vars `WEBULL_APP_KEY`, `WEBULL_APP_SECRET`,
`WEBULL_ACCOUNT_ID` (apply at https://developer.webull.com/).

## Bottom line

No part of this system guarantees a profit. Anyone — software, fund, or person —
who guarantees you 100% in a month is describing a fraud or a coin flip with your
livelihood. Trade only money you can afford to lose.
