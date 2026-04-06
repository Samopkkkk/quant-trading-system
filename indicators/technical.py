"""
技术指标库
"""
import pandas as pd
import numpy as np
from typing import Union


def SMA(data: pd.Series, period: int) -> pd.Series:
    """简单移动平均 (Simple Moving Average)"""
    return data.rolling(window=period).mean()


def EMA(data: pd.Series, period: int) -> pd.Series:
    """指数移动平均 (Exponential Moving Average)"""
    return data.ewm(span=period, adjust=False).mean()


def RSI(data: pd.Series, period: int = 14) -> pd.Series:
    """相对强弱指标 (Relative Strength Index)"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def MACD(data: pd.Series, fast: int = 12, slow: int = 26, 
         signal: int = 9) -> pd.DataFrame:
    """
    MACD 指标
    
    Returns:
        pd.DataFrame with columns: macd, signal, histogram
    """
    ema_fast = EMA(data, fast)
    ema_slow = EMA(data, slow)
    
    macd = ema_fast - ema_slow
    signal_line = EMA(macd, signal)
    histogram = macd - signal_line
    
    return pd.DataFrame({
        'macd': macd,
        'signal': signal_line,
        'histogram': histogram
    })


def BollingerBands(data: pd.Series, period: int = 20, 
                   std_dev: float = 2.0) -> pd.DataFrame:
    """布林带 (Bollinger Bands)"""
    sma = SMA(data, period)
    std = data.rolling(window=period).std()
    
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    return pd.DataFrame({
        'middle': sma,
        'upper': upper,
        'lower': lower
    })


def ATR(high: pd.Series, low: pd.Series, close: pd.Series, 
        period: int = 14) -> pd.Series:
    """平均真实波幅 (Average True Range)"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr


def Stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
               k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """随机指标 (Stochastic Oscillator)"""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(window=d_period).mean()
    
    return pd.DataFrame({
        'k': k,
        'd': d
    })


def ADX(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14) -> pd.Series:
    """平均趋向指数 (Average Directional Index)"""
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr = ATR(high, low, close, period=1)
    
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / tr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / tr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx


def OBV(close: pd.Series, volume: pd.Series) -> pd.Series:
    """能量潮 (On-Balance Volume)"""
    obv = pd.Series(index=close.index, dtype=float)
    obv.iloc[0] = volume.iloc[0]
    
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
        elif close.iloc[i] < close.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
    
    return obv


def VWAP(high: pd.Series, low: pd.Series, close: pd.Series,
         volume: pd.Series) -> pd.Series:
    """成交量加权平均价 (Volume Weighted Average Price)"""
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()
    return vwap


def Keltner(high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = 20, multiplier: float = 2.0) -> pd.DataFrame:
    """肯特纳通道 (Keltner Channels)"""
    ema = EMA(close, period)
    atr = ATR(high, low, close, period)
    
    upper = ema + (multiplier * atr)
    lower = ema - (multiplier * atr)
    
    return pd.DataFrame({
        'middle': ema,
        'upper': upper,
        'lower': lower
    })


def Ichimoku(high: pd.Series, low: pd.Series, close: pd.Series,
             conversion: int = 9, base: int = 26, 
             span_b: int = 52, displacement: int = 26) -> pd.DataFrame:
    """一目均衡表 (Ichimoku Cloud)"""
    # 转换线
    conversion_line = (high.rolling(window=conversion).max() + 
                       low.rolling(window=conversion).min()) / 2
    
    # 基准线
    base_line = (high.rolling(window=base).max() + 
                 low.rolling(window=base).min()) / 2
    
    # 先行带 A
    span_a = ((conversion_line + base_line) / 2).shift(displacement)
    
    # 先行带 B
    span_b_line = ((high.rolling(window=span_b).max() + 
                   low.rolling(window=span_b).min()) / 2).shift(displacement)
    
    return pd.DataFrame({
        'conversion': conversion_line,
        'base': base_line,
        'span_a': span_a,
        'span_b': span_b_line
    })


def calculate_all(data: pd.DataFrame) -> dict:
    """计算所有常用指标"""
    results = {}
    
    if 'close' in data.columns:
        results['sma_20'] = SMA(data['close'], 20)
        results['sma_50'] = SMA(data['close'], 50)
        results['sma_200'] = SMA(data['close'], 200)
        results['ema_12'] = EMA(data['close'], 12)
        results['ema_26'] = EMA(data['close'], 26)
        results['rsi'] = RSI(data['close'])
        results['macd'] = MACD(data['close'])
        results['bb'] = BollingerBands(data['close'])
    
    if all(col in data.columns for col in ['high', 'low', 'close']):
        results['atr'] = ATR(data['high'], data['low'], data['close'])
        results['stoch'] = Stochastic(data['high'], data['low'], data['close'])
        results['adx'] = ADX(data['high'], data['low'], data['close'])
    
    if 'volume' in data.columns and 'close' in data.columns:
        results['obv'] = OBV(data['close'], data['volume'])
    
    return results


if __name__ == "__main__":
    # 测试
    import numpy as np
    
    # 生成测试数据
    dates = pd.date_range("2024-01-01", periods=100)
    close = pd.Series(100 + np.cumsum(np.random.randn(100)), index=dates)
    
    print("SMA(20):", SMA(close, 20).tail())
    print("\nRSI:", RSI(close).tail())
    print("\nMACD:", MACD(close).tail())
