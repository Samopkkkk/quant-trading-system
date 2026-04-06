"""
Coinbase Advanced Trade API 客户端 - 黄金/白银期货
"""
import time
import hmac
import hashlib
import base64
import requests
from typing import Optional, Dict, List
from datetime import datetime
import config


class CoinbaseClient:
    """Coinbase Advanced Trade API 客户端"""
    
    BASE_URL = "https://api.coinbase.com"
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key or config.COINBASE_API_KEY
        self.api_secret = api_secret or config.COINBASE_API_SECRET
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "CB-ACCESS-KEY": self.api_key
        })
    
    def _generate_signature(self, method: str, path: str, body: str = "") -> str:
        """生成签名"""
        timestamp = str(int(time.time()))
        message = timestamp + method + path + body
        
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _request(self, method: str, endpoint: str, data: dict = None) -> Optional[Dict]:
        """发送请求"""
        url = f"{self.BASE_URL}{endpoint}"
        body = ""
        if data:
            body = str(data)
        
        timestamp = str(int(time.time()))
        signature = self._generate_signature(method, endpoint, body)
        
        headers = {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp
        }
        
        try:
            if method == "GET":
                response = self._session.get(url, headers=headers, params=data)
            elif method == "POST":
                response = self._session.post(url, headers=headers, json=data)
            else:
                return None
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"请求失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"请求异常: {e}")
        return None
    
    def get_products(self) -> List[Dict]:
        """获取可交易产品列表"""
        return self._request("GET", "/api/v3/brokerage/products")
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """获取指定产品详情"""
        return self._request("GET", f"/api/v3/brokerage/products/{product_id}")
    
    def get_candles(self, product_id: str, granularity: int = 60,
                    start_time: str = None, end_time: str = None) -> List[Dict]:
        """
        获取K线数据
        
        Args:
            product_id: 产品ID (如 "GC-USD")
            granularity: 时间粒度(秒) - 60, 300, 900, 3600, 86400
            start_time: 开始时间 ISO 8601
            end_time: 结束时间 ISO 8601
        """
        params = {
            "product_id": product_id,
            "candle_selection_params": {
                "candle_period": granularity
            }
        }
        
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        
        result = self._request("GET", "/api/v3/brokerage/products/candles", params)
        if result:
            return result.get("candles", [])
        return []
    
    def get_ticker(self, product_id: str) -> Optional[Dict]:
        """获取实时行情"""
        result = self._request("GET", f"/api/v3/brokerage/products/{product_id}/ticker")
        if result:
            return result.get("ticker", {})
        return None
    
    def get_accounts(self) -> List[Dict]:
        """获取账户列表"""
        result = self._request("GET", "/api/v3/brokerage/accounts")
        if result:
            return result.get("accounts", [])
        return []
    
    def get_account(self, account_id: str) -> Optional[Dict]:
        """获取指定账户详情"""
        return self._request("GET", f"/api/v3/brokerage/accounts/{account_id}")
    
    def place_order(self, product_id: str, side: str, order_type: str,
                   size: float = None, price: float = None,
                   time_in_force: str = "GTC") -> Optional[Dict]:
        """
        下单
        
        Args:
            product_id: 产品ID (如 "GC-USD")
            side: buy/sell
            order_type: market/limit
            size: 数量
            price: 价格 (限价单)
            time_in_force: GTC/IOC/FOK
        """
        order_config = {
            "order_type": order_type.upper()
        }
        
        if order_type == "limit":
            order_config["limit_price"] = str(price)
            order_config["limit_order_config"] = {
                "time_in_force": time_in_force
            }
        elif order_type == "market":
            order_config["market_market_order_config"] = {
                "size": str(size)
            }
        
        data = {
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": order_config
        }
        
        return self._request("POST", "/api/v3/brokerage/orders", data)
    
    def cancel_order(self, order_id: str) -> Optional[Dict]:
        """取消订单"""
        return self._request("POST", "/api/v3/brokerage/orders/batch_cancel", {
            "order_ids": [order_id]
        })
    
    def get_orders(self, order_status: str = "ALL") -> List[Dict]:
        """获取订单列表"""
        result = self._request("GET", "/api/v3/brokerage/orders", {
            "order_status": order_status
        })
        if result:
            return result.get("orders", [])
        return []
    
    def get_fills(self, product_id: str = None) -> List[Dict]:
        """获取成交记录"""
        params = {}
        if product_id:
            params["product_id"] = product_id
        
        result = self._request("GET", "/api/v3/brokerage/fills", params)
        if result:
            return result.get("fills", [])
        return []
    
    # ============ 便捷函数 ============
    
    def get_gold_price(self) -> Optional[Dict]:
        """获取黄金价格"""
        return self.get_ticker("GC-USD")
    
    def get_silver_price(self) -> Optional[Dict]:
        """获取白银价格"""
        return self.get_ticker("SI-USD")
    
    def get_gold_candles(self, granularity: int = 3600,
                         hours: int = 24) -> List[Dict]:
        """获取黄金K线"""
        import datetime
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(hours=hours)
        
        return self.get_candles(
            "GC-USD",
            granularity,
            start_time.isoformat() + "Z",
            end_time.isoformat() + "Z"
        )
    
    def get_silver_candles(self, granularity: int = 3600,
                          hours: int = 24) -> List[Dict]:
        """获取白银K线"""
        import datetime
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(hours=hours)
        
        return self.get_candles(
            "SI-USD",
            granularity,
            start_time.isoformat() + "Z",
            end_time.isoformat() + "Z"
        )


# 便捷函数
def get_realtime_price(symbol: str) -> Optional[Dict]:
    """获取实时价格"""
    client = CoinbaseClient()
    product_map = {
        "GC": "GC-USD",
        "SI": "SI-USD",
        "GOLD": "GC-USD",
        "SILVER": "SI-USD"
    }
    product_id = product_map.get(symbol.upper(), symbol)
    return client.get_ticker(product_id)


def get_historical_prices(symbol: str, hours: int = 24, 
                          granularity: int = 3600) -> List[Dict]:
    """获取历史价格"""
    client = CoinbaseClient()
    product_map = {
        "GC": "GC-USD",
        "SI": "SI-USD"
    }
    product_id = product_map.get(symbol.upper(), symbol)
    
    if product_id == "GC-USD":
        return client.get_gold_candles(granularity, hours)
    elif product_id == "SI-USD":
        return client.get_silver_candles(granularity, hours)
    return []


if __name__ == "__main__":
    # 测试
    client = CoinbaseClient()
    
    # 获取黄金价格
    gold = client.get_gold_price()
    print(f"黄金: {gold}")
    
    # 获取白银价格
    silver = client.get_silver_price()
    print(f"白银: {silver}")
