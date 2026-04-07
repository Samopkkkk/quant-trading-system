"""
Trend Following Signal Pipeline
==============================
Clean signal generation for options trading.
Single strategy: SMA crossover on underlying.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np


@dataclass
class Signal:
    """Trading signal"""
    timestamp: str
    symbol: str
    action: str          # "BUY_CALL", "SELL_CALL", "BUY_PUT", "SELL_PUT", "CLOSE", "HOLD"
    strength: float      # Signal strength 0-1
    reason: str         # Human-readable reason
    price: float         # Current price
    strike: float        # Recommended strike
    expiry: str          # Recommended expiry


class TrendFollowingSignal:
    """
    Trend following signal generator using SMA crossover.
    
    Strategy:
    - Fast SMA > Slow SMA = Uptrend = Buy calls
    - Fast SMA < Slow SMA = Downtrend = Buy puts
    - Exit on trend reversal
    
    MVP: Single strategy, no expansion.
    """
    
    def __init__(self, 
                 fast_period: int = 10,
                 slow_period: int = 50,
                 signal_threshold: float = 0.0):
        """
        Args:
            fast_period: Fast SMA period
            slow_period: Slow SMA period
            signal_threshold: Minimum diff to generate signal
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_threshold = signal_threshold
        
        # State
        self.current_position = None  # "CALL" or "PUT" or None
        self.last_signal = None
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Generate trading signals from price data.
        
        Args:
            data: DataFrame with 'close' column
        
        Returns:
            List of signals
        """
        if len(data) < self.slow_period:
            return []
        
        signals = []
        
        # Calculate SMAs
        data = data.copy()
        data['fast_ma'] = data['close'].rolling(self.fast_period).mean()
        data['slow_ma'] = data['close'].rolling(self.slow_period).mean()
        
        # Calculate crossover
        data['ma_diff'] = data['fast_ma'] - data['slow_ma']
        data['ma_diff_prev'] = data['ma_diff'].shift(1)
        
        # Generate signals
        for i in range(self.slow_period, len(data)):
            row = data.iloc[i]
            prev_row = data.iloc[i-1]
            
            # Skip if MA not available
            if pd.isna(row['fast_ma']) or pd.isna(row['slow_ma']):
                continue
            
            timestamp = str(data.index[i])[:19]
            
            # Golden cross (bullish)
            if (prev_row['ma_diff_prev'] <= 0 and row['ma_diff'] > 0):
                if self.current_position != "CALL":
                    signal = Signal(
                        timestamp=timestamp,
                        symbol=str(data['symbol'].iloc[0]),
                        action="BUY_CALL",
                        strength=min(1.0, abs(row['ma_diff']) / row['close']),
                        reason=f"Golden cross: fast MA ({row['fast_ma']:.2f}) > slow MA ({row['slow_ma']:.2f})",
                        price=row['close'],
                        strike=self._calculate_strike(row['close'], 'CALL'),
                        expiry=self._calculate_expiry(30)
                    )
                    signals.append(signal)
                    self.current_position = "CALL"
                    self.last_signal = signal
            
            # Death cross (bearish)
            elif (prev_row['ma_diff_prev'] >= 0 and row['ma_diff'] < 0):
                if self.current_position != "PUT":
                    signal = Signal(
                        timestamp=timestamp,
                        symbol=str(data['symbol'].iloc[0]),
                        action="BUY_PUT",
                        strength=min(1.0, abs(row['ma_diff']) / row['close']),
                        reason=f"Death cross: fast MA ({row['fast_ma']:.2f}) < slow MA ({row['slow_ma']:.2f})",
                        price=row['close'],
                        strike=self._calculate_strike(row['close'], 'PUT'),
                        expiry=self._calculate_expiry(30)
                    )
                    signals.append(signal)
                    self.current_position = "PUT"
                    self.last_signal = signal
        
        return signals
    
    def generate_single_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """
        Generate single current signal (for live trading).
        
        Returns:
            Current signal or None
        """
        if len(data) < self.slow_period:
            return None
        
        # Calculate latest MAs
        fast_ma = data['close'].rolling(self.fast_period).mean().iloc[-1]
        slow_ma = data['close'].rolling(self.slow_period).mean().iloc[-1]
        
        # Get previous MA values
        fast_ma_prev = data['close'].rolling(self.fast_period).mean().iloc[-2]
        slow_ma_prev = data['close'].rolling(self.slow_period).mean().iloc[-2]
        
        ma_diff = fast_ma - slow_ma
        ma_diff_prev = fast_ma_prev - slow_ma_prev
        
        current_price = data['close'].iloc[-1]
        
        # Determine action
        if ma_diff > self.signal_threshold and ma_diff_prev <= 0:
            # Bullish crossover
            return Signal(
                timestamp=str(data.index[-1])[:19],
                symbol=str(data['symbol'].iloc[0]),
                action="BUY_CALL",
                strength=min(1.0, abs(ma_diff) / current_price),
                reason=f"Bullish: fast MA ({fast_ma:.2f}) crossed above slow MA ({slow_ma:.2f})",
                price=current_price,
                strike=self._calculate_strike(current_price, 'CALL'),
                expiry=self._calculate_expiry(30)
            )
        
        elif ma_diff < -self.signal_threshold and ma_diff_prev >= 0:
            # Bearish crossover
            return Signal(
                timestamp=str(data.index[-1])[:19],
                symbol=str(data['symbol'].iloc[0]),
                action="BUY_PUT",
                strength=min(1.0, abs(ma_diff) / current_price),
                reason=f"Bearish: fast MA ({fast_ma:.2f}) crossed below slow MA ({slow_ma:.2f})",
                price=current_price,
                strike=self._calculate_strike(current_price, 'PUT'),
                expiry=self._calculate_expiry(30)
            )
        
        elif self.current_position and ma_diff * ma_diff_prev < 0:
            # Trend reversal - close position
            return Signal(
                timestamp=str(data.index[-1])[:19],
                symbol=str(data['symbol'].iloc[0]),
                action="CLOSE",
                strength=1.0,
                reason=f"Trend reversal: closing {self.current_position} position",
                price=current_price,
                strike=0,
                expiry=""
            )
        
        return None
    
    def _calculate_strike(self, underlying_price: float, 
                         option_type: str) -> float:
        """Calculate ATM strike price"""
        if option_type == "CALL":
            return round(underlying_price / 2.5) * 2.5
        else:
            return round(underlying_price / 2.5) * 2.5
    
    def _calculate_expiry(self, dte: int) -> str:
        """Calculate expiry date string (YYYYMMDD)"""
        from datetime import datetime, timedelta
        expiry = datetime.now() + timedelta(days=dte)
        return expiry.strftime("%y%m%d")


class SignalPipeline:
    """
    End-to-end signal pipeline.
    
    Flow:
    1. Load price data
    2. Generate signals
    3. Apply risk filters
    4. Output actionable signals
    """
    
    def __init__(self, signal_generator: TrendFollowingSignal,
                 risk_manager):
        self.signal_gen = signal_generator
        self.risk_manager = risk_manager
    
    def process(self, data: pd.DataFrame) -> List[Signal]:
        """Process data through full pipeline"""
        # Step 1: Generate signals
        signals = self.signal_gen.generate_signals(data)
        
        # Step 2: Filter with risk rules
        filtered = []
        for sig in signals:
            if sig.action == "HOLD":
                continue
            
            # Check risk manager
            if "BUY" in sig.action:
                allowed, reason = self.risk_manager.can_open_position(
                    sig.symbol, sig.price
                )
                if not allowed:
                    continue
            
            filtered.append(sig)
        
        return filtered


if __name__ == "__main__":
    # Test signal generation
    import numpy as np
    from datetime import datetime, timedelta
    
    # Generate test data with trend
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
    np.random.seed(42)
    
    trend = np.linspace(0, 0.1, 100)
    noise = np.random.randn(100) * 0.02
    price = 100 * np.exp(np.cumsum(0.001 + trend + noise))
    
    data = pd.DataFrame({
        'symbol': ['SPY'] * 100,
        'close': price
    }, index=dates)
    
    # Generate signals
    tf = TrendFollowingSignal(fast_period=10, slow_period=50)
    signals = tf.generate_signals(data)
    
    print(f"Generated {len(signals)} signals:")
    for s in signals:
        print(f"  {s.timestamp}: {s.action} {s.symbol} @ ${s.price:.2f} - {s.reason}")
