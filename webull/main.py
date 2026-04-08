"""
Webull 量化交易机器人 - 主程序入口
"""
import time
import logging
from datetime import datetime

from config import APP_KEY, APP_SECRET
from trading_client import WebullTrader
from order_manager import OrderManager
from market_data import WebullMarketData
from strategy import MovingAverageStrategy, RSIStrategy, BreakoutStrategy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuantBot:
    """量化交易机器人主类"""
    
    def __init__(self, app_key: str, app_secret: str, symbols: list):
        self.app_key = app_key
        self.app_secret = app_secret
        self.symbols = symbols
        
        # 初始化组件
        self.trader = WebullTrader(app_key, app_secret)
        self.order_manager = OrderManager(self.trader)
        self.market_data = WebullMarketData(app_key, app_secret)
        
        # 账户设置
        self.trader.set_account()
        
        # 策略
        self.strategies = {
            'MA': MovingAverageStrategy,
            'RSI': RSIStrategy,
            'Breakout': BreakoutStrategy
        }
        
        logger.info(f"量化机器人启动, 交易标的: {symbols}")
    
    def get_account_status(self):
        """获取账户状态"""
        info = self.trader.get_account_info()
        logger.info(f"账户信息: 现金={info.get('cash_balance')}, 购买力={info.get('buy_power')}")
        return info
    
    def get_positions_summary(self):
        """获取持仓汇总"""
        positions = self.trader.get_positions()
        
        summary = []
        if positions:
            for pos in positions:
                symbol = pos.get('symbol')
                qty = pos.get('position')
                cost = pos.get('cost')
                current_value = pos.get('marketValue')
                profit = pos.get('unrealizedPL')
                
                summary.append({
                    'symbol': symbol,
                    'quantity': qty,
                    'cost': cost,
                    'value': current_value,
                    'profit': profit
                })
        
        return summary
    
    def run_strategy(self, strategy_name: str, symbol: str, **kwargs):
        """运行策略"""
        strategy_class = self.strategies.get(strategy_name)
        if not strategy_class:
            logger.error(f"未知策略: {strategy_name}")
            return None
        
        strategy = strategy_class(symbol, **kwargs)
        signal = strategy.generate_signal()
        
        logger.info(f"{symbol} - {strategy_name}策略信号: {signal}")
        return signal
    
    def execute_signal(self, symbol: str, signal: str, quantity: int = 10):
        """执行交易信号"""
        if signal == 'BUY':
            # 检查购买力
            buy_power = self.trader.get_buy_power()
            if buy_power and float(buy_power) > 100:
                # 获取当前价格
                quote = self.market_data.get_realtime_quote(symbol)
                if quote and 'data' in quote:
                    current_price = quote['data'].get('close')
                    if current_price:
                        order_id = self.order_manager.buy_limit(
                            symbol, quantity, current_price * 0.98  # 98%市价
                        )
                        logger.info(f"买入信号执行: {symbol} x{quantity} @ {current_price*0.98}, 订单ID: {order_id}")
                        return order_id
        
        elif signal == 'SELL':
            # 检查持仓
            positions = self.trader.get_positions()
            if positions:
                for pos in positions:
                    if pos.get('symbol') == symbol:
                        qty = int(pos.get('position', 0))
                        if qty > 0:
                            quote = self.market_data.get_realtime_quote(symbol)
                            if quote and 'data' in quote:
                                current_price = quote['data'].get('close')
                                if current_price:
                                    order_id = self.order_manager.sell_limit(
                                        symbol, qty, current_price * 1.02  # 102%市价
                                    )
                                    logger.info(f"卖出信号执行: {symbol} x{qty} @ {current_price*1.02}, 订单ID: {order_id}")
                                    return order_id
        
        return None
    
    def run(self, strategy_name: str = 'MA', interval: int = 60, **strategy_kwargs):
        """
        运行机器人
        
        Args:
            strategy_name: 策略名称
            interval: 运行间隔(秒)
            **strategy_kwargs: 策略参数
        """
        logger.info(f"开始运行策略: {strategy_name}")
        
        try:
            while True:
                # 获取账户状态
                self.get_account_status()
                
                # 遍历所有标的
                for symbol in self.symbols:
                    # 获取信号
                    signal = self.run_strategy(strategy_name, symbol, **strategy_kwargs)
                    
                    # 执行信号
                    if signal in ['BUY', 'SELL']:
                        self.execute_signal(symbol, signal)
                
                # 等待下一个周期
                logger.info(f"等待 {interval} 秒...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("机器人停止")
        except Exception as e:
            logger.error(f"运行错误: {e}")


def demo():
    """演示模式"""
    # 配置你的API密钥
    APP_KEY = "your_app_key"
    APP_SECRET = "your_app_secret"
    
    # 交易标的
    symbols = ["AAPL", "TSLA", "NVDA"]
    
    # 创建机器人
    bot = QuantBot(APP_KEY, APP_SECRET, symbols)
    
    # 获取账户状态
    bot.get_account_status()
    
    # 获取持仓
    positions = bot.get_positions_summary()
    print("当前持仓:", positions)
    
    # 测试策略
    for symbol in symbols:
        signal = bot.run_strategy('MA', symbol, short_ma=5, long_ma=20)
        print(f"{symbol} MA策略信号: {signal}")
        
        signal = bot.run_strategy('RSI', symbol)
        print(f"{symbol} RSI策略信号: {signal}")


if __name__ == "__main__":
    demo()
