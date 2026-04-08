"""
Webull 模拟交易盘
用于测试和回测，无需真实API key
"""
import random
import time
from datetime import datetime
from collections import defaultdict


class SimulatedMarket:
    """模拟市场环境"""
    
    def __init__(self, initial_prices: dict = None):
        """
        Args:
            initial_prices: 初始价格 {"AAPL": 150.0, "TSLA": 200.0, ...}
        """
        self.prices = initial_prices or {
            "AAPL": 175.0,
            "TSLA": 250.0,
            "NVDA": 450.0,
            "GOOGL": 140.0,
            "MSFT": 350.0,
            "AMZN": 175.0,
            "META": 380.0,
        }
        self.price_history = {symbol: [price] for symbol, price in self.prices.items()}
        self.volatility = 0.02  # 2% 价格波动
        
    def update_prices(self):
        """模拟价格波动"""
        for symbol in self.prices:
            change = random.uniform(-self.volatility, self.volatility)
            self.prices[symbol] *= (1 + change)
            self.price_history[symbol].append(self.prices[symbol])
    
    def get_price(self, symbol: str) -> float:
        """获取当前价格"""
        return self.prices.get(symbol, 100.0)
    
    def get_history(self, symbol: str, count: int = 100) -> list:
        """获取历史价格"""
        history = self.price_history.get(symbol, [])
        return history[-count:]
    
    def generate_klines(self, symbol: str, period: str = "D1", count: int = 100) -> list:
        """生成K线数据"""
        history = self.get_history(symbol, count)
        klines = []
        
        for i, close in enumerate(history):
            open_price = history[i-1] if i > 0 else close
            high = max(open_price, close) * random.uniform(1.0, 1.02)
            low = min(open_price, close) * random.uniform(0.98, 1.0)
            volume = random.randint(1000000, 10000000)
            
            klines.append({
                "time": int(time.time()) - (count - i) * 86400,
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": volume
            })
        
        return klines
    
    def add_symbol(self, symbol: str, price: float):
        """添加交易标的"""
        self.prices[symbol] = price
        self.price_history[symbol] = [price]


class SimulatedAccount:
    """模拟账户"""
    
    def __init__(self, initial_cash: float = 100000.0):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions = defaultdict(int)  # symbol -> quantity
        self.position_cost = defaultdict(float)  # symbol -> cost basis
        self.order_history = []
        self.trade_history = []
        
    def buy(self, symbol: str, quantity: int, price: float) -> dict:
        """买入"""
        total_cost = quantity * price * 1.001  # 0.1% 手续费
        
        if self.cash < total_cost:
            return {"success": False, "reason": "insufficient_cash"}
        
        self.cash -= total_cost
        self.positions[symbol] += quantity
        self.position_cost[symbol] = (self.position_cost[symbol] * (self.positions[symbol] - quantity) + 
                                       quantity * price) / self.positions[symbol] if self.positions[symbol] > 0 else 0
        
        order = {
            "id": len(self.order_history) + 1,
            "symbol": symbol,
            "side": "BUY",
            "quantity": quantity,
            "price": price,
            "status": "FILLED",
            "timestamp": datetime.now().isoformat()
        }
        self.order_history.append(order)
        self.trade_history.append(order)
        
        return {"success": True, "order": order}
    
    def sell(self, symbol: str, quantity: int, price: float) -> dict:
        """卖出"""
        if self.positions[symbol] < quantity:
            return {"success": False, "reason": "insufficient_position"}
        
        self.cash += quantity * price * 0.999  # 0.1% 手续费
        self.positions[symbol] -= quantity
        
        if self.positions[symbol] == 0:
            del self.position_cost[symbol]
        
        order = {
            "id": len(self.order_history) + 1,
            "symbol": symbol,
            "side": "SELL",
            "quantity": quantity,
            "price": price,
            "status": "FILLED",
            "timestamp": datetime.now().isoformat()
        }
        self.order_history.append(order)
        self.trade_history.append(order)
        
        return {"success": True, "order": order}
    
    def get_position(self, symbol: str) -> int:
        """获取持仓"""
        return self.positions[symbol]
    
    def get_portfolio_value(self, market: SimulatedMarket) -> float:
        """获取组合市值"""
        stock_value = sum(
            self.positions[symbol] * market.get_price(symbol)
            for symbol in self.positions
        )
        return self.cash + stock_value
    
    def get_positions_summary(self, market: SimulatedMarket) -> list:
        """获取持仓汇总"""
        summary = []
        for symbol, qty in self.positions.items():
            if qty > 0:
                current_price = market.get_price(symbol)
                cost = self.position_cost[symbol]
                value = qty * current_price
                cost_basis = qty * cost
                profit = value - cost_basis
                profit_pct = (profit / cost_basis * 100) if cost_basis > 0 else 0
                
                summary.append({
                    "symbol": symbol,
                    "quantity": qty,
                    "avg_cost": round(cost, 2),
                    "current_price": round(current_price, 2),
                    "value": round(value, 2),
                    "profit": round(profit, 2),
                    "profit_pct": round(profit_pct, 2)
                })
        return summary
    
    def get_balance(self, market: SimulatedMarket) -> dict:
        """获取账户余额"""
        return {
            "cash": round(self.cash, 2),
            "stock_value": round(self.get_portfolio_value(market) - self.cash, 2),
            "total_value": round(self.get_portfolio_value(market), 2),
            "initial_cash": self.initial_cash,
            "total_return": round((self.get_portfolio_value(market) - self.initial_cash) / self.initial_cash * 100, 2)
        }


class PaperTrader:
    """模拟交易机器人"""
    
    def __init__(self, initial_cash: float = 100000.0, initial_prices: dict = None):
        self.market = SimulatedMarket(initial_prices)
        self.account = SimulatedAccount(initial_cash)
        self.order_id_counter = 0
        
    def get_quote(self, symbol: str) -> dict:
        """获取实时报价"""
        price = self.market.get_price(symbol)
        return {
            "symbol": symbol,
            "close": price,
            "open": price * random.uniform(0.99, 1.01),
            "high": price * random.uniform(1.0, 1.02),
            "low": price * random.uniform(0.98, 1.0),
            "volume": random.randint(1000000, 10000000)
        }
    
    def get_history_bars(self, symbol: str, period: str = "D1", count: int = 100) -> dict:
        """获取历史K线"""
        klines = self.market.generate_klines(symbol, period, count)
        return {"data": klines}
    
    def buy(self, symbol: str, quantity: int, limit_price: float = None) -> dict:
        """买入"""
        if limit_price is None:
            limit_price = self.market.get_price(symbol)
        
        self.order_id_counter += 1
        return self.account.buy(symbol, quantity, limit_price)
    
    def sell(self, symbol: str, quantity: int, limit_price: float = None) -> dict:
        """卖出"""
        if limit_price is None:
            limit_price = self.market.get_price(symbol)
        
        self.order_id_counter += 1
        return self.account.sell(symbol, quantity, limit_price)
    
    def buy_limit(self, symbol: str, quantity: int, limit_price: float) -> dict:
        """限价买入"""
        current_price = self.market.get_price(symbol)
        if limit_price >= current_price:
            return self.account.buy(symbol, quantity, limit_price)
        return {"success": False, "reason": "price_not_reached"}
    
    def sell_limit(self, symbol: str, quantity: int, limit_price: float) -> dict:
        """限价卖出"""
        current_price = self.market.get_price(symbol)
        if limit_price <= current_price:
            return self.account.sell(symbol, quantity, limit_price)
        return {"success": False, "reason": "price_not_reached"}
    
    def get_positions(self) -> list:
        """获取持仓"""
        return self.account.get_positions_summary(self.market)
    
    def get_balance(self) -> dict:
        """获取账户状态"""
        return self.account.get_balance(self.market)
    
    def next_day(self):
        """模拟一天过去，价格波动"""
        self.market.update_prices()
    
    def run_strategy(self, strategy_class, symbol: str, **kwargs):
        """运行策略并执行信号"""
        # 模拟策略生成信号
        strategy = strategy_class(symbol, **kwargs)
        # 替换市场数据源为模拟市场
        strategy.market_data = self
        
        signal = strategy.generate_signal()
        return signal
    
    def execute_signal(self, symbol: str, signal: str, quantity: int = 10) -> dict:
        """执行交易信号"""
        current_price = self.market.get_price(symbol)
        
        if signal == "BUY":
            return self.buy(symbol, quantity, current_price * 0.98)
        elif signal == "SELL":
            return self.sell(symbol, quantity, current_price * 1.02)
        
        return {"success": False, "reason": "invalid_signal"}


# 便捷函数
def create_paper_trader(initial_cash: float = 100000.0) -> PaperTrader:
    """创建模拟交易者"""
    return PaperTrader(initial_cash)


if __name__ == "__main__":
    # 测试模拟交易
    trader = PaperTrader(100000)
    
    print("=== 初始账户状态 ===")
    print(trader.get_balance())
    
    print("\n=== 买入 AAPL 10股 ===")
    result = trader.buy("AAPL", 10)
    print(result)
    
    print("\n=== 买入 TSLA 5股 ===")
    result = trader.buy("TSLA", 5)
    print(result)
    
    # 模拟几天价格波动
    for i in range(5):
        trader.next_day()
    
    print("\n=== 5天后账户状态 ===")
    print(trader.get_balance())
    
    print("\n=== 当前持仓 ===")
    print(trader.get_positions())
    
    print("\n=== 卖出 AAPL 5股 ===")
    result = trader.sell("AAPL", 5)
    print(result)
    
    print("\n=== 最终账户状态 ===")
    print(trader.get_balance())
