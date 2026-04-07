"""
Risk Control Scaffolding
=======================
Strict risk management for options trading MVP.
"""

from typing import Dict, Optional
from dataclasses import dataclass
import pandas as pd


@dataclass
class RiskLimits:
    """Risk limits configuration"""
    # Position limits
    max_position_size: int = 1           # Max contracts per trade
    max_portfolio_positions: int = 3     # Max concurrent positions
    
    # Loss limits
    max_daily_loss: float = 500.0        # Max daily loss ($)
    max_monthly_loss: float = 2000.0      # Max monthly loss ($)
    max_loss_per_trade: float = 200.0     # Max loss per trade ($)
    
    # Option-specific
    max_delta_exposure: float = 100.0     # Max delta exposure
    max_vega_exposure: float = 50.0       # Max vega exposure
    max_gamma_exposure: float = 20.0      # Max gamma exposure
    
    # Capital allocation
    max_capital_per_trade: float = 2000.0  # Max capital per trade
    max_portfolio_capital: float = 10000.0 # Max total capital deployed


class RiskManager:
    """
    Risk manager for options trading.
    
    Strict controls:
    - Position sizing limits
    - Daily/monthly loss limits
    - Greeks exposure limits
    - Capital allocation limits
    """
    
    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.daily_pnl = 0.0
        self.monthly_pnl = 0.0
        self.positions = []
        self.trade_log = []
    
    def can_open_position(self, symbol: str, premium: float, 
                         contracts: int = 1) -> tuple[bool, str]:
        """
        Check if a new position can be opened.
        
        Returns:
            (allowed, reason)
        """
        # Check position count
        if len(self.positions) >= self.limits.max_portfolio_positions:
            return False, f"Max positions reached ({self.limits.max_portfolio_positions})"
        
        # Check capital per trade
        cost = premium * contracts * 100  # 100 shares per contract
        if cost > self.limits.max_capital_per_trade:
            return False, f"Exceeds max capital per trade (${self.limits.max_capital_per_trade})"
        
        # Check daily loss limit
        if self.daily_pnl <= -self.limits.max_daily_loss:
            return False, f"Daily loss limit reached (${self.limits.max_daily_loss})"
        
        # Check monthly loss limit
        if self.monthly_pnl <= -self.limits.max_monthly_loss:
            return False, f"Monthly loss limit reached (${self.limits.max_monthly_loss})"
        
        return True, "OK"
    
    def calculate_position_size(self, premium: float, 
                                account_value: float = 100000) -> int:
        """
        Calculate appropriate position size based on risk rules.
        
        Args:
            premium: Option premium
            account_value: Total account value
        
        Returns:
            Number of contracts to trade
        """
        # Use 1-2% of account per trade
        max_per_trade = account_value * 0.02
        contracts = int(max_per_trade / (premium * 100))
        
        # Apply limits
        contracts = min(contracts, self.limits.max_position_size)
        contracts = max(contracts, 1)  # At least 1
        
        return contracts
    
    def check_stop_loss(self, entry_premium: float, 
                       current_premium: float) -> bool:
        """
        Check if stop loss should be triggered.
        
        Returns:
            True if should exit position
        """
        loss_per_contract = (entry_premium - current_premium) * 100
        
        if loss_per_contract >= self.limits.max_loss_per_trade:
            return True
        
        return False
    
    def record_trade(self, symbol: str, action: str, premium: float,
                    contracts: int, pnl: float = 0.0):
        """Record a trade for tracking"""
        self.trade_log.append({
            "symbol": symbol,
            "action": action,
            "premium": premium,
            "contracts": contracts,
            "pnl": pnl
        })
        
        if action == "SELL":  # Closing position
            self.daily_pnl += pnl
            self.monthly_pnl += pnl
    
    def reset_daily(self):
        """Reset daily tracking"""
        self.daily_pnl = 0.0
    
    def get_risk_summary(self) -> Dict:
        """Get current risk summary"""
        return {
            "daily_pnl": self.daily_pnl,
            "monthly_pnl": self.monthly_pnl,
            "open_positions": len(self.positions),
            "daily_loss_remaining": self.limits.max_daily_loss + self.daily_pnl,
            "monthly_loss_remaining": self.limits.max_monthly_loss + self.monthly_pnl
        }


class GreeksCalculator:
    """
    Simple Greeks calculator for risk monitoring.
    
    MVP: Uses simplified Black-Scholes approximation.
    """
    
    @staticmethod
    def estimate_delta(spot: float, strike: float, dte: int, 
                     iv: float, is_call: bool = True) -> float:
        """
        Estimate option delta.
        
        Simplified approximation for MVP.
        """
        import math
        
        if dte <= 0:
            return 1.0 if is_call else -1.0
        
        # Time to expiration in years
        t = dte / 365
        
        # Log money-ness
        if strike > 0 and spot > 0:
            moneyness = math.log(spot / strike)
        else:
            moneyness = 0
        
        # Simplified delta (doesn't account for all factors)
        # Uses approximation based on moneyness and time
        if is_call:
            if moneyness > 0.5:
                return 0.9
            elif moneyness < -0.5:
                return 0.1
            else:
                return 0.5
        else:
            if moneyness > 0.5:
                return -0.1
            elif moneyness < -0.5:
                return -0.9
            else:
                return -0.5
    
    @staticmethod
    def estimate_vega(spot: float, strike: float, dte: int, 
                     iv: float) -> float:
        """Estimate option vega (sensitivity to IV)"""
        import math
        
        if dte <= 0:
            return 0.0
        
        # Simplified vega approximation
        t = dte / 365
        return math.sqrt(t) * 0.1
    
    @staticmethod
    def estimate_theta(spot: float, strike: float, dte: int,
                     iv: float, is_call: bool = True) -> float:
        """Estimate option theta (daily time decay)"""
        import math
        
        if dte <= 0:
            return 0.0
        
        # Simplified theta
        t = dte / 365
        base = 0.01 * math.sqrt(t)
        
        return -base if is_call else -base


if __name__ == "__main__":
    # Test risk manager
    rm = RiskManager()
    
    # Test position sizing
    size = rm.calculate_position_size(premium=5.0, account_value=100000)
    print(f"Position size for $5 premium: {size} contracts")
    
    # Test can open
    allowed, reason = rm.can_open_position("SPY", 5.0, 1)
    print(f"Can open SPY position: {allowed} ({reason})")
    
    # Test risk summary
    print(f"\nRisk summary: {rm.get_risk_summary()}")
