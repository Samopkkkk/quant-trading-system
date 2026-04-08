"""
Webull 行情数据客户端
"""
from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.data_streaming_client import DataStreamingClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan
from webull.data.common.subscribe_type import SubscribeType

from config import APP_KEY, APP_SECRET, API_ENDPOINT, DATA_API_ENDPOINT, MQTT_ENDPOINT, MARKET_US


class WebullMarketData:
    """Webull 行情数据客户端"""
    
    def __init__(self, app_key: str = None, app_secret: str = None):
        self.app_key = app_key or APP_KEY
        self.app_secret = app_secret or APP_SECRET
        
        # 初始化数据客户端
        self.api_client = ApiClient(self.app_key, self.app_secret, MARKET_US)
        self.api_client.add_endpoint(MARKET_US, API_ENDPOINT)
        self.data_client = DataClient(self.api_client)
    
    def get_history_bars(self, symbol: str, timespan: str = Timespan.D1.name, 
                          count: int = 100, category: str = None):
        """
        获取历史K线数据
        
        Args:
            symbol: 股票代码 (如 AAPL)
            timespan: 时间周期 (M1/M5/M15/M30/H1/D1/W1/M1)
            count: 数量
            category: 市场类别 (US_STOCK/CRYPTO/FUTURES)
        
        Returns:
            dict: K线数据
        """
        category = category or Category.US_STOCK.name
        res = self.data_client.market_data.get_history_bar(
            symbol, category, timespan, count
        )
        if res.status_code == 200:
            return res.json()
        return None
    
    def get_batch_history_bars(self, symbols: list, timespan: str = Timespan.D1.name,
                               count: int = 1, category: str = None):
        """批量获取历史K线"""
        category = category or Category.US_STOCK.name
        res = self.data_client.market_data.get_batch_history_bar(
            symbols, category, timespan, count
        )
        if res.status_code == 200:
            return res.json()
        return None
    
    def get_realtime_quote(self, symbol: str, category: str = None):
        """获取实时报价"""
        category = category or Category.US_STOCK.name
        res = self.data_client.market_data.get_quote(symbol, category)
        if res.status_code == 200:
            return res.json()
        return None
    
    def get_snapshot(self, symbol: str, category: str = None):
        """获取快照数据"""
        category = category or Category.US_STOCK.name
        res = self.data_client.market_data.get_snapshot(symbol, category)
        if res.status_code == 200:
            return res.json()
        return None


class WebullStreamer:
    """Webull 实时行情订阅"""
    
    def __init__(self, app_key: str = None, app_secret: str = None,
                 session_id: str = "quant_bot"):
        self.app_key = app_key or APP_KEY
        self.app_secret = app_secret or APP_SECRET
        self.session_id = session_id
        self.subscribed = False
        
        self.streaming_client = DataStreamingClient(
            app_key, app_secret, MARKET_US, session_id,
            http_host=DATA_API_ENDPOINT,
            mqtt_host=MQTT_ENDPOINT
        )
        
        # 设置回调
        self.streaming_client.on_connect_success = self._on_connect
        self.streaming_client.on_quotes_message = self._on_message
        self.streaming_client.on_subscribe_success = self._on_subscribe
    
    def _on_connect(self, client, api_client, session_id):
        """连接回调"""
        print(f"Connected: {client.get_session_id()}")
    
    def _on_message(self, client, topic, quotes):
        """消息回调"""
        print(f"Topic: {topic}, Data: {quotes}")
    
    def _on_subscribe(self, client, api_client, session_id):
        """订阅回调"""
        print(f"Subscribed: {client.get_session_id()}")
        self.subscribed = True
    
    def subscribe_quotes(self, symbols: list, category: str = None, 
                         subscribe_types: list = None):
        """
        订阅实时行情
        
        Args:
            symbols: 股票代码列表
            category: 市场类别
            subscribe_types: 订阅类型列表 [QUOTE, SNAPSHOT, TICK]
        """
        category = category or Category.US_STOCK.name
        subscribe_types = subscribe_types or [
            SubscribeType.QUOTE.name, 
            SubscribeType.SNAPSHOT.name, 
            SubscribeType.TICK.name
        ]
        
        # 连接并开始订阅
        self.streaming_client.connect_and_loop_forever()
        
        # 订阅
        self.streaming_client.subscribe(symbols, category, subscribe_types)
    
    def stop(self):
        """停止订阅"""
        self.streaming_client.close()
        self.subscribed = False


# 便捷函数
def get_current_price(symbol: str) -> float:
    """获取当前价格"""
    data = WebullMarketData()
    quote = data.get_realtime_quote(symbol)
    if quote and 'data' in quote:
        return quote['data'].get('close')
    return None


def get_klines(symbol: str, period: str = 'D1', count: int = 100) -> list:
    """
    获取K线数据
    
    Args:
        symbol: 股票代码
        period: 周期 (M1/M5/M15/M30/H1/D1/W1)
        count: 数量
    """
    data = WebullMarketData()
    result = data.get_history_bars(symbol, period, count)
    if result and 'data' in result:
        return result['data']
    return []


if __name__ == "__main__":
    # 测试
    md = WebullMarketData()
    
    # 获取AAPL历史K线
    bars = md.get_history_bars("AAPL", Timespan.D1.name, 10)
    print("AAPL K线:", bars)
    
    # 获取实时报价
    quote = md.get_realtime_quote("AAPL")
    print("AAPL 实时报价:", quote)
    
    # 批量获取
    batch = md.get_batch_history_bars(["AAPL", "TSLA"], Timespan.D1.name, 5)
    print("批量K线:", batch)
