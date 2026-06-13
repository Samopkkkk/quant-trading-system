"""Rebuilt quantitative trading agent.

A clean, honest, risk-managed auto-trading agent for Webull (US equities).

Layers:
    config      - configuration and risk limits (secrets from env only)
    types       - shared data types (Order, Fill, Position, Signal, ...)
    data        - market data (Yahoo / CSV / synthetic for tests)
    strategies  - alpha: price history -> desired exposure (no look-ahead)
    risk        - sizing + circuit breakers (daily-loss halt, drawdown kill)
    broker      - PaperBroker (offline) and WebullBroker (real SDK adapter)
    backtest    - event-driven backtest with honest metrics
    engine      - the live/paper TradingAgent loop

There is no configuration of this system that guarantees a profit. See
docs/RETURNS_AND_RISK.md before risking real money.
"""
from .config import AgentConfig, RiskConfig
from .engine import TradingAgent
from .backtest import (
    Backtester, PortfolioBacktester, BacktestReport, Metrics, align_prices,
)
from .broker import (
    Broker, PaperBroker, WebullBroker, DryRunBroker, make_broker,
    parse_instrument_ids, preflight,
)
from .risk import RiskManager, kelly_fraction
from .state import StateStore
from .strategies import (
    STRATEGIES, Strategy, MovingAverageCross, Momentum, RsiMeanReversion,
)
from .validation import walk_forward, param_grid, WalkForwardResult
from .types import Order, Fill, Position, Signal, Side, OrderType

__version__ = "1.0.0"

__all__ = [
    "AgentConfig", "RiskConfig", "TradingAgent",
    "Backtester", "PortfolioBacktester", "BacktestReport", "Metrics", "align_prices",
    "Broker", "PaperBroker", "WebullBroker", "DryRunBroker", "make_broker",
    "parse_instrument_ids", "preflight",
    "RiskManager", "kelly_fraction", "StateStore",
    "STRATEGIES", "Strategy", "MovingAverageCross", "Momentum", "RsiMeanReversion",
    "walk_forward", "param_grid", "WalkForwardResult",
    "Order", "Fill", "Position", "Signal", "Side", "OrderType",
]
