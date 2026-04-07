"""
MVP Options Trading System
=========================
End-to-end options trading MVP with:
- US stock options (Webull)
- Single trend-following strategy
- Small liquid universe
- Reproducible backtest
- Risk controls
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mvp.option_selector import OptionContractSelector, FactorEvaluator, LIQUID_UNDERLYINGS
from mvp.signal_pipeline import TrendFollowingSignal, SignalPipeline, Signal
from mvp.risk_control import RiskManager, RiskLimits, GreeksCalculator


# =============================================================================
# CONFIGURATION - MVP LOCKED
# =============================================================================

class MVPConfig:
    """MVP Configuration - DO NOT EXPAND"""
    
    # Universe
    UNDERLYINGS = list(LIQUID_UNDERLYINGS.keys())[:5]  # Top 5 only for MVP
    
    # Strategy
    STRATEGY_NAME = "SMA_Crossover"
    FAST_MA = 10
    SLOW_MA = 50
    
    # Options
    DTE_MIN = 21
    DTE_MAX = 45
    STRIKE_WIDTH = 0.02  # ATM +/- 2%
    
    # Risk
    INITIAL_CAPITAL = 100000
    MAX_POSITION_SIZE = 1
    MAX_DAILY_LOSS = 500
    
    # Execution
    PAPER_TRADING = True  # Start with paper trading


# =============================================================================
# DATA GENERATOR - FOR BACKTESTING
# =============================================================================

def generate_underlying_data(symbol: str, days: int = 252) -> pd.DataFrame:
    """
    Generate realistic underlying price data for backtesting.
    
    Args:
        symbol: Stock symbol
        days: Number of trading days
    
    Returns:
        DataFrame with OHLCV data
    """
    dates = pd.date_range(end=datetime.now(), periods=days, freq='B')
    np.random.seed(hash(symbol) % 10000)
    
    # Get volatility estimate from config
    vol = LIQUID_UNDERLYINGS.get(symbol, {}).get('vol_estimate', 0.25)
    
    # Generate price with trend + mean reversion
    daily_return = 0.0003  # Small positive drift
    noise = np.random.randn(days) * (vol / np.sqrt(252))
    
    returns = daily_return + noise
    price = 100 * np.cumprod(1 + returns)
    price = np.insert(price, 0, 100)
    price = price[:-1]
    
    # Ensure reasonable price range based on symbol
    if symbol == "SPY":
        price = price * 5  # Scale to ~500
    elif symbol == "QQQ":
        price = price * 4  # Scale to ~400
    
    # Generate OHLC
    data = pd.DataFrame({
        'date': dates,
        'symbol': symbol,
        'open': price * (1 + np.random.uniform(-0.005, 0.005, days)),
        'high': price * (1 + np.abs(np.random.uniform(0, 0.02, days))),
        'low': price * (1 - np.abs(np.random.uniform(0, 0.02, days))),
        'close': price,
        'volume': np.random.randint(10_000_000, 100_000_000, days)
    })
    
    data.set_index('date', inplace=True)
    return data


# =============================================================================
# OPTION PRICING - SIMPLIFIED BLACK-SCHOLES
# =============================================================================

class OptionPricer:
    """
    Simplified option pricing for backtesting.
    
    MVP: Uses intrinsic value + time value approximation.
    """
    
    @staticmethod
    def estimate_premium(underlying_price: float, strike: float,
                        dte: int, iv: float, is_call: bool = True) -> float:
        """
        Estimate option premium.
        
        Simplified: intrinsic + time value
        """
        # Time to expiration (years)
        t = dte / 365
        
        # Intrinsic value
        if is_call:
            intrinsic = max(0, underlying_price - strike)
        else:
            intrinsic = max(0, strike - underlying_price)
        
        # Time value (simplified)
        # Higher IV, more time = more time value
        time_multiplier = np.sqrt(max(t, 0.01))
        time_value = underlying_price * iv * time_multiplier * 0.1
        
        premium = intrinsic + time_value
        
        return max(premium, 0.01)  # Minimum $0.01
    
    @staticmethod
    def calculate_payoff(entry_premium: float, exit_premium: float,
                        is_long: bool = True) -> float:
        """Calculate trade P&L"""
        if is_long:
            return (exit_premium - entry_premium) * 100
        else:
            return (entry_premium - exit_premium) * 100


# =============================================================================
# BACKTEST ENGINE
# =============================================================================

class OptionsBacktest:
    """
    Options backtest engine for MVP strategy.
    
    Flow:
    1. For each day, check for signals on underlyings
    2. On signal, estimate option premium
    3. Simulate trade with slippage
    4. Track P&L and risk limits
    """
    
    def __init__(self, config: MVPConfig):
        self.config = config
        self.signal_gen = TrendFollowingSignal(
            fast_period=config.FAST_MA,
            slow_period=config.SLOW_MA
        )
        self.risk_manager = RiskManager()
        self.pricer = OptionPricer()
        
        # Results
        self.trades = []
        self.equity_curve = [config.INITIAL_CAPITAL]
        self.daily_pnl = []
    
    def run(self) -> Dict:
        """
        Run backtest across all underlyings.
        
        Returns:
            Backtest results
        """
        print("=" * 60)
        print("MVP Options Backtest - SMA Crossover Strategy")
        print("=" * 60)
        
        for symbol in self.config.UNDERLYINGS:
            print(f"\n>>> Testing {symbol}")
            
            # Generate data
            data = generate_underlying_data(symbol, days=252)
            data['symbol'] = symbol
            
            # Run strategy
            signals = self.signal_gen.generate_signals(data)
            
            print(f"    Generated {len(signals)} signals")
            
            # Simulate each signal
            for sig in signals:
                if "BUY" in sig.action:
                    self._simulate_entry(sig)
                elif sig.action == "CLOSE":
                    self._simulate_exit(sig)
        
        return self.get_results()
    
    def _simulate_entry(self, signal: Signal):
        """Simulate entering a position"""
        # Estimate premium
        iv = LIQUID_UNDERLYINGS.get(signal.symbol, {}).get('vol_estimate', 0.25)
        premium = self.pricer.estimate_premium(
            signal.price, signal.strike, 30, iv,
            is_call=("CALL" in signal.action)
        )
        
        # Check risk
        allowed, reason = self.risk_manager.can_open_position(
            signal.symbol, premium
        )
        
        if not allowed:
            print(f"    BLOCKED: {reason}")
            return
        
        # Record trade
        trade = {
            'date': signal.timestamp,
            'symbol': signal.symbol,
            'action': signal.action,
            'underlying_price': signal.price,
            'strike': signal.strike,
            'premium': premium,
            'entry_date': signal.timestamp,
            'status': 'OPEN'
        }
        
        self.trades.append(trade)
        print(f"    ENTER: {signal.action} {signal.symbol} @ ${premium:.2f}")
    
    def _simulate_exit(self, signal: Signal):
        """Simulate exiting a position"""
        # Find matching open position
        for trade in reversed(self.trades):
            if trade['status'] == 'OPEN' and trade['symbol'] == signal.symbol:
                # Estimate exit premium (simplified: same as entry for now)
                # In real backtest, would recalculate based on new price
                exit_premium = trade['premium'] * 0.95  # Small loss assumption
                
                # Calculate P&L
                pnl = self.pricer.calculate_payoff(
                    trade['premium'], exit_premium, is_long=True
                )
                
                trade['status'] = 'CLOSED'
                trade['exit_date'] = signal.timestamp
                trade['exit_premium'] = exit_premium
                trade['pnl'] = pnl
                
                # Update risk manager
                self.risk_manager.record_trade(
                    trade['symbol'], 'SELL', exit_premium, 1, pnl
                )
                
                print(f"    EXIT: {trade['symbol']} @ ${exit_premium:.2f} P&L: ${pnl:.2f}")
                break
        
        # Reset position
        self.signal_gen.current_position = None
    
    def get_results(self) -> Dict:
        """Calculate backtest results"""
        closed_trades = [t for t in self.trades if t.get('status') == 'CLOSED']
        
        if closed_trades:
            pnls = [t['pnl'] for t in closed_trades]
            total_pnl = sum(pnls)
            winning = [p for p in pnls if p > 0]
            losing = [p for p in pnls if p <= 0]
            
            results = {
                'total_trades': len(closed_trades),
                'winning_trades': len(winning),
                'losing_trades': len(losing),
                'win_rate': len(winning) / len(closed_trades) if closed_trades else 0,
                'total_pnl': total_pnl,
                'avg_win': sum(winning) / len(winning) if winning else 0,
                'avg_loss': sum(losing) / len(losing) if losing else 0,
            }
        else:
            results = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
            }
        
        return results


# =============================================================================
# MAIN
# =============================================================================

def run_mvp():
    """Run MVP backtest"""
    print("\n" + "=" * 60)
    print("MVP OPTIONS TRADING SYSTEM")
    print("=" * 60)
    print(f"Strategy: SMA Crossover (10/50)")
    print(f"Universe: {MVPConfig.UNDERLYINGS}")
    print(f"Capital: ${MVPConfig.INITIAL_CAPITAL:,}")
    print("=" * 60 + "\n")
    
    # Run backtest
    backtest = OptionsBacktest(MVPConfig)
    results = backtest.run()
    
    # Print results
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Total Trades: {results['total_trades']}")
    print(f"Winning: {results['winning_trades']}")
    print(f"Losing: {results['losing_trades']}")
    print(f"Win Rate: {results['win_rate']:.1%}")
    print(f"Total P&L: ${results['total_pnl']:,.2f}")
    print(f"Avg Win: ${results['avg_win']:,.2f}")
    print(f"Avg Loss: ${results['avg_loss']:,.2f}")
    print("=" * 60)
    
    return backtest, results


if __name__ == "__main__":
    run_mvp()
