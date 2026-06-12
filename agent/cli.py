"""Command-line interface for the trading agent.

    python -m agent.cli backtest --symbol AAPL --strategy ma_cross --range 2y
    python -m agent.cli paper    --symbols AAPL,MSFT --strategy momentum --cycles 5
    python -m agent.cli live     --symbols AAPL --strategy ma_cross --i-understand-the-risk

Live trading is gated behind an explicit flag AND the Webull env credentials.
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import data as market_data
from .backtest import Backtester
from .broker import PaperBroker, make_broker
from .config import AgentConfig, RiskConfig
from .engine import TradingAgent
from .strategies import STRATEGIES
from .validation import param_grid, walk_forward


def _build_strategy(name: str, args: argparse.Namespace):
    cls = STRATEGIES[name]
    if name == "ma_cross":
        return cls(fast=args.fast, slow=args.slow, allow_short=args.allow_short)
    if name == "momentum":
        return cls(lookback=args.lookback, allow_short=args.allow_short)
    if name == "rsi":
        return cls(allow_short=args.allow_short)
    return cls()


def _risk_from_args(args: argparse.Namespace) -> RiskConfig:
    return RiskConfig(
        max_position_fraction=args.max_position,
        risk_per_trade_fraction=args.risk_per_trade,
        max_gross_leverage=args.max_leverage,
        daily_loss_limit_fraction=args.daily_loss_limit,
        max_drawdown_limit_fraction=args.max_drawdown,
    )


def _load_prices(args: argparse.Namespace):
    if getattr(args, "csv", None):
        return market_data.load_csv(args.csv)
    if getattr(args, "synthetic", False):
        return market_data.synthetic_ohlcv(days=args.days, seed=args.seed)
    return market_data.get_history(args.symbol, range_=args.range, interval="1d")


def cmd_backtest(args: argparse.Namespace) -> int:
    prices = _load_prices(args)
    cfg = AgentConfig(symbols=[args.symbol], initial_capital=args.capital,
                      risk=_risk_from_args(args))
    bt = Backtester(cfg, _build_strategy(args.strategy, args))
    report = bt.run(args.symbol, prices)
    print(report.summary())
    print("\nReminder: this is one historical path, not a prediction or guarantee.")
    return 0


def _grid_for(name: str, args: argparse.Namespace) -> list[dict]:
    """Build a parameter grid for walk-forward from comma-separated CLI lists."""
    def ints(s):
        return [int(x) for x in s.split(",") if x.strip()]
    if name == "ma_cross":
        return [g for g in param_grid(fast=ints(args.fast_grid), slow=ints(args.slow_grid))
                if g["fast"] < g["slow"]]
    if name == "momentum":
        return param_grid(lookback=ints(args.lookback_grid))
    return [{}]  # rsi etc. use defaults


def cmd_walkforward(args: argparse.Namespace) -> int:
    prices = _load_prices(args)
    cfg = AgentConfig(symbols=[args.symbol], initial_capital=args.capital,
                      risk=_risk_from_args(args))
    grid = _grid_for(args.strategy, args)
    if not grid:
        print("Empty parameter grid (check fast<slow constraints).")
        return 2
    res = walk_forward(cfg, STRATEGIES[args.strategy], grid, args.symbol, prices,
                       train=args.train, test=args.test, select_metric=args.select)
    print(res.summary())
    print("\nThe out-of-sample numbers above are the honest estimate; the per-fold "
          "in-sample scores are not. Still not a guarantee.")
    return 0


def cmd_paper(args: argparse.Namespace) -> int:
    cfg = AgentConfig(symbols=args.symbols.split(","), initial_capital=args.capital,
                      live=False, poll_interval_seconds=args.interval,
                      risk=_risk_from_args(args))
    agent = TradingAgent(cfg, _build_strategy(args.strategy, args), PaperBroker(cfg))
    agent.run(max_cycles=args.cycles, sleep_fn=lambda s: None if args.no_sleep else __import__("time").sleep(s))
    print("Final account:", agent.broker.get_account().equity)
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    if not args.i_understand_the_risk:
        print("Refusing to trade live without --i-understand-the-risk.\n"
              "Live trading can lose money rapidly, including more than you "
              "deposit if margin/leverage is used. Read docs/RETURNS_AND_RISK.md.")
        return 2
    cfg = AgentConfig(symbols=args.symbols.split(","), initial_capital=args.capital,
                      live=True, paper_trading_endpoint=not args.production,
                      poll_interval_seconds=args.interval, risk=_risk_from_args(args))
    cfg.validate()  # raises if credentials are missing
    endpoint = "PRODUCTION (real money)" if args.production else "UAT sandbox"
    confirm = input(f"About to trade {cfg.symbols} on Webull {endpoint}. Type 'TRADE' to proceed: ")
    if confirm.strip() != "TRADE":
        print("Aborted.")
        return 1
    agent = TradingAgent(cfg, _build_strategy(args.strategy, args), make_broker(cfg))
    agent.run(max_cycles=args.cycles)
    return 0


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--strategy", choices=list(STRATEGIES), default="ma_cross")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=50)
    p.add_argument("--lookback", type=int, default=90)
    p.add_argument("--allow-short", action="store_true")
    # Risk knobs.
    p.add_argument("--max-position", type=float, default=0.20)
    p.add_argument("--risk-per-trade", type=float, default=0.01)
    p.add_argument("--max-leverage", type=float, default=1.0)
    p.add_argument("--daily-loss-limit", type=float, default=0.03)
    p.add_argument("--max-drawdown", type=float, default=0.15)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quant trading agent")
    sub = parser.add_subparsers(dest="command", required=True)

    bt = sub.add_parser("backtest", help="run a historical backtest")
    _add_common(bt)
    bt.add_argument("--symbol", default="AAPL")
    bt.add_argument("--range", default="2y")
    bt.add_argument("--csv", default=None, help="load OHLCV from a CSV (date,open,high,low,close[,volume])")
    bt.add_argument("--synthetic", action="store_true", help="use synthetic data (offline)")
    bt.add_argument("--days", type=int, default=504)
    bt.add_argument("--seed", type=int, default=42)
    bt.set_defaults(func=cmd_backtest)

    wf = sub.add_parser("walkforward", help="walk-forward (out-of-sample) validation")
    _add_common(wf)
    wf.add_argument("--symbol", default="AAPL")
    wf.add_argument("--range", default="5y")
    wf.add_argument("--csv", default=None, help="load OHLCV from a CSV instead of Yahoo")
    wf.add_argument("--synthetic", action="store_true")
    wf.add_argument("--days", type=int, default=1260)
    wf.add_argument("--seed", type=int, default=42)
    wf.add_argument("--train", type=int, default=252, help="in-sample window (bars)")
    wf.add_argument("--test", type=int, default=63, help="out-of-sample window (bars)")
    wf.add_argument("--select", default="sharpe", choices=["sharpe", "cagr", "calmar", "sortino"])
    wf.add_argument("--fast-grid", default="10,20,30")
    wf.add_argument("--slow-grid", default="50,100,150")
    wf.add_argument("--lookback-grid", default="30,60,90,120")
    wf.set_defaults(func=cmd_walkforward)

    pa = sub.add_parser("paper", help="run the agent on the paper broker")
    _add_common(pa)
    pa.add_argument("--symbols", default="AAPL,MSFT,SPY")
    pa.add_argument("--cycles", type=int, default=1)
    pa.add_argument("--interval", type=int, default=60)
    pa.add_argument("--no-sleep", action="store_true")
    pa.set_defaults(func=cmd_paper)

    lv = sub.add_parser("live", help="trade live on Webull (requires credentials)")
    _add_common(lv)
    lv.add_argument("--symbols", default="AAPL")
    lv.add_argument("--cycles", type=int, default=None)
    lv.add_argument("--interval", type=int, default=60)
    lv.add_argument("--production", action="store_true",
                    help="use api.webull.com (REAL MONEY) instead of UAT sandbox")
    lv.add_argument("--i-understand-the-risk", action="store_true")
    lv.set_defaults(func=cmd_live)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
