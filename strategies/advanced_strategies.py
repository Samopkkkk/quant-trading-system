"""
Advanced Quantitative Strategies
Pairs Trading, Statistical Arbitrage, Machine Learning based strategies
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from strategies.base_strategy import BaseStrategy


class PairsTradingStrategy(BaseStrategy):
    """
    Pairs Trading Strategy
    
    Find two correlated securities, trade when they diverge from the spread
    Works well for Gold/Silver, stocks in same sector, ETFs
    """
    
    def __init__(self, symbol1: str = "GC", symbol2: str = "SI",
                 lookback: int = 60, entry_threshold: float = 2.0,
                 exit_threshold: float = 0.5):
        super().__init__()
        self.symbol1 = symbol1  # Primary (e.g., Gold)
        self.symbol2 = symbol2  # Secondary (e.g., Silver)
        self.lookback = lookback  # Days to calculate spread
        self.entry_threshold = entry_threshold  # Z-score entry
        self.exit_threshold = exit_threshold  # Z-score exit
        self.position = 0  # 1: long spread, -1: short spread, 0: flat
        
    def calculate_spread(self, price1: pd.Series, price2: pd.Series) -> pd.Series:
        """Calculate spread (price ratio)"""
        return price1 / price2
    
    def calculate_zscore(self, spread: pd.Series) -> float:
        """Calculate z-score of spread"""
        mean = spread.rolling(self.lookback).mean()
        std = spread.rolling(self.lookback).std()
        
        if std.iloc[-1] == 0 or np.isnan(std.iloc[-1]):
            return 0
        
        return (spread.iloc[-1] - mean.iloc[-1]) / std.iloc[-1]
    
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data or not self.engine:
            return signals
        
        # Need both symbols data
        # Simplified: using single data for demonstration
        lookback_data = self.engine.data.loc[:date].tail(self.lookback + 1)
        
        if len(lookback_data) < self.lookback:
            return signals
        
        # For pairs trading, you'd need data for both securities
        # This is a simplified version
        return signals


class StatisticalArbitrageStrategy(BaseStrategy):
    """
    Statistical Arbitrage Strategy
    
    Use cointegration to find trading opportunities
    """
    
    def __init__(self, symbols: List[str] = None,
                 lookback: int = 100,
                 entry_zscore: float = 2.0,
                 exit_zscore: float = 0.0):
        super().__init__()
        self.symbols = symbols or ["GC", "SI", "ES"]
        self.lookback = lookback
        self.entry_zscore = entry_zscore
        self.exit_zscore = exit_zscore
        self.cointegration_pairs: List[Tuple] = []
        self.positions: Dict[str, int] = {}
        
    def find_cointegrated_pairs(self, prices: pd.DataFrame) -> List[Dict]:
        """Find cointegrated pairs using Engle-Granger test"""
        n = len(self.symbols)
        pairs = []
        
        for i in range(n):
            for j in range(i + 1, n):
                sym1, sym2 = self.symbols[i], self.symbols[j]
                
                # Calculate spread
                spread = prices[sym1] - prices[sym2]
                
                # Simple cointegration check (variance ratio)
                spread_returns = spread.pct_change().dropna()
                hurst = self._calculate_hurst_exponent(spread_returns)
                
                if hurst < 0.5:  # Mean reverting
                    pairs.append({
                        'sym1': sym1,
                        'sym2': sym2,
                        'hurst': hurst
                    })
        
        return pairs
    
    def _calculate_hurst_exponent(self, returns: pd.Series) -> float:
        """Calculate Hurst exponent to determine mean reversion"""
        if len(returns) < 20:
            return 0.5
        
        # Simplified Hurst calculation
        lags = range(2, min(20, len(returns) // 2))
        tau = [returns.iloc[lag:].var() / returns.var() for lag in lags]
        
        if all(t > 0 for t in tau):
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0] * 0.5
        return 0.5
    
    def on_bar(self, data, date) -> List[Dict]:
        # Statistical arbitrage implementation
        return []


class MeanReversionEnhancedStrategy(BaseStrategy):
    """
    Enhanced Mean Reversion Strategy
    
    Combines multiple mean reversion indicators:
    - Bollinger Bands
    - RSI
    - Z-Score
    """
    
    def __init__(self, symbol: str = "SPY",
                 bb_period: int = 20,
                 bb_std: float = 2.0,
                 rsi_period: int = 14,
                 rsi_oversold: float = 30,
                 rsi_overbought: float = 70):
        super().__init__()
        self.symbol = symbol
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.position = 0
        
    def calculate_bollinger_bands(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        sma = prices.rolling(self.bb_period).mean()
        std = prices.rolling(self.bb_period).std()
        
        upper = sma + (std * self.bb_std)
        lower = sma - (std * self.bb_std)
        
        return upper, sma, lower
    
    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data or not self.engine:
            return signals
        
        lookback = self.engine.data.loc[:date].tail(self.bb_period + 1)
        
        if len(lookback) < self.bb_period:
            return signals
        
        prices = lookback['close']
        
        # Calculate indicators
        upper, middle, lower = self.calculate_bollinger_bands(prices)
        rsi = self.calculate_rsi(prices)
        
        current_price = prices.iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_lower = lower.iloc[-1]
        current_upper = upper.iloc[-1]
        
        # Buy signal: price near lower band + RSI oversold
        if current_price <= current_lower * 1.02 and current_rsi < self.rsi_oversold:
            if self.position != 1:
                signals.append({
                    'action': 'buy',
                    'symbol': self.symbol,
                    'quantity': 1
                })
                self.position = 1
        
        # Sell signal: price near upper band + RSI overbought
        elif current_price >= current_upper * 0.98 and current_rsi > self.rsi_overbought:
            if self.position != -1:
                signals.append({
                    'action': 'sell',
                    'symbol': self.symbol,
                    'quantity': 1
                })
                self.position = -1
        
        # Exit: mean reversion complete
        elif self.position != 0 and abs(current_price - middle.iloc[-1]) < middle.iloc[-1] * 0.01:
            signals.append({
                'action': 'close',
                'symbol': self.symbol,
                'quantity': abs(self.position)
            })
            self.position = 0
        
        return signals


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy
    
    Trade with the trend using multiple timeframes
    """
    
    def __init__(self, symbol: str = "SPY",
                 fast_ma: int = 10,
                 medium_ma: int = 30,
                 slow_ma: int = 90):
        super().__init__()
        self.symbol = symbol
        self.fast_ma = fast_ma
        self.medium_ma = medium_ma
        self.slow_ma = slow_ma
        self.position = 0
        
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data or not self.engine:
            return signals
        
        lookback = self.engine.data.loc[:date].tail(self.slow_ma + 1)
        
        if len(lookback) < self.slow_ma:
            return signals
        
        prices = lookback['close']
        
        # Calculate MAs
        fast = prices.rolling(self.fast_ma).mean()
        medium = prices.rolling(self.medium_ma).mean()
        slow = prices.rolling(self.slow_ma).mean()
        
        # Current values
        f, m, s = fast.iloc[-1], medium.iloc[-1], slow.iloc[-1]
        pf, pm, ps = fast.iloc[-2], medium.iloc[-2], slow.iloc[-2]
        
        # Golden cross (bullish)
        if pm >= ps and m < s and f > m:
            if self.position != 1:
                signals.append({
                    'action': 'buy',
                    'symbol': self.symbol,
                    'quantity': 1
                })
                self.position = 1
        
        # Death cross (bearish)
        elif pm <= ps and m > s and f < m:
            if self.position != -1:
                signals.append({
                    'action': 'sell',
                    'symbol': self.symbol,
                    'quantity': 1
                })
                self.position = -1
        
        return signals


class FactorStrategy(BaseStrategy):
    """
    Factor-based Strategy
    
    Use multiple factors:
    - Momentum
    - Value
    - Quality
    """
    
    def __init__(self, symbols: List[str] = None):
        super().__init__()
        self.symbols = symbols or []
        self.weights: Dict[str, float] = {}
        
    def calculate_momentum_factor(self, prices: pd.Series, period: int = 20) -> float:
        """Momentum factor: return over period"""
        if len(prices) < period:
            return 0
        return (prices.iloc[-1] / prices.iloc[-period]) - 1
    
    def calculate_value_factor(self, price: float, fair_value: float) -> float:
        """Value factor: deviation from fair value"""
        return (fair_value - price) / fair_value
    
    def calculate_quality_factor(self, returns: pd.Series) -> float:
        """Quality factor: risk-adjusted returns (Sharpe-like)"""
        if len(returns) < 2 or returns.std() == 0:
            return 0
        return returns.mean() / returns.std()
    
    def on_bar(self, data, date) -> List[Dict]:
        # Factor-based strategy implementation
        return []


# ============== Strategy Factory ==============

def create_advanced_strategy(strategy_name: str, **kwargs) -> BaseStrategy:
    """Create advanced strategy instance"""
    strategies = {
        'pairs_trading': PairsTradingStrategy,
        'pairs': PairsTradingStrategy,
        'stat_arb': StatisticalArbitrageStrategy,
        'statistical_arbitrage': StatisticalArbitrageStrategy,
        'mean_reversion_enhanced': MeanReversionEnhancedStrategy,
        'momentum': MomentumStrategy,
        'factor': FactorStrategy,
    }
    
    strategy_class = strategies.get(strategy_name.lower())
    if strategy_class:
        return strategy_class(**kwargs)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


if __name__ == "__main__":
    # Test strategies
    strategy = MeanReversionEnhancedStrategy(symbol="SPY")
    print(f"Strategy: {strategy.name}")
    print(f"BB Period: {strategy.bb_period}")
    print(f"RSI Period: {strategy.rsi_period}")
