"""
Webull Live Trading Connector
Real-time trading for US stock options
"""
from typing import Optional, Dict, List
from datetime import datetime
import time
import requests
from data.webull_client import WebullClient
import config


class WebullTrader(WebullClient):
    """
    Webull Live Trading Connector
    
    Extends WebullClient with trading functionality
    """
    
    def __init__(self, paper_trading: bool = True):
        """
        Initialize trader
        
        Args:
            paper_trading: Use paper trading (simulated) account
        """
        super().__init__()
        self.paper_trading = paper_trading
        self.base_url = "https://api.webull.com/api" if not paper_trading else "https://api.webull.com/paperapi2"
        
    def is_logged_in(self) -> bool:
        """Check if logged in"""
        return self.access_token is not None
    
    def get_account_balance(self) -> Optional[float]:
        """Get account balance"""
        endpoint = "/account/info"
        result = self._request("GET", endpoint)
        
        if result:
            return result.get('cashBalance', 0)
        return None
    
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        endpoint = "/portfolio/positions"
        result = self._request("GET", endpoint)
        
        if result:
            return result.get('rows', [])
        return []
    
    def place_order(self, symbol: str, quantity: int,
                   order_type: str = "MKT",
                   side: str = "BUY",
                   price: float = None,
                   strike_price: float = None,
                   option_type: str = None,
                   expiry_date: str = None,
                   duration: str = "GTC") -> Optional[Dict]:
        """
        Place an order
        
        Args:
            symbol: Stock symbol (e.g., AAPL)
            quantity: Number of contracts/shares
            order_type: MKT, LMT, STP
            side: BUY, SELL
            price: Limit price (for LMT orders)
            strike_price: Strike price (for options)
            option_type: CALL, PUT (for options)
            expiry_date: Expiration date (for options)
            duration: GTC, DAY, IOC
        
        Returns:
            Order result
        """
        # Build order payload
        order_data = {
            "symbol": symbol,
            "quantity": quantity,
            "side": side.upper(),
            "orderType": order_type.upper(),
            "timeInForce": duration.upper()
        }
        
        # Add limit price
        if price and order_type.upper() in ["LMT", "STP"]:
            order_data["limitPrice"] = str(price)
        
        # For options
        if strike_price and option_type and expiry_date:
            order_data["strikePrice"] = str(strike_price)
            order_data["callOrPut"] = option_type.upper()[0]  # C or P
            order_data["expirationDate"] = expiry_date
        
        # Use paper trading endpoint if enabled
        endpoint = "/trade/order"
        if self.paper_trading:
            endpoint = "/paper/order"
        
        result = self._request("POST", endpoint, order_data)
        
        return result
    
    def place_options_order(self, symbol: str,
                           quantity: int,
                           strike_price: float,
                           option_type: str,  # CALL or PUT
                           expiry_date: str,
                           side: str = "SELL",
                           order_type: str = "MKT",
                           price: float = None) -> Optional[Dict]:
        """
        Place an options order
        
        Args:
            symbol: Underlying stock symbol
            quantity: Number of contracts
            strike_price: Strike price
            option_type: CALL or PUT
            expiry_date: Expiration date (YYYY-MM-DD)
            side: BUY or SELL
            order_type: MKT or LMT
            price: Limit price (for LMT orders)
        """
        # Construct options symbol (Webull format)
        # Example: AAPL240420C00150000
        expiry_str = expiry_date.replace("-", "")
        option_symbol = f"{symbol}{expiry_str}{option_type[0].upper()}{int(strike_price * 1000):08d}"
        
        order_data = {
            "symbol": option_symbol,
            "quantity": quantity,
            "side": side.upper(),
            "orderType": order_type.upper()
        }
        
        if price:
            order_data["limitPrice"] = str(price)
        
        endpoint = "/trade/order/option"
        if self.paper_trading:
            endpoint = "/paper/option/order"
        
        return self._request("POST", endpoint, order_data)
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        endpoint = f"/trade/order/{order_id}"
        
        if self.paper_trading:
            endpoint = f"/paper/order/{order_id}"
        
        result = self._request("DELETE", endpoint)
        return result is not None
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get order status"""
        endpoint = f"/trade/order/{order_id}"
        
        if self.paper_trading:
            endpoint = f"/paper/order/{order_id}"
        
        return self._request("GET", endpoint)
    
    def get_open_orders(self) -> List[Dict]:
        """Get all open orders"""
        endpoint = "/trade/orders"
        
        if self.paper_trading:
            endpoint = "/paper/orders"
        
        result = self._request("GET", endpoint)
        
        if result:
            return result.get('rows', [])
        return []
    
    def modify_order(self, order_id: str, quantity: int = None,
                    price: float = None) -> Optional[Dict]:
        """Modify an existing order"""
        order_data = {}
        
        if quantity:
            order_data["quantity"] = quantity
        if price:
            order_data["limitPrice"] = str(price)
        
        if not order_data:
            return None
        
        endpoint = f"/trade/order/{order_id}"
        
        if self.paper_trading:
            endpoint = f"/paper/order/{order_id}"
        
        return self._request("PUT", endpoint, order_data)
    
    def _request(self, method: str, endpoint: str, data: dict = None) -> Optional[Dict]:
        """Make API request with auth"""
        if not self.is_logged_in():
            if not self.login():
                return None
        
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=data)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                return None
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Token expired, try to refresh
                if self.refresh_login():
                    return self._request(method, endpoint, data)
            
        except Exception as e:
            print(f"Request error: {e}")
        
        return None


# ============== Convenience Functions ==============

def create_trader(paper_trading: bool = True) -> WebullTrader:
    """Create a Webull trader instance"""
    return WebullTrader(paper_trading=paper_trading)


if __name__ == "__main__":
    # Test
    trader = WebullTrader(paper_trading=True)
    
    if trader.login():
        print("Logged in successfully")
        
        # Get balance
        balance = trader.get_account_balance()
        print(f"Account balance: ${balance}")
        
        # Get positions
        positions = trader.get_positions()
        print(f"Open positions: {len(positions)}")
