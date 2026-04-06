"""
Data Loader
Fetch and manage historical data for backtesting
"""
import os
import pandas as pd
import numpy as np
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import config


class DataLoader:
    """
    Historical Data Loader
    
    Fetch data from various sources for backtesting
    """
    
    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
    
    def load_csv(self, filename: str) -> Optional[pd.DataFrame]:
        """Load data from CSV file"""
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            return None
        
        df = pd.read_csv(filepath, parse_dates=['date'], index_col='date')
        return df
    
    def save_csv(self, df: pd.DataFrame, filename: str):
        """Save data to CSV file"""
        filepath = os.path.join(self.data_dir, filename)
        df.to_csv(filepath)
    
    def get_data_path(self, symbol: str, start_date: str, end_date: str) -> str:
        """Get data file path"""
        return f"{symbol}_{start_date}_{end_date}.csv"


class WebullDataLoader(DataLoader):
    """
    Webull Data Loader
    
    Fetch options and stock data from Webull
    """
    
    def __init__(self, data_dir: str = "data/historical"):
        super().__init__(data_dir)
        self.client = None
    
    def _get_client(self):
        """Get or create Webull client"""
        if not self.client:
            from data.webull_client import WebullClient
            self.client = WebullClient()
            self.client.login()
        return self.client
    
    def fetch_stock_data(self, symbol: str, period: int = 5,
                        direction: str = "down") -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data
        
        Args:
            symbol: Stock symbol (e.g., AAPL, SPY)
            period: Number of time periods
            direction: "down" (past) or "up" (future)
        """
        client = self._get_client()
        
        data = client.get_historical_data(symbol, period, direction)
        
        if not data:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        if 'time' in df.columns:
            df['date'] = pd.to_datetime(df['time'], unit='ms')
            df = df.set_index('date')
            df = df.sort_index()
        
        return df
    
    def fetch_options_chain(self, symbol: str,
                          expiration: str = None) -> List[Dict]:
        """Fetch options chain"""
        client = self._get_client()
        return client.get_options(symbol, expiration)
    
    def load_or_fetch(self, symbol: str, start_date: str, end_date: str,
                     force_refresh: bool = False) -> pd.DataFrame:
        """
        Load from cache or fetch from API
        
        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            force_refresh: Force refresh from API
        """
        filename = self.get_data_path(symbol, start_date, end_date)
        
        # Try to load from cache
        if not force_refresh:
            df = self.load_csv(filename)
            if df is not None:
                return df
        
        # Fetch from API
        # Note: Webull API returns limited historical data
        # For full historical data, consider using yfinance
        df = self.fetch_stock_data(symbol, period=5)
        
        if df is not None:
            # Filter by date range
            df = df[(df.index >= start_date) & (df.index <= end_date)]
            # Save to cache
            self.save_csv(df, filename)
        
        return df


class YahooDataLoader(DataLoader):
    """
    Yahoo Finance Data Loader
    
    Use yfinance to fetch historical data
    """
    
    def __init__(self, data_dir: str = "data/historical"):
        super().__init__(data_dir)
    
    def fetch_data(self, symbol: str, start_date: str, end_date: str,
                  interval: str = "1d") -> Optional[pd.DataFrame]:
        """
        Fetch data from Yahoo Finance
        
        Args:
            symbol: Stock/futures symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Data interval (1d, 1h, 5m, etc.)
        """
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)
            
            if df is not None and len(df) > 0:
                df.index = df.index.tz_localize(None)  # Remove timezone
                return df
            
        except ImportError:
            print("yfinance not installed. Run: pip install yfinance")
        except Exception as e:
            print(f"Error fetching data: {e}")
        
        return None
    
    def load_or_fetch(self, symbol: str, start_date: str, end_date: str,
                     interval: str = "1d",
                     force_refresh: bool = False) -> pd.DataFrame:
        """Load from cache or fetch from Yahoo"""
        filename = f"{symbol}_{start_date}_{end_date}_{interval}.csv"
        
        # Try to load from cache
        if not force_refresh:
            df = self.load_csv(filename)
            if df is not None:
                return df
        
        # Fetch from Yahoo
        df = self.fetch_data(symbol, start_date, end_date, interval)
        
        if df is not None:
            self.save_csv(df, filename)
        
        return df
    
    def fetch_multiple(self, symbols: List[str], start_date: str,
                      end_date: str) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols"""
        result = {}
        
        for symbol in symbols:
            print(f"Fetching {symbol}...")
            df = self.load_or_fetch(symbol, start_date, end_date)
            if df is not None:
                result[symbol] = df
        
        return result


class CoinbaseDataLoader(DataLoader):
    """
    Coinbase Data Loader
    
    Fetch futures data from Coinbase
    """
    
    def __init__(self, data_dir: str = "data/historical"):
        super().__init__(data_dir)
        self.client = None
    
    def _get_client(self):
        """Get or create Coinbase client"""
        if not self.client:
            from data.coinbase_client import CoinbaseClient
            self.client = CoinbaseClient()
        return self.client
    
    def fetch_candles(self, product_id: str, granularity: int = 3600,
                     start_time: str = None, end_time: str = None) -> Optional[pd.DataFrame]:
        """
        Fetch candle data
        
        Args:
            product_id: Product ID (GC-USD, SI-USD)
            granularity: Candle period in seconds (60, 300, 900, 3600, 86400)
            start_time: Start time (ISO 8601)
            end_time: End time (ISO 8601)
        """
        client = self._get_client()
        
        candles = client.get_candles(product_id, granularity, start_time, end_time)
        
        if not candles:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
        df['date'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.set_index('date')
        df = df.sort_index()
        
        # Convert to numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def fetch_gold_data(self, days: int = 30, granularity: int = 3600) -> Optional[pd.DataFrame]:
        """Fetch gold futures data"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        return self.fetch_candles(
            "GC-USD",
            granularity,
            start_time.isoformat() + "Z",
            end_time.isoformat() + "Z"
        )
    
    def fetch_silver_data(self, days: int = 30, granularity: int = 3600) -> Optional[pd.DataFrame]:
        """Fetch silver futures data"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        return self.fetch_candles(
            "SI-USD",
            granularity,
            start_time.isoformat() + "Z",
            end_time.isoformat() + "Z"
        )
    
    def load_or_fetch(self, product_id: str, days: int = 30,
                     granularity: int = 3600,
                     force_refresh: bool = False) -> pd.DataFrame:
        """Load from cache or fetch"""
        filename = f"{product_id}_{days}d_{granularity}s.csv"
        
        if not force_refresh:
            df = self.load_csv(filename)
            if df is not None:
                return df
        
        df = self.fetch_candles(product_id, granularity)
        
        if df is not None:
            self.save_csv(df, filename)
        
        return df


# ============== Factory ==============

def create_loader(source: str = "yahoo", **kwargs) -> DataLoader:
    """
    Create a data loader
    
    Args:
        source: Data source (yahoo, webull, coinbase)
    """
    loaders = {
        'yahoo': YahooDataLoader,
        'webull': WebullDataLoader,
        'coinbase': CoinbaseDataLoader,
    }
    
    loader_class = loaders.get(source.lower())
    if loader_class:
        return loader_class(**kwargs)
    else:
        raise ValueError(f"Unknown data source: {source}")


# ============== Example Usage ==============

if __name__ == "__main__":
    # Example: Fetch gold data from Coinbase
    loader = CoinbaseDataLoader()
    
    print("Fetching gold data...")
    gold_data = loader.fetch_gold_data(days=7)
    
    if gold_data is not None:
        print(f"Got {len(gold_data)} candles")
        print(gold_data.tail())
    else:
        print("Failed to fetch data")
