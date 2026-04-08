"""
Webull 量化交易机器人 - 主程序入口
支持实盘和模拟盘两种模式
"""
import time
import logging
from datetime import datetime

# 尝试导入webull，模拟盘模式不需要
try:
    from config import APP_KEY, APP_SECRET
    from trading_client import WebullTrader
    from order_manager import OrderManager
    from market_data import WebullMarketData
    HAS_WEBULL = True
except ImportError:
    HAS_WEBULL = False
    APP_KEY = None
    APP_SECRET = None

from strategy import MovingAverageStrategy, RSIStrategy, BreakoutStrategy
from paper_trading import PaperTrader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuantBot:
    """量化交易机器人主类"""
    
    def __init__(self, app_key: str = None, app_secret: str = None, 
                 symbols: list = None, paper_trading: bool = True,
                 initial_cash: float = 100000.0):
        """
        初始化量化机器人
        
        Args:
            app_key: Webull App Key (实盘模式必填)
            app_secret: Webull App Secret (实盘模式必填)
            symbols: 交易标的列表
            paper_trading: 是否使用模拟盘 (默认True)
            initial_cash: 初始资金 (模拟盘模式)
        """
        self.paper_trading = paper_trading
        self.symbols = symbols or []
        
        if paper_trading:
            # 模拟盘模式
            logger.info(f"🤖 模拟盘模式启动, 初始资金: ${initial_cash:,.2f}")
            self.trader = PaperTrader(initial_cash)
            self.is_paper = True
        else:
            # 实盘模式
            logger.info("📈 实盘模式启动")
            self.trader = WebullTrader(app_key, app_secret)
            self.order_manager = OrderManager(self.trader)
            self.market_data = WebullMarketData(app_key, app_secret)
            self.trader.set_account()
            self.is_paper = False
        
        # 策略
        self.strategies = {
            'MA': MovingAverageStrategy,
            'RSI': RSIStrategy,
            'Breakout': BreakoutStrategy
        }
        
        logger.info(f"量化机器人启动, 交易标的: {symbols}")
    
    def get_quote(self, symbol: str) -> dict:
        """获取实时报价"""
        if self.is_paper:
            return self.trader.get_quote(symbol)
        else:
            return self.trader.market_data.get_realtime_quote(symbol)
    
    def get_history_bars(self, symbol: str, period: str = "D1", count: int = 100) -> dict:
        """获取历史K线"""
        if self.is_paper:
            return self.trader.get_history_bars(symbol, period, count)
        else:
            return self.trader.market_data.get_history_bars(symbol, period, count)
    
    def get_account_status(self):
        """获取账户状态"""
        if self.is_paper:
            return self.trader.get_balance()
        else:
            info = self.trader.get_account_info()
            logger.info(f"账户信息: 现金={info.get('cash_balance')}, 购买力={info.get('buy_power')}")
            return info
    
    def get_positions_summary(self):
        """获取持仓汇总"""
        if self.is_paper:
            return self.trader.get_positions()
        else:
            positions = self.trader.get_positions()
            summary = []
            if positions:
                for pos in positions:
                    summary.append({
                        'symbol': pos.get('symbol'),
                        'quantity': pos.get('position'),
                        'cost': pos.get('cost'),
                        'value': pos.get('marketValue'),
                        'profit': pos.get('unrealizedPL')
                    })
            return summary
    
    def buy(self, symbol: str, quantity: int, limit_price: float = None) -> dict:
        """买入"""
        if self.is_paper:
            if limit_price:
                return self.trader.buy_limit(symbol, quantity, limit_price)
            return self.trader.buy(symbol, quantity)
        else:
            if limit_price:
                return self.order_manager.buy_limit(symbol, quantity, limit_price)
            return self.order_manager.buy_market(symbol, quantity)
    
    def sell(self, symbol: str, quantity: int, limit_price: float = None) -> dict:
        """卖出"""
        if self.is_paper:
            if limit_price:
                return self.trader.sell_limit(symbol, quantity, limit_price)
            return self.trader.sell(symbol, quantity)
        else:
            if limit_price:
                return self.order_manager.sell_limit(symbol, quantity, limit_price)
            return self.order_manager.sell_market(symbol, quantity)
    
    def run_strategy(self, strategy_name: str, symbol: str, **kwargs):
        """运行策略"""
        strategy_class = self.strategies.get(strategy_name)
        if not strategy_class:
            logger.error(f"未知策略: {strategy_name}")
            return None
        
        # 创建策略实例
        strategy = strategy_class(symbol, **kwargs)
        
        # 传入数据客户端
        data_client = self.trader if self.is_paper else self.trader.market_data
        
        signal = strategy.generate_signal(data_client)
        logger.info(f"{symbol} - {strategy_name}策略信号: {signal}")
        return signal
    
    def execute_signal(self, symbol: str, signal: str, quantity: int = 10) -> dict:
        """执行交易信号"""
        if self.is_paper:
            return self.trader.execute_signal(symbol, signal, quantity)
        
        # 实盘模式
        if signal == 'BUY':
            buy_power = self.trader.get_buy_power()
            if buy_power and float(buy_power) > 100:
                quote = self.get_quote(symbol)
                if quote and 'data' in quote:
                    current_price = quote['data'].get('close')
                    if current_price:
                        order_id = self.order_manager.buy_limit(
                            symbol, quantity, current_price * 0.98
                        )
                        logger.info(f"买入信号执行: {symbol} x{quantity} @ {current_price*0.98}")
                        return order_id
        
        elif signal == 'SELL':
            positions = self.trader.get_positions()
            if positions:
                for pos in positions:
                    if pos.get('symbol') == symbol:
                        qty = int(pos.get('position', 0))
                        if qty > 0:
                            quote = self.get_quote(symbol)
                            if quote and 'data' in quote:
                                current_price = quote['data'].get('close')
                                if current_price:
                                    order_id = self.order_manager.sell_limit(
                                        symbol, qty, current_price * 1.02
                                    )
                                    logger.info(f"卖出信号执行: {symbol} x{qty} @ {current_price*1.02}")
                                    return order_id
        
        return None
    
    def next_day(self):
        """模拟一天过去 (仅模拟盘有效)"""
        if self.is_paper:
            self.trader.next_day()
    
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


def demo_paper_trading():
    """模拟盘演示"""
    print("=" * 50)
    print("🤖 Webull 模拟盘演示")
    print("=" * 50)
    
    # 创建模拟交易机器人
    bot = QuantBot(
        symbols=["AAPL", "TSLA", "NVDA"],
        paper_trading=True,
        initial_cash=100000.0
    )
    
    # 查看初始状态
    print("\n📊 初始账户状态:")
    print(bot.get_account_status())
    
    # 测试策略
    print("\n📈 策略信号测试:")
    for symbol in ["AAPL", "TSLA", "NVDA"]:
        signal = bot.run_strategy('MA', symbol, short_ma=5, long_ma=20)
        print(f"  {symbol}: {signal}")
    
    # 执行一些交易
    print("\n💰 执行交易:")
    
    # 买入 AAPL
    result = bot.buy("AAPL", 10)
    print(f"  买入 AAPL 10股: {result}")
    
    # 买入 TSLA
    result = bot.buy("TSLA", 5)
    print(f"  买入 TSLA 5股: {result}")
    
    # 模拟30天
    print("\n📅 模拟30天...")
    for i in range(30):
        bot.next_day()
    
    # 查看持仓
    print("\n📊 30天后持仓:")
    positions = bot.get_positions_summary()
    for pos in positions:
        print(f"  {pos}")
    
    # 查看账户
    print("\n💰 30天后账户状态:")
    print(bot.get_account_status())
    
    # 卖出部分
    print("\n🔴 卖出:")
    result = bot.sell("AAPL", 5)
    print(f"  卖出 AAPL 5股: {result}")
    
    print("\n✅ 最终账户状态:")
    print(bot.get_account_status())


def demo_live_trading():
    """实盘演示 (需要真实API)"""
    print("=" * 50)
    print("📈 Webull 实盘演示")
    print("=" * 50)
    
    # 需要真实的 API Key
    APP_KEY = "your_app_key"
    APP_SECRET = "your_app_secret"
    
    if APP_KEY == "your_app_key":
        print("⚠️ 请先在 config.py 中配置你的 API Key")
        return
    
    # 创建实盘机器人
    bot = QuantBot(
        app_key=APP_KEY,
        app_secret=APP_SECRET,
        symbols=["AAPL", "TSLA"],
        paper_trading=False
    )
    
    # 查看账户
    print("\n📊 账户状态:")
    print(bot.get_account_status())
    
    # 查看持仓
    print("\n📊 持仓:")
    print(bot.get_positions_summary())
    
    # 测试策略
    print("\n📈 策略信号:")
    for symbol in ["AAPL", "TSLA"]:
        signal = bot.run_strategy('MA', symbol, short_ma=5, long_ma=20)
        print(f"  {symbol}: {signal}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        demo_live_trading()
    else:
        demo_paper_trading()
