"""
Webull API 客户端 - 美股期权数据获取
"""
import time
import hmac
import hashlib
import base64
import json
import requests
from typing import Optional, Dict, List
import config


class WebullClient:
    """Webull API 客户端"""
    
    BASE_URL = "https://api.webull.com/api"
    
    def __init__(self, email: str = None, password: str = None):
        self.email = email or config.WEBULL_EMAIL
        self.password = password or config.WEBULL_PASSWORD
        self.device_id = config.WEBULL_DEVICE_ID or self._generate_device_id()
        self.access_token = None
        self.refresh_token = config.WEBULL_REFRESH_TOKEN
        self._session = requests.Session()
    
    def _generate_device_id(self) -> str:
        """生成设备ID"""
        import uuid
        return str(uuid.uuid4())
    
    def login(self) -> bool:
        """登录 Webull 账号"""
        url = f"{self.BASE_URL}/user/login"
        data = {
            "account": self.email,
            "password": self.password,
            "deviceId": self.device_id,
            "regionId": 1
        }
        try:
            response = self._session.post(url, json=data)
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get("accessToken")
                self.refresh_token = result.get("refreshToken")
                return True
        except Exception as e:
            print(f"登录失败: {e}")
        return False
    
    def refresh_login(self) -> bool:
        """刷新登录状态"""
        if not self.refresh_token:
            return self.login()
        
        url = f"{self.BASE_URL}/user/refreshToken"
        headers = {"Authorization": f"Bearer {self.refresh_token}"}
        try:
            response = self._session.get(url, headers=headers)
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get("accessToken")
                self.refresh_token = result.get("refreshToken")
                return True
        except Exception as e:
            print(f"刷新登录失败: {e}")
        return False
    
    def get_quote(self, ticker: str) -> Optional[Dict]:
        """获取股票实时行情"""
        url = f"{self.BASE_URL}/quote/quotes/{ticker}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = self._session.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"获取行情失败: {e}")
        return None
    
    def get_options(self, ticker: str, expiration: str = None) -> List[Dict]:
        """
        获取期权链
        
        Args:
            ticker: 股票代码 (如 AAPL)
            expiration: 到期日 (如 2024-12-20)
        
        Returns:
            期权链数据
        """
        url = f"{self.BASE_URL}/option/optionChain/{ticker}"
        params = {}
        if expiration:
            params["expirationDate"] = expiration
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = self._session.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json().get("optionChain", [])
        except Exception as e:
            print(f"获取期权链失败: {e}")
        return []
    
    def get_historical_data(self, ticker: str, period: int = 5, 
                           direction: str = "down") -> List[Dict]:
        """
        获取历史K线数据
        
        Args:
            ticker: 股票代码
            period: 时间周期数量
            direction: up/down
        """
        url = f"{self.BASE_URL}/quote/history/{ticker}"
        params = {
            "period": period,
            "direction": direction,
            "chartType": "candle",
            "showExtend": True
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = self._session.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
        except Exception as e:
            print(f"获取历史数据失败: {e}")
        return []
    
    def get_account_info(self) -> Optional[Dict]:
        """获取账户信息"""
        url = f"{self.BASE_URL}/user/account"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = self._session.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"获取账户信息失败: {e}")
        return None
    
    def get_positions(self) -> List[Dict]:
        """获取当前持仓"""
        url = f"{self.BASE_URL}/portfolio/positions"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = self._session.get(url, headers=headers)
            if response.status_code == 200:
                return response.json().get("rows", [])
        except Exception as e:
            print(f"获取持仓失败: {e}")
        return []
    
    def place_order(self, ticker: str, quantity: int, 
                   strike_price: float, option_type: str,
                   expiry_date: str, action: str) -> Optional[Dict]:
        """
        下单期权
        
        Args:
            ticker: 标的股票
            quantity: 数量
            strike_price: 行权价
            option_type: Call/Put
            expiry_date: 到期日
            action: buy/sell
        """
        url = f"{self.BASE_URL}/trade/order/option"
        
        # 组合期权代码
        option_symbol = f"{ticker}{expiry_date.replace('-','')}{option_type[0].upper()}{strike_price}"
        
        data = {
            "symbol": option_symbol,
            "quantity": quantity,
            "action": action.upper(),
            "orderType": "MLT",
            "outsideRegularTradingHour": True
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = self._session.post(url, json=data, headers=headers)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"下单失败: {e}")
        return None


# 便捷函数
def get_options_chain(ticker: str, refresh: bool = False) -> List[Dict]:
    """获取期权链的便捷函数"""
    client = WebullClient()
    if refresh or not client.access_token:
        client.login()
    return client.get_options(ticker)


def get_realtime_quote(ticker: str) -> Optional[Dict]:
    """获取实时行情的便捷函数"""
    client = WebullClient()
    if not client.access_token:
        client.login()
    return client.get_quote(ticker)


if __name__ == "__main__":
    # 测试
    client = WebullClient()
    if client.login():
        print("登录成功!")
        # 获取 AAPL 行情
        quote = client.get_quote("AAPL")
        print(quote)
