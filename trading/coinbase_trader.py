"""
Coinbase Live Trading Connector
Real-time trading for Gold/Silver futures
"""
from typing import Optional, Dict, List
from datetime import datetime
import time
import hmac
import hashlib
import requests
from data.coinbase_client import CoinbaseClient
import config


class CoinbaseTrader(CoinbaseClient):
    """
    Coinbase Live Trading Connector
    
    Extends CoinbaseClient with trading functionality
    """
    
    def __init__(self, paper_trading: bool = False):
        """
        Initialize trader
        
        Args:
            paper_trading: Use sandbox/testnet (if available)
        """
        super().__init__()
        self.paper_trading = paper_trading
        
        if paper_trading:
            self.BASE_URL = "https://api.sandbox.coinbase.com"
    
    def is_configured(self) -> bool:
        """Check if API credentials are configured"""
        return bool(self.api_key and self.api_secret)
    
    def get_balance(self, currency: str = "USD") -> Optional[float]:
        """
        Get account balance
        
        Args:
            currency: Currency symbol (USD, USDC, BTC, etc.)
        """
        accounts = self.get_accounts()
        
        for account in accounts:
            if account.get('currency', {}).get('code') == currency:
                return float(account.get('available_balance', {}).get('value', 0))
        
        return None
    
    def place_market_order(self, product_id: str, side: str,
                          size: float) -> Optional[Dict]:
        """
        Place market order
        
        Args:
            product_id: Product ID (e.g., "GC-USD", "SI-USD")
            side: "BUY" or "SELL"
            size: Order size
        """
        return self.place_order(
            product_id=product_id,
            side=side,
            order_type="market",
            size=size
        )
    
    def place_limit_order(self, product_id: str, side: str,
                         size: float, price: float,
                         time_in_force: str = "GTC") -> Optional[Dict]:
        """
        Place limit order
        
        Args:
            product_id: Product ID
            side: "BUY" or "SELL"
            size: Order size
            price: Limit price
            time_in_force: GTC, IOC, FOK
        """
        return self.place_order(
            product_id=product_id,
            side=side,
            order_type="limit",
            size=size,
            price=price,
            time_in_force=time_in_force
        )
    
    def place_stop_order(self, product_id: str, side: str,
                        size: float, stop_price: float) -> Optional[Dict]:
        """
        Place stop order
        
        Args:
            product_id: Product ID
            side: "BUY" or "SELL"
            size: Order size
            stop_price: Stop trigger price
        """
        # Stop orders in Coinbase Advanced Trade
        order_config = {
            "stop_order_config": {
                "stop_price": str(stop_price),
                "stop_direction": "STOP_UP" if side.upper() == "BUY" else "STOP_DOWN"
            }
        }
        
        data = {
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": {
                "market_market_order_config": {"size": str(size)},
                **order_config
            }
        }
        
        return self._request("POST", "/api/v3/brokerage/orders", data)
    
    def cancel_all_orders(self, product_id: str = None) -> List[str]:
        """
        Cancel all open orders
        
        Args:
            product_id: Optional product filter
        
        Returns:
            List of cancelled order IDs
        """
        open_orders = self.get_orders("OPEN")
        cancelled = []
        
        for order in open_orders:
            if product_id and order.get('product_id') != product_id:
                continue
            
            order_id = order.get('order_id')
            if self.cancel_order(order_id):
                cancelled.append(order_id)
        
        return cancelled
    
    def get_orderbook(self, product_id: str, level: int = 2) -> Optional[Dict]:
        """
        Get orderbook
        
        Args:
            product_id: Product ID
            level: 1 (top), 2 (top 50), 3 (full)
        """
        return self._request("GET", f"/api/v3/brokerage/products/{product_id}/book", {
            "product_id": product_id,
            "limit": 50 if level == 2 else (100 if level == 3 else 1)
        })
    
    def get_fees(self, product_id: str = None) -> Optional[Dict]:
        """
        Get fee information
        """
        if product_id:
            return self.get_product(product_id)
        
        # Get fees from account
        return self._request("GET", "/api/v3/brokerage/accounts/fees")
    
    def get_market_trades(self, product_id: str, limit: int = 100) -> List[Dict]:
        """
        Get recent market trades
        """
        result = self._request("GET", f"/api/v3/brokerage/products/{product_id}/ticker")
        
        if result:
            return result.get('trades', [])
        return []
    
    # ============== Convenience Trading Functions ==============
    
    def buy_gold(self, size: float, order_type: str = "market",
                price: float = None) -> Optional[Dict]:
        """Buy gold (GC-USD)"""
        if order_type == "market":
            return self.place_market_order("GC-USD", "BUY", size)
        else:
            return self.place_limit_order("GC-USD", "BUY", size, price)
    
    def sell_gold(self, size: float, order_type: str = "market",
                 price: float = None) -> Optional[Dict]:
        """Sell gold (GC-USD)"""
        if order_type == "market":
            return self.place_market_order("GC-USD", "SELL", size)
        else:
            return self.place_limit_order("GC-USD", "SELL", size, price)
    
    def buy_silver(self, size: float, order_type: str = "market",
                  price: float = None) -> Optional[Dict]:
        """Buy silver (SI-USD)"""
        if order_type == "market":
            return self.place_market_order("SI-USD", "BUY", size)
        else:
            return self.place_limit_order("SI-USD", "BUY", size, price)
    
    def sell_silver(self, size: float, order_type: str = "market",
                   price: float = None) -> Optional[Dict]:
        """Sell silver (SI-USD)"""
        if order_type == "market":
            return self.place_market_order("SI-USD", "SELL", size)
        else:
            return self.place_limit_order("SI-USD", "SELL", size, price)
    
    def close_all_positions(self, product_id: str = None) -> List[Dict]:
        """
        Close all positions for a product
        
        Args:
            product_id: Optional product filter
        """
        results = []
        
        # Get all positions (fills)
        fills = self.get_fills(product_id)
        
        # Group by product and calculate net position
        positions = {}
        for fill in fills:
            product = fill.get('product_id')
            side = fill.get('side')
            size = float(fill.get('size', 0))
            
            if product not in positions:
                positions[product] = 0
            
            if side == "BUY":
                positions[product] += size
            else:
                positions[product] -= size
        
        # Close positions
        for product, net_size in positions.items():
            if net_size > 0:
                result = self.place_market_order(product, "SELL", abs(net_size))
                results.append(result)
            elif net_size < 0:
                result = self.place_market_order(product, "BUY", abs(net_size))
                results.append(result)
        
        return results


# ============== Trading Bot Framework ==============

class TradingBot:
    """
    Simple Trading Bot Framework
    
    Connects strategy signals to live trading
    """
    
    def __init__(self, name: str, trader: CoinbaseTrader):
        self.name = name
        self.trader = trader
        self.positions: Dict[str, float] = {}
        self.running = False
    
    def start(self):
        """Start the trading bot"""
        self.running = True
        print(f"Trading bot '{self.name}' started")
    
    def stop(self):
        """Stop the trading bot"""
        self.running = False
        print(f"Trading bot '{self.name}' stopped")
    
    def execute_signal(self, symbol: str, action: str, quantity: float,
                      price: float = None) -> Optional[Dict]:
        """
        Execute a trading signal
        
        Args:
            symbol: Product ID (GC-USD, SI-USD)
            action: BUY, SELL, CLOSE
            quantity: Size
            price: Limit price (optional)
        """
        if action.upper() == "CLOSE":
            # Close position
            return self.trader.place_market_order(symbol, "SELL" if self.positions.get(symbol, 0) > 0 else "BUY", abs(quantity))
        elif action.upper() in ["BUY", "SELL"]:
            if price:
                return self.trader.place_limit_order(symbol, action.upper(), quantity, price)
            else:
                return self.trader.place_market_order(symbol, action.upper(), quantity)
        
        return None
    
    def update_positions(self):
        """Update position tracking"""
        # In production, fetch from exchange
        pass


# ============== Convenience Functions ==============

def create_trader(paper_trading: bool = False) -> CoinbaseTrader:
    """Create a Coinbase trader instance"""
    return CoinbaseTrader(paper_trading=paper_trading)


def create_bot(name: str, paper_trading: bool = False) -> TradingBot:
    """Create a trading bot"""
    trader = create_trader(paper_trading)
    return TradingBot(name, trader)


if __name__ == "__main__":
    # Test
    trader = CoinbaseTrader()
    
    if trader.is_configured():
        # Get balances
        usd_balance = trader.get_balance("USD")
        print(f"USD Balance: ${usd_balance}")
        
        # Get gold price
        gold = trader.get_gold_price()
        print(f"Gold price: ${gold}")
    else:
        print("API credentials not configured")
