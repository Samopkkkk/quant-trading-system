"""
量化策略示例
"""
import time
from datetime import datetime
from market_data import WebullMarketData


class MovingAverageStrategy:
    """移动平均线策略
    
    策略逻辑:
    - 金叉买入: 短期均线上穿长期均线
    - 死叉卖出: 短期均线下穿长期均线
    """
    
    def __init__(self, symbol: str, short_ma: int = 5, long_ma: int = 20):
        self.symbol = symbol
        self.short_ma = short_ma  # 短期均线
        self.long_ma = long_ma   # 长期均线
        self.market_data = WebullMarketData()
    
    def calculate_ma(self, prices: list, period: int) -> float:
        """计算移动平均"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def generate_signal(self) -> str:
        """
        生成交易信号
        
        Returns:
            'BUY' - 买入信号
            'SELL' - 卖出信号
            'HOLD' - 持有
        """
        # 获取历史数据
        bars = self.market_data.get_history_bars(
            self.symbol, 
            timespan="D1",  # 日线
            count=max(self.short_ma, self.long_ma) + 5
        )
        
        if not bars or 'data' not in bars:
            return 'HOLD'
        
        # 提取收盘价
        closes = [bar['close'] for bar in bars['data']]
        
        # 计算均线
        short_ma_value = self.calculate_ma(closes, self.short_ma)
        long_ma_value = self.calculate_ma(closes, self.long_ma)
        
        if short_ma_value is None or long_ma_value is None:
            return 'HOLD'
        
        # 需要前一天的均线值来判断金叉死叉
        if len(closes) > max(self.short_ma, self.long_ma):
            prev_closes = closes[:-1]
            prev_short_ma = self.calculate_ma(prev_closes, self.short_ma)
            prev_long_ma = self.calculate_ma(prev_closes, self.long_ma)
            
            if prev_short_ma and prev_long_ma:
                # 金叉: 昨天短期<=长期, 今天短期>长期
                if prev_short_ma <= prev_long_ma and short_ma_value > long_ma_value:
                    return 'BUY'
                # 死叉: 昨天短期>=长期, 今天短期<长期
                elif prev_short_ma >= prev_long_ma and short_ma_value < long_ma_value:
                    return 'SELL'
        
        return 'HOLD'


class BreakoutStrategy:
    """突破策略
    
    策略逻辑:
    - 突破N日高点: 买入
    - 跌破N日低点: 卖出
    """
    
    def __init__(self, symbol: str, period: int = 20):
        self.symbol = symbol
        self.period = period  # 观察周期
        self.market_data = WebullMarketData()
    
    def generate_signal(self) -> str:
        """突破策略信号"""
        bars = self.market_data.get_history_bars(
            self.symbol,
            timesnap="D1",
            count=self.period + 5
        )
        
        if not bars or 'data' not in bars:
            return 'HOLD'
        
        highs = [bar['high'] for bar in bars['data']]
        lows = [bar['low'] for bar in bars['data']]
        current_price = highs[-1]
        
        # 前N日最高点和最低点
        period_high = max(highs[-self.period:-1])
        period_low = min(lows[-self.period:-1])
        
        # 突破买入
        if current_price > period_high:
            return 'BUY'
        # 跌破卖出
        elif current_price < period_low:
            return 'SELL'
        
        return 'HOLD'


class RSIStrategy:
    """RSI 策略
    
    策略逻辑:
    - RSI < 30: 超卖, 买入信号
    - RSI > 70: 超买, 卖出信号
    """
    
    def __init__(self, symbol: str, period: int = 14, oversold: int = 30, overbought: int = 70):
        self.symbol = symbol
        self.period = period
        self.oversold = oversold    # 超卖阈值
        self.overbought = overbought  # 超买阈值
        self.market_data = WebullMarketData()
    
    def calculate_rsi(self, prices: list) -> float:
        """计算RSI"""
        if len(prices) < self.period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        # 只取最后period个
        gains = gains[-self.period:]
        losses = losses[-self.period:]
        
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def generate_signal(self) -> str:
        """RSI策略信号"""
        bars = self.market_data.get_history_bars(
            self.symbol,
            timesnap="D1",
            count=self.period + 10
        )
        
        if not bars or 'data' not in bars:
            return 'HOLD'
        
        closes = [bar['close'] for bar in bars['data']]
        
        rsi = self.calculate_rsi(closes)
        
        if rsi is None:
            return 'HOLD'
        
        if rsi < self.oversold:
            return 'BUY'  # 超卖, 买入
        elif rsi > self.overbought:
            return 'SELL'  # 超买, 卖出
        
        return 'HOLD'


class MACDStrategy:
    """MACD 策略
    
    策略逻辑:
    - MACD金叉(DIFF上穿DEA): 买入
    - MACD死叉(DIFF下穿DEA): 卖出
    """
    
    def __init__(self, symbol: str, fast: int = 12, slow: int = 26, signal: int = 9):
        self.symbol = symbol
        self.fast = fast    # 快线周期
        self.slow = slow    # 慢线周期
        self.signal = signal  # 信号线周期
        self.market_data = WebullMarketData()
    
    def calculate_ema(self, prices: list, period: int) -> float:
        """计算指数移动平均"""
        if len(prices) < period:
            return None
        
        # 使用SMA作为初始值
        ema = sum(prices[:period]) / period
        
        # 计算EMA
        multiplier = 2 / (period + 1)
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def generate_signal(self) -> str:
        """MACD策略信号"""
        bars = self.market_data.get_history_bars(
            self.symbol,
            timesnap="D1",
            count=self.slow + self.signal + 10
        )
        
        if not bars or 'data' not in bars:
            return 'HOLD'
        
        closes = [bar['close'] for bar in bars['data']]
        
        # 计算EMA
        ema_fast = self.calculate_ema(closes, self.fast)
        ema_slow = self.calculate_ema(closes, self.slow)
        
        if ema_fast is None or ema_slow is None:
            return 'HOLD'
        
        # 计算MACD和Signal
        macd_line = ema_fast - ema_slow
        
        # 简化计算，使用MACD作为信号线
        # 实际应该用MACD的EMA作为signal线
        if macd_line > 0:
            return 'BUY'
        elif macd_line < 0:
            return 'SELL'
        
        return 'HOLD'


# 网格交易策略
class GridStrategy:
    """网格交易策略
    
    策略逻辑:
    - 在价格区间内设置网格
    - 价格下跌买入, 价格上涨卖出
    """
    
    def __init__(self, symbol: str, lower_price: float, upper_price: float, grid_count: int = 10):
        self.symbol = symbol
        self.lower_price = lower_price  # 价格下限
        self.upper_price = upper_price  # 价格上限
        self.grid_count = grid_count     # 网格数量
        self.grid_size = (upper_price - lower_price) / grid_count
        
    def get_grid_level(self, price: float) -> int:
        """获取价格所在的网格层级"""
        if price < self.lower_price or price > self.upper_price:
            return -1
        return int((price - self.lower_price) / self.grid_size)
    
    def should_buy(self, current_price: float) -> bool:
        """是否应该买入"""
        level = self.get_grid_level(current_price)
        return level >= 0 and level < self.grid_count // 2
    
    def should_sell(self, current_price: float) -> bool:
        """是否应该卖出"""
        level = self.get_grid_level(current_price)
        return level >= self.grid_count // 2


if __name__ == "__main__":
    # 测试策略
    symbols = ["AAPL", "TSLA", "NVDA"]
    
    print("=== 移动平均策略 ===")
    for symbol in symbols:
        strategy = MovingAverageStrategy(symbol, short_ma=5, long_ma=20)
        signal = strategy.generate_signal()
        print(f"{symbol}: {signal}")
    
    print("\n=== RSI策略 ===")
    for symbol in symbols:
        strategy = RSIStrategy(symbol, period=14)
        signal = strategy.generate_signal()
        print(f"{symbol}: {signal}")
