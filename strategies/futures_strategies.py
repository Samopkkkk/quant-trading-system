"""
期货策略
"""
import pandas as pd
import numpy as np
from typing import List, Dict
from strategies.base_strategy import BaseStrategy


class FuturesStrategy(BaseStrategy):
    """期货策略基类"""
    
    def __init__(self, symbol: str, contract_size: float = 1.0):
        super().__init__()
        self.symbol = symbol
        self.contract_size = contract_size  # 合约乘数


class TrendFollowingStrategy(FuturesStrategy):
    """
    趋势跟踪策略 - 均线交叉
    """
    
    def __init__(self, symbol: str = "GC",
                 fast_ma: int = 10,
                 slow_ma: int = 50):
        super().__init__(symbol)
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.position = 0  # 1: long, -1: short, 0: flat
        
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data:
            return signals
        
        # 计算均线
        if self.engine and self.engine.data is not None:
            lookback = self.engine.data.loc[:date].tail(self.slow_ma + 1)
            
            if len(lookback) < self.slow_ma:
                return signals
            
            # 计算移动平均
            close_prices = lookback['close']
            fast_ma_value = close_prices.rolling(self.fast_ma).mean().iloc[-1]
            slow_ma_value = close_prices.rolling(self.slow_ma).mean().iloc[-1]
            
            # 获取前一根K线的均线值
            prev_fast = close_prices.rolling(self.fast_ma).mean().iloc[-2]
            prev_slow = close_prices.rolling(self.slow_ma).mean().iloc[-2]
            
            # 金叉做多
            if prev_fast <= prev_slow and fast_ma_value > slow_ma_value:
                if self.position != 1:
                    signals.append({
                        'action': 'buy',
                        'symbol': self.symbol,
                        'quantity': 1
                    })
                    self.position = 1
            
            # 死叉做空
            elif prev_fast >= prev_slow and fast_ma_value < slow_ma_value:
                if self.position != -1:
                    signals.append({
                        'action': 'sell',
                        'symbol': self.symbol,
                        'quantity': 1
                    })
                    self.position = -1
        
        return signals


class MeanReversionStrategy(FuturesStrategy):
    """
    均值回归策略 - 布林带
    """
    
    def __init__(self, symbol: str = "GC",
                 period: int = 20,
                 std_dev: float = 2.0):
        super().__init__(symbol)
        self.period = period
        self.std_dev = std_dev
        self.position = 0
        
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data:
            return signals
        
        if self.engine and self.engine.data is not None:
            lookback = self.engine.data.loc[:date].tail(self.period + 1)
            
            if len(lookback) < self.period:
                return signals
            
            close_prices = lookback['close']
            
            # 计算布林带
            sma = close_prices.rolling(self.period).mean().iloc[-1]
            std = close_prices.rolling(self.period).std().iloc[-1]
            
            upper_band = sma + self.std_dev * std
            lower_band = sma - self.std_dev * std
            
            current_price = close_prices.iloc[-1]
            
            # 价格触及下轨买入
            if current_price <= lower_band and self.position != 1:
                signals.append({
                    'action': 'buy',
                    'symbol': self.symbol,
                    'quantity': 1
                })
                self.position = 1
            
            # 价格触及上轨卖出
            elif current_price >= upper_band and self.position != -1:
                signals.append({
                    'action': 'sell',
                    'symbol': self.symbol,
                    'quantity': 1
                })
                self.position = -1
            
            # 回归均线平仓
            elif self.position != 0:
                if abs(current_price - sma) < std * 0.5:
                    signals.append({
                        'action': 'close',
                        'symbol': self.symbol,
                        'quantity': 1
                    })
                    self.position = 0
        
        return signals


class BreakoutStrategy(FuturesStrategy):
    """
    突破策略 - 通道突破
    """
    
    def __init__(self, symbol: str = "SI",
                 lookback: int = 20,
                 atr_multiplier: float = 2.0):
        super().__init__(symbol)
        self.lookback = lookback
        self.atr_multiplier = atr_multiplier
        self.position = 0
        
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data or 'high' not in data or 'low' not in data:
            return signals
        
        if self.engine and self.engine.data is not None:
            lookback = self.engine.data.loc[:date].tail(self.lookback + 1)
            
            if len(lookback) < self.lookback:
                return signals
            
            # 计算 ATR
            high = lookback['high']
            low = lookback['low']
            close = lookback['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            # 计算通道
            recent_high = high.tail(self.lookback).max()
            recent_low = low.tail(self.lookback).min()
            
            current_price = close.iloc[-1]
            
            # 突破高点做多
            if current_price > recent_high + atr * 0.5 and self.position != 1:
                signals.append({
                    'action': 'buy',
                    'symbol': self.symbol,
                    'quantity': 1
                })
                self.position = 1
            
            # 突破低点做空
            elif current_price < recent_low - atr * 0.5 and self.position != -1:
                signals.append({
                    'action': 'sell',
                    'symbol': self.symbol,
                    'quantity': 1
                })
                self.position = -1
        
        return signals


class GridStrategy(FuturesStrategy):
    """
    网格交易策略
    适用于震荡市场
    """
    
    def __init__(self, symbol: str = "GC",
                 grid_size: float = 0.02,
                 grid_count: int = 10):
        super().__init__(symbol)
        self.grid_size = grid_size  # 网格间距 (2%)
        self.grid_count = grid_count  # 网格数量
        self.base_price = None
        self.positions = {}  # 网格持仓
        
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data:
            return signals
        
        current_price = data['close']
        
        # 初始化网格
        if self.base_price is None:
            self.base_price = current_price
            
            # 建立初始网格
            for i in range(-self.grid_count // 2, self.grid_count // 2 + 1):
                grid_price = self.base_price * (1 + i * self.grid_size)
                distance = (current_price - grid_price) / grid_price
                
                if abs(distance) < self.grid_size * 0.5:
                    # 在网格附近开仓
                    if i < 0:  # 低于基准价，做多
                        signals.append({
                            'action': 'buy',
                            'symbol': self.symbol,
                            'quantity': 1
                        })
                    elif i > 0:  # 高于基准价，做空
                        signals.append({
                            'action': 'sell',
                            'symbol': self.symbol,
                            'quantity': 1
                        })
        
        return signals


class ArbitrageStrategy(FuturesStrategy):
    """
    跨交易所套利策略
    黄金/白银跨市场套利
    """
    
    def __init__(self, symbol1: str = "GC", symbol2: str = "SI",
                 lookback: int = 100,
                 z_threshold: float = 2.0):
        """
        Args:
            symbol1: 第一个品种 (黄金)
            symbol2: 第二个品种 (白银)
            lookback: 回看周期
            z_threshold: Z-score 阈值
        """
        super().__init__(f"{symbol1}_{symbol2}")
        self.symbol1 = symbol1
        self.symbol2 = symbol2
        self.lookback = lookback
        self.z_threshold = z_threshold
        
    def calculate_spread(self, price1: float, price2: float) -> float:
        """计算价差 (标准化)"""
        # 黄金/白银比率
        return price1 / price2
    
    def calculate_zscore(self, spread_series: pd.Series) -> float:
        """计算 Z-score"""
        mean = spread_series.mean()
        std = spread_series.std()
        
        if std == 0:
            return 0
        
        return (spread_series.iloc[-1] - mean) / std
    
    def on_bar(self, data, date) -> List[Dict]:
        # 简化版套利策略
        # 实际需要两个品种的数据
        return []


# 策略工厂
def create_futures_strategy(strategy_name: str, **kwargs) -> FuturesStrategy:
    """创建期货策略实例"""
    strategies = {
        'trend': TrendFollowingStrategy,
        'trend_following': TrendFollowingStrategy,
        'mean_reversion': MeanReversionStrategy,
        'breakout': BreakoutStrategy,
        'grid': GridStrategy,
        'arbitrage': ArbitrageStrategy,
    }
    
    strategy_class = strategies.get(strategy_name.lower())
    if strategy_class:
        return strategy_class(**kwargs)
    else:
        raise ValueError(f"Unknown futures strategy: {strategy_name}")


if __name__ == "__main__":
    # 测试
    strategy = TrendFollowingStrategy(symbol="GC", fast_ma=10, slow_ma=50)
    print(f"策略: {strategy.__class__.__name__}")
    print(f"标的: {strategy.symbol}")
    print(f"快线: {strategy.fast_ma}, 慢线: {strategy.slow_ma}")
