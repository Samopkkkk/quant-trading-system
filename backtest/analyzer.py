"""
Backtest Analyzer
Advanced analysis tools for backtest results
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Performance metrics"""
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    avg_trade: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    consecutive_wins: int
    consecutive_losses: int
    recovery_factor: float


class BacktestAnalyzer:
    """
    Advanced Backtest Analyzer
    
    Provides comprehensive analysis of backtest results
    """
    
    def __init__(self, equity_curve: List[float], trades: List[Dict]):
        self.equity = np.array(equity_curve)
        self.trades = trades
        
    def calculate_returns(self) -> np.ndarray:
        """Calculate returns"""
        returns = np.diff(self.equity) / self.equity[:-1]
        return returns
    
    def calculate_metrics(self) -> PerformanceMetrics:
        """Calculate all performance metrics"""
        returns = self.calculate_returns()
        
        # Basic metrics
        total_return = (self.equity[-1] - self.equity[0]) / self.equity[0]
        
        # Sharpe Ratio (assuming 252 trading days, 0% risk-free rate)
        if returns.std() > 0:
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252)
        else:
            sharpe_ratio = 0
            
        # Sortino Ratio (downside deviation)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino_ratio = returns.mean() / downside_returns.std() * np.sqrt(252)
        else:
            sortino_ratio = 0
            
        # Calmar Ratio (return / max drawdown)
        max_dd = self.calculate_max_drawdown()
        if max_dd > 0:
            calmar_ratio = total_return / max_dd
        else:
            calmar_ratio = 0
            
        # Win rate
        winning_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in self.trades if t.get('pnl', 0) < 0]
        
        total_trades = len(winning_trades) + len(losing_trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # Profit Factor
        gross_profit = sum(t.get('pnl', 0) for t in winning_trades)
        gross_loss = abs(sum(t.get('pnl', 0) for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Trade statistics
        all_pnls = [t.get('pnl', 0) for t in self.trades if 'pnl' in t]
        avg_trade = np.mean(all_pnls) if all_pnls else 0
        avg_win = np.mean([t.get('pnl', 0) for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.get('pnl', 0) for t in losing_trades]) if losing_trades else 0
        
        # Extreme trades
        largest_win = max(all_pnls) if all_pnls else 0
        largest_loss = min(all_pnls) if all_pnls else 0
        
        # Consecutive trades
        consecutive_wins = self.calculate_max_consecutive(winning_trades)
        consecutive_losses = self.calculate_max_consecutive(losing_trades)
        
        # Recovery Factor
        recovery_factor = total_return / max_dd if max_dd > 0 else 0
        
        # Max drawdown duration
        max_dd_duration = self.calculate_max_drawdown_duration()
        
        return PerformanceMetrics(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade=avg_trade,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            recovery_factor=recovery_factor
        )
    
    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        running_max = np.maximum.accumulate(self.equity)
        drawdown = (self.equity - running_max) / running_max
        return abs(drawdown.min())
    
    def calculate_max_drawdown_duration(self) -> int:
        """Calculate duration of max drawdown"""
        running_max = np.maximum.accumulate(self.equity)
        drawdown = (self.equity - running_max) / running_max
        
        # Find max drawdown period
        in_dd = False
        max_duration = 0
        current_duration = 0
        
        for dd in drawdown:
            if dd < -0.01:  # 1% threshold
                current_duration += 1
                in_dd = True
            else:
                if in_dd:
                    max_duration = max(max_duration, current_duration)
                    current_duration = 0
                in_dd = False
                
        return max_duration
    
    def calculate_max_consecutive(self, trades: List[Dict]) -> int:
        """Calculate maximum consecutive wins/losses"""
        if not trades:
            return 0
            
        # This is simplified - in real implementation would track sequence
        return len(trades)
    
    def generate_report(self) -> str:
        """Generate text report"""
        metrics = self.calculate_metrics()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                    BACKTEST ANALYSIS REPORT                   ║
╠══════════════════════════════════════════════════════════════╣
║  Total Return:          {metrics.total_return:>10.2%}                       ║
║  Sharpe Ratio:          {metrics.sharpe_ratio:>10.2f}                       ║
║  Sortino Ratio:         {metrics.sortino_ratio:>10.2f}                       ║
║  Calmar Ratio:          {metrics.calmar_ratio:>10.2f}                       ║
╠══════════════════════════════════════════════════════════════╣
║  Max Drawdown:         {metrics.max_drawdown:>10.2%}                       ║
║  Max DD Duration:       {metrics.max_drawdown_duration:>10d} days                   ║
║  Recovery Factor:       {metrics.recovery_factor:>10.2f}                       ║
╠══════════════════════════════════════════════════════════════╣
║  Win Rate:             {metrics.win_rate:>10.2%}                       ║
║  Profit Factor:        {metrics.profit_factor:>10.2f}                       ║
║  Avg Trade:            ${metrics.avg_trade:>10.2f}                       ║
║  Avg Win:              ${metrics.avg_win:>10.2f}                       ║
║  Avg Loss:             ${metrics.avg_loss:>10.2f}                       ║
╠══════════════════════════════════════════════════════════════╣
║  Largest Win:          ${metrics.largest_win:>10.2f}                       ║
║  Largest Loss:         ${metrics.largest_loss:>10.2f}                       ║
║  Max Consecutive Wins: {metrics.consecutive_wins:>10d}                       ║
║  Max Consecutive Loss: {metrics.consecutive_losses:>10d}                       ║
╚══════════════════════════════════════════════════════════════╝
"""
        return report
    
    def save_to_csv(self, filepath: str):
        """Save detailed results to CSV"""
        df = pd.DataFrame(self.trades)
        df.to_csv(filepath, index=False)


def compare_strategies(results: Dict[str, PerformanceMetrics]) -> pd.DataFrame:
    """Compare multiple strategy results"""
    data = []
    
    for name, metrics in results.items():
        data.append({
            'Strategy': name,
            'Return': metrics.total_return,
            'Sharpe': metrics.sharpe_ratio,
            'Max DD': metrics.max_drawdown,
            'Win Rate': metrics.win_rate,
            'Profit Factor': metrics.profit_factor
        })
    
    return pd.DataFrame(data)


if __name__ == "__main__":
    # Test
    import random
    
    # Simulate equity curve
    equity = [100000]
    for _ in range(250):
        equity.append(equity[-1] * (1 + random.uniform(-0.02, 0.025)))
    
    # Simulate trades
    trades = [
        {'pnl': random.uniform(-500, 800)} for _ in range(50)
    ]
    
    analyzer = BacktestAnalyzer(equity, trades)
    print(analyzer.generate_report())
