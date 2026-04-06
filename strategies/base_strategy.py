"""
基础策略类
"""
from typing import List, Dict
from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    """所有策略的基类"""
    
    def __init__(self):
        self.engine = None
        self.indicators = {}
    
    def set_engine(self, engine):
        """设置回测引擎"""
        self.engine = engine
    
    def on_init(self):
        """策略初始化 - 在回测开始前调用"""
        pass
    
    @abstractmethod
    def on_bar(self, data, date) -> List[Dict]:
        """
        每根K线调用一次
        
        Args:
            data: 当前K线数据 (pd.Series)
            date: 当前日期
        
        Returns:
            信号列表 [{"action": "buy/sell", "symbol": "...", "quantity": ...}]
        """
        pass
    
    def on_finish(self):
        """策略结束 - 回测完成后调用"""
        pass
    
    def get_indicator(self, name: str) -> pd.Series:
        """获取指标缓存"""
        return self.indicators.get(name, pd.Series())
    
    def set_indicator(self, name: str, value: pd.Series):
        """设置指标缓存"""
        self.indicators[name] = value
    
    @property
    def name(self) -> str:
        """策略名称"""
        return self.__class__.__name__
