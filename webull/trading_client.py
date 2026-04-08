"""
Webull 交易客户端封装
"""
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.trade.events.trade_events_client import TradeEventsClient
from config import APP_KEY, APP_SECRET, API_ENDPOINT, MARKET_US


class WebullTrader:
    """Webull 交易客户端"""
    
    def __init__(self, app_key: str = None, app_secret: str = None, endpoint: str = API_ENDPOINT):
        self.app_key = app_key or APP_KEY
        self.app_secret = app_secret or APP_SECRET
        self.endpoint = endpoint
        
        # 初始化 API 客户端
        self.api_client = ApiClient(self.app_key, self.app_secret, MARKET_US)
        self.api_client.add_endpoint(MARKET_US, endpoint)
        
        # 初始化交易客户端
        self.trade_client = TradeClient(self.api_client)
        
        # 账户 ID
        self.account_id = None
    
    def get_account_list(self):
        """获取账户列表"""
        res = self.trade_client.account_v2.get_account_list()
        if res.status_code == 200:
            return res.json()
        return None
    
    def set_account(self, account_id: str = None):
        """设置交易账户"""
        if account_id is None:
            accounts = self.get_account_list()
            if accounts and len(accounts) > 0:
                self.account_id = accounts[0].get('accountId')
            else:
                raise Exception("No account found")
        else:
            self.account_id = account_id
        return self.account_id
    
    def get_account_balance(self):
        """获取账户余额"""
        if not self.account_id:
            self.set_account()
        res = self.trade_client.account_v2.get_account(self.account_id)
        if res.status_code == 200:
            return res.json()
        return None
    
    def get_positions(self):
        """获取持仓"""
        if not self.account_id:
            self.set_account()
        res = self.trade_client.account_v2.get_positions(self.account_id)
        if res.status_code == 200:
            return res.json()
        return None
    
    def get_buy_power(self):
        """获取购买力"""
        balance = self.get_account_balance()
        if balance:
            return balance.get('buyPower')
        return None
    
    def get_account_info(self):
        """获取完整账户信息"""
        if not self.account_id:
            self.set_account()
        
        info = {}
        
        # 账户详情
        balance = self.get_account_balance()
        if balance:
            info['cash_balance'] = balance.get('cashBalance')
            info['buy_power'] = balance.get('buyPower')
            info['account_value'] = balance.get('accountValue')
            info['total_equity'] = balance.get('totalEquity')
        
        # 持仓
        positions = self.get_positions()
        info['positions'] = positions
        
        return info


# 事件订阅客户端
class WebullEvents:
    """Webull 事件订阅客户端"""
    
    def __init__(self, app_key: str = None, app_secret: str = None):
        self.app_key = app_key or APP_KEY
        self.app_secret = app_secret or APP_SECRET
        self.events_client = TradeEventsClient(self.app_key, self.app_secret, MARKET_US)
        self.running = False
    
    def subscribe_order_updates(self, account_id: str, callback):
        """
        订阅订单状态更新
        
        Args:
            account_id: 账户ID
            callback: 回调函数
        """
        from webull.trade.events.types import ORDER_STATUS_CHANGED, EVENT_TYPE_ORDER
        
        def on_event(event_type, subscribe_type, payload, raw_message):
            if EVENT_TYPE_ORDER == event_type and ORDER_STATUS_CHANGED == subscribe_type:
                callback(payload)
        
        self.events_client.on_events_message = on_event
        self.events_client.do_subscribe([account_id])
        self.running = True
    
    def stop(self):
        """停止订阅"""
        self.running = False
        # 清理资源


if __name__ == "__main__":
    # 测试
    trader = WebullTrader()
    trader.set_account()
    
    # 获取账户信息
    info = trader.get_account_info()
    print("账户信息:", info)
    
    # 获取持仓
    positions = trader.get_positions()
    print("持仓:", positions)
