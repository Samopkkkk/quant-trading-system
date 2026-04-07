"""
回测引擎核心
"""
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from copy import deepcopy
import config


@dataclass
class Trade:
    """交易记录"""
    date: str
    symbol: str
    action: str  # buy/sell
    quantity: int
    price: float
    commission: float = 0.0
    pnl: float = 0.0  # 盈亏


@dataclass
class Position:
    """持仓"""
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    
    def update_price(self, price: float):
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.quantity


@dataclass
class BacktestResult:
    """回测结果"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_commission: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    # 资金曲线
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    
    def calculate(self):
        if self.total_trades > 0:
            self.win_rate = self.winning_trades / self.total_trades
            if self.winning_trades > 0:
                self.avg_win = self.total_pnl / self.winning_trades
            if self.losing_trades > 0:
                self.avg_loss = abs(self.total_pnl / self.losing_trades)


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_capital: float = None, 
                 commission: float = None):
        self.initial_capital = initial_capital or config.INITIAL_CAPITAL
        self.commission = commission or config.WEBULL_COMMISSION
        self.slippage = config.SLIPPAGE
        
        self.capital = self.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve = [self.initial_capital]
        
        # 数据
        self.data: pd.DataFrame = None
        self.current_idx = 0
        
        # 策略
        self.strategy = None
        
        # 指标缓存
        self.indicators = {}
    
    def load_data(self, symbol: str, start_date: str, end_date: str,
                  source: str = "webull"):
        """
        加载历史数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            source: 数据源
        """
        if source == "webull":
            from data.webull_client import WebullClient
            client = WebullClient()
            client.login()
            data = client.get_historical_data(symbol)
            
            if data:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['time'], unit='ms')
                df = df.set_index('date')
                df = df[(df.index >= start_date) & (df.index <= end_date)]
                self.data = df
                return
        
        # 尝试从CSV加载
        csv_path = f"data/historical/{symbol}_{start_date}_{end_date}.csv"
        try:
            self.data = pd.read_csv(csv_path, parse_dates=['date'], index_col='date')
        except:
            print(f"无法加载 {symbol} 数据，请先获取历史数据")
    
    def load_dataframe(self, df: pd.DataFrame):
        """直接加载 DataFrame"""
        self.data = df.copy()
    
    def set_strategy(self, strategy):
        """设置策略"""
        self.strategy = strategy
        strategy.set_engine(self)
    
    def run_strategy(self, strategy = None):
        """运行回测"""
        if strategy:
            self.set_strategy(strategy)
        
        if not self.strategy:
            print("请先设置策略")
            return
        
        if self.data is None or len(self.data) == 0:
            print("请先加载数据")
            return
        
        # 初始化
        self.strategy.on_init()
        
        # 逐日回测
        for self.current_idx in range(len(self.data)):
            current_date = self.data.index[self.current_idx]
            current_data = self.data.iloc[self.current_idx]
            
            # 更新持仓估值
            self._update_positions(current_data)
            
            # 策略信号
            signals = self.strategy.on_bar(current_data, current_date)
            
            # 执行交易
            if signals:
                for signal in signals:
                    self._execute_signal(signal, current_data)
            
            # 记录权益
            self.equity_curve.append(self._get_total_value(current_data))
        
        # 结束
        self.strategy.on_finish()
    
    def _update_positions(self, current_data: pd.Series):
        """更新持仓估值"""
        for symbol, pos in self.positions.items():
            if 'close' in current_data:
                pos.update_price(current_data['close'])
    
    def _get_total_value(self, current_data: pd.Series) -> float:
        """计算总权益"""
        position_value = sum(
            pos.quantity * pos.current_price 
            for pos in self.positions.values()
        )
        return self.capital + position_value
    
    def _execute_signal(self, signal: Dict, data: pd.Series):
        """执行交易信号"""
        symbol = signal.get('symbol')
        action = signal.get('action')  # buy/sell
        quantity = signal.get('quantity', 1)
        price = data.get('close', 0) * (1 + self.slippage if action == 'buy' else 1 - self.slippage)
        
        cost = price * quantity
        
        if action == 'buy' and self.capital >= cost + self.commission:
            # 买入
            self.capital -= (cost + self.commission)
            
            if symbol in self.positions:
                pos = self.positions[symbol]
                # 计算新的平均成本
                total_cost = pos.entry_price * pos.quantity + price * quantity
                pos.quantity += quantity
                pos.entry_price = total_cost / pos.quantity
                pos.current_price = price
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=price,
                    current_price=price
                )
            
            self.trades.append(Trade(
                date=str(data.name)[:10],
                symbol=symbol,
                action='buy',
                quantity=quantity,
                price=price,
                commission=self.commission
            ))
            
        elif action == 'sell' and symbol in self.positions:
            pos = self.positions[symbol]
            sell_qty = min(quantity, pos.quantity)
            
            # 卖出
            proceeds = price * sell_qty - self.commission
            self.capital += proceeds
            
            pnl = (price - pos.entry_price) * sell_qty
            pos.quantity -= sell_qty
            
            if pos.quantity <= 0:
                del self.positions[symbol]
            
            self.trades.append(Trade(
                date=str(data.name)[:10],
                symbol=symbol,
                action='sell',
                quantity=sell_qty,
                price=price,
                commission=self.commission,
                pnl=pnl
            ))
    
    def get_results(self) -> BacktestResult:
        """获取回测结果"""
        result = BacktestResult()
        result.total_trades = len([t for t in self.trades if t.action == 'sell'])
        result.trades = self.trades
        result.equity_curve = self.equity_curve
        
        pnl_list = [t.pnl for t in self.trades if t.pnl != 0]
        
        for t in self.trades:
            result.total_commission += t.commission
        
        for pnl in pnl_list:
            if pnl > 0:
                result.winning_trades += 1
                result.total_pnl += pnl
            elif pnl < 0:
                result.losing_trades += 1
                result.total_pnl += pnl
        
        # 计算最大回撤
        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        result.max_drawdown = abs(drawdown.min())
        
        # 计算夏普比率
        if len(pnl_list) > 1:
            returns = np.diff(equity) / equity[:-1]
            result.sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        result.calculate()
        return result
    
    def print_results(self):
        """打印回测结果"""
        result = self.get_results()
        
        print("=" * 50)
        print("回测结果")
        print("=" * 50)
        print(f"总交易次数: {result.total_trades}")
        print(f"盈利交易: {result.winning_trades}")
        print(f"亏损交易: {result.losing_trades}")
        print(f"胜率: {result.win_rate:.2%}")
        print(f"总盈亏: ${result.total_pnl:.2f}")
        print(f"总手续费: ${result.total_commission:.2f}")
        print(f"最大回撤: {result.max_drawdown:.2%}")
        print(f"夏普比率: {result.sharpe_ratio:.2f}")
        print(f"平均盈利: ${result.avg_win:.2f}")
        print(f"平均亏损: ${result.avg_loss:.2f}")
        print(f"最终权益: ${self.equity_curve[-1]:.2f}")
        print("=" * 50)
    
    def plot_equity(self):
        """绘制权益曲线"""
        try:
            import matplotlib.pyplot as plt
            
            result = self.get_results()
            plt.figure(figsize=(12, 6))
            plt.plot(result.equity_curve)
            plt.title('Equity Curve')
            plt.xlabel('Days')
            plt.ylabel('Capital ($)')
            plt.grid(True)
            plt.show()
        except ImportError:
            print("需要安装 matplotlib 才能绘图")


# 便捷函数
def run_backtest(data: pd.DataFrame, strategy, 
                initial_capital: float = 100000) -> BacktestResult:
    """快速回测函数"""
    engine = BacktestEngine(initial_capital=initial_capital)
    engine.load_dataframe(data)
    engine.run_strategy(strategy)
    return engine.get_results()
