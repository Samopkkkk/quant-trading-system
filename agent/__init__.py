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
from .backtest import Backtester, BacktestReport, Metrics
from .broker import Broker, PaperBroker, WebullBroker, make_broker
from .risk import RiskManager, kelly_fraction
from .strategies import (
    STRATEGIES, Strategy, MovingAverageCross, Momentum, RsiMeanReversion,
)
from .types import Order, Fill, Position, Signal, Side, OrderType

__version__ = "1.0.0"

__all__ = [
    "AgentConfig", "RiskConfig", "TradingAgent",
    "Backtester", "BacktestReport", "Metrics",
    "Broker", "PaperBroker", "WebullBroker", "make_broker",
    "RiskManager", "kelly_fraction",
    "STRATEGIES", "Strategy", "MovingAverageCross", "Momentum", "RsiMeanReversion",
    "Order", "Fill", "Position", "Signal", "Side", "OrderType",
]
