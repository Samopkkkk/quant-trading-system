"""
Webull 订单管理
"""
import uuid
from config import *


class OrderManager:
    """订单管理器"""
    
    def __init__(self, trader: 'WebullTrader'):
        self.trader = trader
    
    def place_order(self, symbol: str, side: str, quantity: int, 
                    order_type: str = "LIMIT", limit_price: float = None,
                    time_in_force: str = DEFAULT_TIME_IN_FORCE):
        """
        下单
        
        Args:
            symbol: 股票代码 (如 AAPL)
            side: BUY/SELL
            quantity: 数量
            order_type: LIMIT/MARKET
            limit_price: 限价（限价单必填）
            time_in_force: DAY/GTC/IOC/FOK
        
        Returns:
            client_order_id: 订单ID
        """
        if not self.trader.account_id:
            self.trader.set_account()
        
        client_order_id = uuid.uuid4().hex
        
        order = {
            "combo_type": DEFAULT_COMBO_TYPE,
            "client_order_id": client_order_id,
            "symbol": symbol,
            "instrument_type": "EQUITY",
            "market": "US",
            "order_type": order_type,
            "quantity": str(quantity),
            "support_trading_session": DEFAULT_TRADING_SESSION,
            "side": side,
            "time_in_force": time_in_force,
            "entrust_type": DEFAULT_ENTRUST_TYPE
        }
        
        if order_type == "LIMIT" and limit_price:
            order["limit_price"] = str(limit_price)
        
        res = self.trader.trade_client.order_v2.place_order(
            self.trader.account_id, [order]
        )
        
        if res.status_code == 200:
            result = res.json()
            return result[0].get('clientOrderId') if result else None
        return None
    
    def buy_limit(self, symbol: str, quantity: int, limit_price: float, 
                  time_in_force: str = DEFAULT_TIME_IN_FORCE):
        """限价买入"""
        return self.place_order(symbol, "BUY", quantity, "LIMIT", limit_price, time_in_force)
    
    def sell_limit(self, symbol: str, quantity: int, limit_price: float,
                   time_in_force: str = DEFAULT_TIME_IN_FORCE):
        """限价卖出"""
        return self.place_order(symbol, "SELL", quantity, "LIMIT", limit_price, time_in_force)
    
    def buy_market(self, symbol: str, quantity: int):
        """市价买入"""
        return self.place_order(symbol, "BUY", quantity, "MARKET")
    
    def sell_market(self, symbol: str, quantity: int):
        """市价卖出"""
        return self.place_order(symbol, "SELL", quantity, "MARKET")
    
    def modify_order(self, client_order_id: str, quantity: int = None, 
                     limit_price: float = None):
        """
        修改订单
        
        Args:
            client_order_id: 订单ID
            quantity: 新数量
            limit_price: 新价格
        """
        if not self.trader.account_id:
            self.trader.set_account()
        
        modify_order = {
            "client_order_id": client_order_id
        }
        
        if quantity:
            modify_order["quantity"] = str(quantity)
        if limit_price:
            modify_order["limit_price"] = str(limit_price)
        
        res = self.trader.trade_client.order_v2.replace_order(
            self.trader.account_id, [modify_order]
        )
        
        if res.status_code == 200:
            return res.json()
        return None
    
    def cancel_order(self, client_order_id: str):
        """撤单"""
        if not self.trader.account_id:
            self.trader.set_account()
        
        res = self.trader.trade_client.order_v2.cancel_order(
            self.trader.account_id, client_order_id
        )
        
        if res.status_code == 200:
            return res.json()
        return None
    
    def get_open_orders(self):
        """获取未完成订单"""
        if not self.trader.account_id:
            self.trader.set_account()
        
        res = self.trader.trade_client.order_v2.get_orders(self.trader.account_id)
        if res.status_code == 200:
            return res.json()
        return None
    
    def get_order_details(self, client_order_id: str):
        """获取订单详情"""
        if not self.trader.account_id:
            self.trader.set_account()
        
        res = self.trader.trade_client.order_v2.get_order(
            self.trader.account_id, client_order_id
        )
        if res.status_code == 200:
            return res.json()
        return None
    
    def cancel_all_orders(self):
        """撤销所有未完成订单"""
        open_orders = self.get_open_orders()
        if not open_orders:
            return []
        
        cancelled = []
        for order in open_orders:
            client_order_id = order.get('clientOrderId')
            if client_order_id:
                result = self.cancel_order(client_order_id)
                cancelled.append({
                    'order_id': client_order_id,
                    'result': result
                })
        
        return cancelled


class Order:
    """订单数据类"""
    
    def __init__(self, data: dict):
        self.data = data
        self.client_order_id = data.get('clientOrderId')
        self.symbol = data.get('symbol')
        self.side = data.get('side')
        self.quantity = data.get('quantity')
        self.price = data.get('limitPrice') or data.get('price')
        self.order_type = data.get('orderType')
        self.status = data.get('status')
        self.filled = data.get('filled')
        self.create_time = data.get('createTime')
    
    def __repr__(self):
        return f"Order({self.symbol} {self.side} {self.quantity}@{self.price} [{self.status}])"


if __name__ == "__main__":
    from trading_client import WebullTrader
    
    # 测试
    trader = WebullTrader()
    trader.set_account()
    
    order_mgr = OrderManager(trader)
    
    # 下单测试
    # order_id = order_mgr.buy_limit("AAPL", 1, 150.0)
    # print(f"下单成功，订单ID: {order_id}")
    
    # 获取未完成订单
    open_orders = order_mgr.get_open_orders()
    print("未完成订单:", open_orders)
