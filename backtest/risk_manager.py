"""
Risk Management Module
Position sizing, risk controls, and portfolio management
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_position_size: float = 0.1  # Max 10% of portfolio per position
    max_total_leverage: float = 1.0  # No leverage by default
    max_loss_per_trade: float = 0.02  # Max 2% loss per trade
    max_daily_loss: float = 0.05  # Max 5% daily loss
    max_drawdown: float = 0.20  # Max 20% drawdown


class RiskManager:
    """
    Risk Manager
    
    Manages position sizing, risk controls, and portfolio risk
    """
    
    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        self.peak_equity = 0
        self.daily_pnl = 0
        self.stop_trading = False
        
    def calculate_position_size(self, 
                              capital: float,
                              entry_price: float,
                              stop_loss_pct: float) -> int:
        """
        Calculate position size based on risk
        
        Args:
            capital: Total capital
            entry_price: Entry price
            stop_loss_pct: Stop loss percentage
        
        Returns:
            Number of contracts/shares
        """
        # Risk-based sizing: risk = capital * risk_per_trade
        risk_amount = capital * self.config.max_loss_per_trade
        
        # Position size = risk / (entry * stop_loss_pct)
        position_value = risk_amount / stop_loss_pct
        position_size = int(position_value / entry_price)
        
        # Apply max position size limit
        max_size = int(capital * self.config.max_position_size / entry_price)
        position_size = min(position_size, max_size)
        
        return max(1, position_size)  # Minimum 1
    
    def calculate_kelly_criterion(self, win_rate: float, avg_win: float, 
                                   avg_loss: float) -> float:
        """
        Calculate Kelly Criterion for position sizing
        
        Args:
            win_rate: Win rate (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount
        
        Returns:
            Kelly percentage (0-1)
        """
        if avg_loss == 0:
            return 0
            
        b = avg_win / avg_loss  # Win/loss ratio
        p = win_rate  # Probability of win
        q = 1 - p  # Probability of loss
        
        kelly = (b * p - q) / b
        
        # Kelly should be positive
        return max(0, min(kelly, 0.25))  # Cap at 25%
    
    def calculate_volatility_position(self, 
                                     capital: float,
                                     volatility: float,
                                     target_risk: float = 0.02) -> int:
        """
        Calculate position size based on volatility
        
        Args:
            capital: Total capital
            volatility: Daily volatility (std of returns)
            target_risk: Target risk per trade
        
        Returns:
            Position size
        """
        # Risk = position_size * volatility
        # position_size = target_risk * capital / volatility
        position_size = (target_risk * capital) / volatility
        
        return max(1, int(position_size))
    
    def check_risk_limits(self, 
                         current_equity: float,
                         positions: Dict[str, float]) -> Dict[str, bool]:
        """
        Check if any risk limits are breached
        
        Returns:
            Dict of limit checks
        """
        # Update peak equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        # Calculate current drawdown
        if self.peak_equity > 0:
            drawdown = (self.peak_equity - current_equity) / self.peak_equity
        else:
            drawdown = 0
        
        # Check limits
        checks = {
            'max_drawdown_breached': drawdown > self.config.max_drawdown,
            'daily_loss_breached': abs(self.daily_pnl) / self.peak_equity > self.config.max_daily_loss,
            'stop_trading': self.stop_trading
        }
        
        # Auto-stop if drawdown exceeded
        if checks['max_drawdown_breached']:
            self.stop_trading = True
            print(f"⚠️ Max drawdown exceeded: {drawdown:.2%}. Stopping trading.")
        
        return checks
    
    def update_daily_pnl(self, pnl: float):
        """Update daily P&L"""
        self.daily_pnl += pnl
        
    def reset_daily(self):
        """Reset daily counters"""
        self.daily_pnl = 0


class PortfolioManager:
    """
    Portfolio Manager
    
    Manages multi-strategy/multi-asset portfolios
    """
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.allocations: Dict[str, float] = {}
        self.returns: Dict[str, List[float]] = {}
        
    def equal_weight(self, strategies: List[str]):
        """Equal weight allocation"""
        weight = 1.0 / len(strategies)
        for strategy in strategies:
            self.allocations[strategy] = weight
            
    def risk_parity(self, volatilities: Dict[str, float]):
        """
        Risk parity allocation
        
        Allocate based on inverse volatility
        """
        inv_vol = {k: 1/v for k, v in volatilities.items() if v > 0}
        total = sum(inv_vol.values())
        
        for k, v in inv_vol.items():
            self.allocations[k] = v / total
            
    def momentum_weighted(self, returns: Dict[str, float], lookback: int = 20):
        """
        Momentum-weighted allocation
        
        Allocate more to recent winners
        """
        # Normalize returns
        total = sum(max(0, r) for r in returns.values())
        
        if total == 0:
            self.equal_weight(list(returns.keys()))
            return
            
        for strategy, ret in returns.items():
            weight = max(0, ret) / total
            self.allocations[strategy] = weight
    
    def get_allocation(self, strategy: str) -> float:
        """Get allocation for a strategy"""
        return self.allocations.get(strategy, 0)
    
    def rebalance(self, current_weights: Dict[str, float], 
                  target_weights: Dict[str, float],
                  threshold: float = 0.05) -> Dict[str, float]:
        """
        Rebalance portfolio if deviation exceeds threshold
        
        Returns:
            Rebalance orders
        """
        orders = {}
        
        for strategy in target_weights:
            current = current_weights.get(strategy, 0)
            target = target_weights[strategy]
            
            if abs(current - target) > threshold:
                orders[strategy] = target - current
                
        return orders
    
    def calculate_portfolio_metrics(self) -> Dict[str, float]:
        """Calculate portfolio-level metrics"""
        if not self.returns:
            return {}
            
        # Combine returns
        all_returns = []
        for strategy_returns in self.returns.values():
            all_returns.extend(strategy_returns)
            
        if not all_returns:
            return {}
            
        returns_array = np.array(all_returns)
        
        return {
            'total_return': np.sum(returns_array),
            'volatility': np.std(returns_array) * np.sqrt(252),
            'sharpe_ratio': np.mean(returns_array) / np.std(returns_array) * np.sqrt(252) if np.std(returns_array) > 0 else 0,
            'max_drawdown': self._calculate_max_drawdown(returns_array),
            'win_rate': len(returns_array[returns_array > 0]) / len(returns_array)
        }
    
    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate max drawdown"""
        equity = (1 + returns).cumprod()
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        return abs(drawdown.min())


# ============== Convenience Functions ==============

def calculate_sharpe(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """Calculate Sharpe ratio"""
    if not returns or np.std(returns) == 0:
        return 0
        
    excess_returns = np.array(returns) - risk_free_rate
    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)


def calculate_sortino(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """Calculate Sortino ratio"""
    if not returns:
        return 0
        
    excess_returns = np.array(returns) - risk_free_rate
    downside = excess_returns[excess_returns < 0]
    
    if len(downside) == 0 or np.std(downside) == 0:
        return 0
        
    return np.mean(excess_returns) / np.std(downside) * np.sqrt(252)


def calculate_var(returns: List[float], confidence: float = 0.95) -> float:
    """Calculate Value at Risk"""
    if not returns:
        return 0
    return np.percentile(returns, (1 - confidence) * 100)


def calculate_cvar(returns: List[float], confidence: float = 0.95) -> float:
    """Calculate Conditional Value at Risk (Expected Shortfall)"""
    var = calculate_var(returns, confidence)
    return np.mean([r for r in returns if r <= var])


if __name__ == "__main__":
    # Test
    config = RiskConfig()
    rm = RiskManager(config)
    
    # Test position sizing
    size = rm.calculate_position_size(
        capital=100000,
        entry_price=150,
        stop_loss_pct=0.05  # 5% stop loss
    )
    print(f"Position size: {size}")
    
    # Test Kelly Criterion
    kelly = rm.calculate_kelly_criterion(
        win_rate=0.6,
        avg_win=500,
        avg_loss=300
    )
    print(f"Kelly: {kelly:.2%}")
