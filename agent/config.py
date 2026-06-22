"""Configuration for the trading agent.

Design rules:
  * Secrets ONLY come from environment variables. Nothing is hard-coded.
  * Paper trading is the default. Going live is an explicit, deliberate act.
  * Risk parameters live here so they are auditable in one place.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


# Webull OpenAPI endpoints. The UAT host is Webull's sandbox; api.webull.com is
# real money. We never default to production.
WEBULL_UAT_ENDPOINT = "us-openapi-alb.uat.webullbroker.com"
WEBULL_PROD_ENDPOINT = "api.webull.com"


@dataclass
class RiskConfig:
    """All risk limits in one auditable place.

    Defaults are intentionally conservative. The aggressiveness of the system
    is governed here, not buried inside a strategy.
    """
    # Fraction of equity that a single position may occupy (notional / equity).
    max_position_fraction: float = 0.20
    # Capital risked per trade if a stop is supplied (loss to stop / equity).
    risk_per_trade_fraction: float = 0.01
    # Target annualized volatility for vol-targeted sizing (None disables it).
    target_annual_vol: float | None = 0.20
    # Hard cap on gross exposure (sum |position notional| / equity).
    max_gross_leverage: float = 1.0
    # Halt opening NEW positions once cumulative loss for the day hits this.
    daily_loss_limit_fraction: float = 0.03
    # Kill switch: flatten everything and stop once drawdown from peak hits this.
    max_drawdown_limit_fraction: float = 0.15
    # Optional fractional-Kelly sizing cap (None disables Kelly entirely).
    kelly_fraction_cap: float | None = None

    def validate(self) -> None:
        if not 0 < self.max_position_fraction <= 1.0:
            raise ValueError("max_position_fraction must be in (0, 1]")
        if not 0 < self.risk_per_trade_fraction <= 1.0:
            raise ValueError("risk_per_trade_fraction must be in (0, 1]")
        if self.max_gross_leverage <= 0:
            raise ValueError("max_gross_leverage must be > 0")
        if not 0 < self.daily_loss_limit_fraction <= 1.0:
            raise ValueError("daily_loss_limit_fraction must be in (0, 1]")
        if not 0 < self.max_drawdown_limit_fraction <= 1.0:
            raise ValueError("max_drawdown_limit_fraction must be in (0, 1]")

    # ---- Named presets (the aggressiveness dial, made explicit) ----
    @classmethod
    def conservative(cls) -> "RiskConfig":
        """Survival-first: small positions, no leverage, tight kill switch."""
        return cls(max_position_fraction=0.10, risk_per_trade_fraction=0.005,
                   target_annual_vol=0.12, max_gross_leverage=1.0,
                   daily_loss_limit_fraction=0.02, max_drawdown_limit_fraction=0.10)

    @classmethod
    def balanced(cls) -> "RiskConfig":
        """The default. Reasonable risk for a single retail account."""
        return cls()

    @classmethod
    def aggressive(cls) -> "RiskConfig":
        """High target, HIGH probability of large drawdown or ruin.

        Use only with money you can lose entirely. Run `python -m agent.montecarlo`
        to see the ruin probability this implies before enabling it.
        """
        return cls(max_position_fraction=0.50, risk_per_trade_fraction=0.02,
                   target_annual_vol=0.40, max_gross_leverage=3.0,
                   daily_loss_limit_fraction=0.08, max_drawdown_limit_fraction=0.35)


@dataclass
class AgentConfig:
    symbols: list[str] = field(default_factory=lambda: ["AAPL", "MSFT", "SPY"])
    initial_capital: float = 100_000.0

    # Broker selection.
    live: bool = False                 # False => paper broker. True => Webull.
    paper_trading_endpoint: bool = True  # If live, use Webull UAT unless False.
    dry_run: bool = False              # If True, log intended orders, send none.

    # Execution model (also used by the paper broker / backtest).
    commission_per_share: float = 0.0   # Webull US stock commission is $0.
    commission_min: float = 0.0
    slippage_bps: float = 2.0           # 2 bps modelled slippage.

    # Loop cadence for live/paper run, in seconds.
    poll_interval_seconds: int = 60

    # If True, the live/paper loop only trades during US-equity regular hours.
    enforce_market_hours: bool = False

    # Auto symbol selection (新标的选择). If `universe` is set, the agent screens
    # that candidate pool and trades the top `screen_top_n`, re-screening every
    # `rescreen_every` cycles; positions in dropped names are flattened. If None,
    # the agent trades the fixed `symbols` list.
    universe: list[str] | None = None
    screen_top_n: int = 5
    rescreen_every: int = 1
    screen_min_cmf: float | None = None        # require net inflow (CMF >=) to select

    # Path to a JSON state file (persists kill switch / peak equity / trade log
    # across restarts). None disables persistence (fine for backtests).
    state_path: str | None = None

    risk: RiskConfig = field(default_factory=RiskConfig)

    # ---- Webull credentials (env only) ----
    webull_app_key: str = field(default_factory=lambda: os.getenv("WEBULL_APP_KEY", ""))
    webull_app_secret: str = field(default_factory=lambda: os.getenv("WEBULL_APP_SECRET", ""))
    webull_account_id: str = field(default_factory=lambda: os.getenv("WEBULL_ACCOUNT_ID", ""))
    webull_region: str = field(default_factory=lambda: os.getenv("WEBULL_REGION", "us"))

    @property
    def webull_endpoint(self) -> str:
        return WEBULL_UAT_ENDPOINT if self.paper_trading_endpoint else WEBULL_PROD_ENDPOINT

    def require_live_credentials(self) -> None:
        """Fail loudly if live trading is requested without full credentials."""
        missing = [
            name for name, val in [
                ("WEBULL_APP_KEY", self.webull_app_key),
                ("WEBULL_APP_SECRET", self.webull_app_secret),
                ("WEBULL_ACCOUNT_ID", self.webull_account_id),
            ] if not val
        ]
        if missing:
            raise RuntimeError(
                "Live trading requires these environment variables: "
                + ", ".join(missing)
            )

    def validate(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be > 0")
        if not self.symbols:
            raise ValueError("at least one symbol is required")
        self.risk.validate()
        if self.live:
            self.require_live_credentials()
