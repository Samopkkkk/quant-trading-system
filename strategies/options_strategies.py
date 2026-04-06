"""
期权策略
"""
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np


class BaseStrategy(ABC):
    """基础策略类"""
    
    def __init__(self):
        self.engine = None
        self.indicators = {}
    
    def set_engine(self, engine):
        self.engine = engine
    
    def on_init(self):
        """初始化策略"""
        pass
    
    @abstractmethod
    def on_bar(self, data, date) -> List[Dict]:
        """
        每根K线调用一次
        
        Args:
            data: 当前K线数据
            date: 当前日期
        
        Returns:
            信号列表 [{"action": "buy/sell", "symbol": "...", "quantity": ...}]
        """
        pass
    
    def on_finish(self):
        """策略结束"""
        pass
    
    def get_indicator(self, name: str) -> pd.Series:
        """获取指标"""
        return self.indicators.get(name, pd.Series())
    
    def set_indicator(self, name: str, value: pd.Series):
        """设置指标"""
        self.indicators[name] = value


class OptionsStrategy(BaseStrategy):
    """期权策略基类"""
    
    def __init__(self, underlying: str, expiry_days: int = 30):
        super().__init__()
        self.underlying = underlying  # 标的股票
        self.expiry_days = expiry_days  # 期权到期天数
    
    def calculate_iv(self, data: pd.Series) -> float:
        """计算隐含波动率 (简化版)"""
        if 'close' in data and 'open' in data:
            returns = np.log(data['close'] / data['close'].shift(1))
            return returns.std() * np.sqrt(252)
        return 0.3
    
    def get_strike_prices(self, current_price: float, 
                          atm_offset: int = 5) -> Dict[str, float]:
        """获取行权价"""
        return {
            'atm': current_price,  # 平值
            'itm_call': current_price * 1.05,  # 实值看涨
            'otm_call': current_price * 1.05,  # 虚值看涨
            'itm_put': current_price * 0.95,   # 实值看跌
            'otm_put': current_price * 0.95,   # 虚值看跌
        }


class IronCondorStrategy(OptionsStrategy):
    """
    铁鹰策略 (Iron Condor)
    
    卖出看涨价差 + 卖出看跌价差
    预期: 标的价格在一定区间内波动
    """
    
    def __init__(self, underlying: str = "SPY", 
                 width: float = 0.05,
                 expiry_days: int = 30):
        super().__init__(underlying, expiry_days)
        self.width = width  # 行权价宽度 (5%)
        
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        # 获取当前价格
        if 'close' not in data:
            return signals
        
        current_price = data['close']
        
        # 计算波动率
        if self.engine and self.engine.data is not None:
            lookback = self.engine.data.loc[:date].tail(20)
            if len(lookback) > 10:
                returns = np.log(lookback['close'] / lookback['close'].shift(1))
                volatility = returns.std() * np.sqrt(252)
                
                # 根据波动率调整仓位
                if volatility > 0.3:  # 高波动率
                    # 宽铁鹰
                    width = self.width * 1.5
                else:
                    width = self.width
        
        # 简化: 生成卖铁鹰信号
        # 实际需要结合期权链数据
        return signals


class CoveredCallStrategy(OptionsStrategy):
    """
    备兑看涨期权策略
    
    持有标的 + 卖出看涨期权
    预期: 小幅上涨或横盘
    """
    
    def __init__(self, underlying: str = "AAPL",
                 delta_target: float = 0.3):
        super().__init__(underlying, expiry_days=30)
        self.delta_target = delta_target  # 目标 Delta
        self.last_roll_date = None
        
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data:
            return signals
        
        # 检查是否需要建仓
        if self.engine and self.engine.positions.get(self.underlying) is None:
            # 买入标的股票
            signals.append({
                'action': 'buy',
                'symbol': self.underlying,
                'quantity': 100  # 1手
            })
            
            # 卖出备兑看涨期权
            signals.append({
                'action': 'sell',
                'symbol': f"{self.underlying}_CALL",
                'quantity': 1
            })
        
        # 检查是否需要到期滚动
        if self.last_roll_date:
            days_since_roll = (date - self.last_roll_date).days
            if days_since_roll >= self.expiry_days - 5:
                # 滚动到下一期
                signals.append({
                    'action': 'roll',
                    'symbol': self.underlying
                })
                self.last_roll_date = date
        
        return signals


class ProtectivePutStrategy(OptionsStrategy):
    """
    保护性看跌期权策略
    
    持有标的 + 买入看跌期权
    预期: 下跌保护
    """
    
    def __init__(self, underlying: str = "AAPL",
                 put_strike_pct: float = 0.95):
        super().__init__(underlying, expiry_days=30)
        self.put_strike_pct = put_strike_pct  # 看跌期权行权价比例
        
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data:
            return signals
        
        # 检查是否需要建仓
        if self.engine and self.engine.positions.get(self.underlying) is None:
            # 买入标的
            signals.append({
                'action': 'buy',
                'symbol': self.underlying,
                'quantity': 100
            })
            
            # 买入保护性看跌
            strike = data['close'] * self.put_strike_pct
            signals.append({
                'action': 'buy',
                'symbol': f"{self.underlying}_PUT_{strike:.0f}",
                'quantity': 1
            })
        
        return signals


class StraddleStrategy(OptionsStrategy):
    """
    跨式策略 (Straddle)
    
    同时买入看涨和看跌期权
    预期: 大幅波动 (突破)
    """
    
    def __init__(self, underlying: str = "NVDA",
                 expiry_days: int = 30,
                 iv_threshold: float = 0.25):
        super().__init__(underlying, expiry_days)
        self.iv_threshold = iv_threshold  # 隐含波动率阈值
        
    def on_bar(self, data, date) -> List[Dict]:
        signals = []
        
        if 'close' not in data or not self.engine:
            return signals
        
        # 计算历史波动率
        lookback = self.engine.data.loc[:date].tail(20)
        if len(lookback) < 10:
            return signals
        
        returns = np.log(lookback['close'] / lookback['close'].shift(1))
        historical_vol = returns.std() * np.sqrt(252)
        
        # 波动率突破时买入跨式
        if historical_vol > self.iv_threshold:
            # 检查是否已持仓
            if not self.engine.positions:
                signals.append({
                    'action': 'buy',
                    'symbol': f"{self.underlying}_CALL",
                    'quantity': 1
                })
                signals.append({
                    'action': 'buy',
                    'symbol': f"{self.underlying}_PUT",
                    'quantity': 1
                })
        
        return signals


# 策略工厂
def create_strategy(strategy_name: str, **kwargs) -> BaseStrategy:
    """创建策略实例"""
    strategies = {
        'iron_condor': IronCondorStrategy,
        'covered_call': CoveredCallStrategy,
        'protective_put': ProtectivePutStrategy,
        'straddle': StraddleStrategy,
    }
    
    strategy_class = strategies.get(strategy_name.lower())
    if strategy_class:
        return strategy_class(**kwargs)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


if __name__ == "__main__":
    # 测试
    strategy = IronCondorStrategy(underlying="SPY")
    print(f"策略: {strategy.__class__.__name__}")
    print(f"标的: {strategy.underlying}")
    print(f"到期天数: {strategy.expiry_days}")
