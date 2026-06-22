# Real-data validation results

This records an honest out-of-sample test on **real** data, so the repo carries
the evidence — not just the hope.

## Data

- Source: S&P 500 daily OHLCV, 505 tickers, **2013-02-08 → 2018-02-07**
  (`raw.githubusercontent.com/plotly/datasets/master/all_stocks_5yr.csv`).
- Why this source: the environment's egress allowlist blocks dedicated
  market-data APIs (Yahoo/Stooq/AlphaVantage), but GitHub-hosted CSVs are
  reachable. Loaded via `agent.data.fetch_csv_url`.

## Method

- Symbol selection: `screen_universe` ranked all 505 names by momentum + Chaikin
  Money Flow, requiring net inflow (`min_cmf=0`). 222/505 passed liquidity+inflow
  filters. Top picks were sensible high-momentum, positive-flow names
  (STX, NFLX, AMZN, ALGN, NVDA, …).
- Strategy test: `money_flow` strategy, **walk-forward** out-of-sample
  (train=252, test=63), on each of the top-10 selected names, vs buy-and-hold.

## Result (the honest part)

| sym | buy&hold 5y | money_flow OOS | OOS Sharpe | beat B&H? |
|-----|------------:|---------------:|-----------:|:---------:|
| STX  | +39.7%  | +2.90% | 0.32 | no |
| NFLX | +923.3% | +4.80% | 0.47 | no |
| AMZN | +440.9% | +9.80% | 0.90 | no |
| KR   | +105.0% | +1.94% | 0.22 | no |
| WMT  | +43.9%  | +0.26% | 0.05 | no |
| ALGN | +615.9% | +5.57% | 0.54 | no |
| FLR  | −10.5%  | +5.68% | 0.78 | **yes** |
| FL   | +37.8%  | +3.63% | 0.45 | no |
| TRV  | +80.2%  | +1.37% | 0.23 | no |
| TGT  | +17.2%  | −1.25% | −0.16 | no |

**Median money_flow OOS ≈ +3.3% vs median buy-and-hold ≈ +62%. It beat
buy-and-hold in only 1 of 10 names — and that one (FLR) only by sidestepping a
decline, not by capturing gains.**

## Conclusion

- The machinery is real and works end-to-end on real data: fetch → screen →
  walk-forward → metrics.
- The **screener** selects sensible names.
- The **money_flow strategy as built has no demonstrable edge.** It is far too
  defensive — volatility targeting plus the money-flow gate keep it flat or small
  most of the time, so it captures almost none of the trend it correctly
  identifies. Low Sharpes confirm there is no free lunch here.
- Note how a single-name/single-window test would have misled: AAPL 2015-17 alone
  showed an OOS Sharpe of ~1.9 for the same strategy. The broader test shows that
  was luck, not edge. This is exactly why walk-forward across many names matters.

This is the opposite of the original "100%/month" goal, and it is the truth.
Beating buy-and-hold is hard; this configuration does not.

## If you want to pursue an actual edge (no guarantees)

- Make sizing less defensive (raise `target_annual_vol` / `max_position_fraction`)
  and re-test — but watch drawdown and the Monte-Carlo ruin numbers.
- Try staying in winners (trend-following that holds, not mean-reverting exits).
- Treat money flow as one input among several, validated the same honest way.
- Always judge against the buy-and-hold benchmark, out-of-sample, across names.
