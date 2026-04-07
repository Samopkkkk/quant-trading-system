"""
Option Contract Selector
=======================
Selects liquid US stock options contracts for trading.
Only trades high-liquidity options to ensure fillability.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import pandas as pd


# =============================================================================
# SMALL LIQUID UNIVERSE - MVP focused
# Only trade these underlying stocks (high liquidity, tight spreads)
# =============================================================================

LIQUID_UNDERLYINGS = {
    # US Large Cap - Highest Liquidity
    "SPY": {"name": "S&P 500 ETF", "vol_estimate": 0.15},
    "QQQ": {"name": "Nasdaq 100 ETF", "vol_estimate": 0.20},
    "IWM": {"name": "Russell 2000 ETF", "vol_estimate": 0.22},
    "AAPL": {"name": "Apple Inc", "vol_estimate": 0.25},
    "MSFT": {"name": "Microsoft", "vol_estimate": 0.22},
    "NVDA": {"name": "NVIDIA", "vol_estimate": 0.35},
    "TSLA": {"name": "Tesla", "vol_estimate": 0.45},
    "AMD": {"name": "AMD", "vol_estimate": 0.40},
    "META": {"name": "Meta Platforms", "vol_estimate": 0.30},
    "AMZN": {"name": "Amazon", "vol_estimate": 0.28},
}


@dataclass
class OptionFilter:
    """Option contract selection criteria"""
    min_dte: int = 21          # Minimum days to expiration (3 weeks)
    max_dte: int = 45          # Maximum days to expiration (~1 month)
    min_open_interest: int = 5000  # Minimum open interest
    min_volume: int = 1000     # Minimum daily volume
    strike_width_pct: float = 0.02  # ATM +/- 2% strikes
    min_bid_ask_spread: float = 0.05  # Max spread as % of underlying


class OptionContractSelector:
    """
    Selects appropriate options contracts for trading.
    
    MVP Focus:
    - Only liquid underlyings
    - Near-term expirations (21-45 DTE)
    - ATM strikes (+/- 2%)
    - High open interest (>5000)
    """
    
    def __init__(self, filter_config: Optional[OptionFilter] = None):
        self.filter = filter_config or OptionFilter()
        self.underlyings = LIQUID_UNDERLYINGS
    
    def get_available_underlyings(self) -> List[str]:
        """Get list of tradable underlying symbols"""
        return list(self.underlyings.keys())
    
    def select_strikes(self, underlying: str, current_price: float) -> Dict:
        """
        Select ATM strike prices for an underlying.
        
        Args:
            underlying: Stock symbol
            current_price: Current price of underlying
        
        Returns:
            Dict with call and put strike prices
        """
        if underlying not in self.underlyings:
            raise ValueError(f"Unknown underlying: {underlying}")
        
        # Calculate strike range (ATM +/- 2%)
        width = current_price * self.filter.strike_width_pct
        
        # Find nearest strikes (round to nearest $2.5 or $5)
        atm_strike = self._round_strike(current_price)
        
        return {
            "underlying": underlying,
            "current_price": current_price,
            "atm_strike": atm_strike,
            "call_strike": atm_strike,
            "put_strike": atm_strike,
            "strike_range": {
                "lower": atm_strike - width,
                "upper": atm_strike + width
            }
        }
    
    def _round_strike(self, price: float) -> float:
        """Round strike price to nearest valid increment"""
        if price > 200:
            return round(price / 5) * 5
        elif price > 50:
            return round(price / 2.5) * 2.5
        else:
            return round(price / 2.5) * 2.5
    
    def filter_contracts(self, contracts: pd.DataFrame) -> pd.DataFrame:
        """
        Filter options contracts by liquidity criteria.
        
        Args:
            contracts: DataFrame of available contracts
        
        Returns:
            Filtered DataFrame
        """
        if contracts.empty:
            return contracts
        
        # Apply DTE filter
        contracts = contracts[
            (contracts['dte'] >= self.filter.min_dte) &
            (contracts['dte'] <= self.filter.max_dte)
        ]
        
        # Apply liquidity filters
        contracts = contracts[
            (contracts['open_interest'] >= self.filter.min_open_interest) &
            (contracts['volume'] >= self.filter.min_volume)
        ]
        
        return contracts
    
    def get_contract_spec(self, underlying: str, expiry: str, strike: float, 
                         option_type: str) -> str:
        """
        Generate option contract symbol.
        
        Args:
            underlying: Stock symbol
            expiry: Expiration date (YYYYMMDD)
            strike: Strike price
            option_type: 'CALL' or 'PUT'
        
        Returns:
            Full contract symbol (e.g., AAPL240615C00150000)
        """
        # Format: SYMMDDSTRIKETYPE
        # Example: AAPL240615C00150000
        strike_str = str(int(strike * 1000)).zfill(8)
        type_code = 'C' if option_type.upper() == 'CALL' else 'P'
        
        return f"{underlying.upper()}{expiry}{type_code}{strike_str}"


# =============================================================================
# FACTOR EVALUATION FRAMEWORK
# Core factors for trend following on options
# =============================================================================

class FactorEvaluator:
    """
    Evaluates factors for option trading decisions.
    
    MVP Factors:
    1. Trend strength (SMA slope)
    2. Volatility regime (IV vs HV)
    3. Momentum (recent returns)
    """
    
    def __init__(self):
        self.factors = {}
    
    def calculate_trend_factor(self, prices: pd.Series, 
                              short_window: int = 10,
                              long_window: int = 50) -> float:
        """
        Calculate trend strength factor.
        
        Returns:
            Value between -1 (strong downtrend) and +1 (strong uptrend)
        """
        if len(prices) < long_window:
            return 0.0
        
        short_ma = prices.rolling(short_window).mean().iloc[-1]
        long_ma = prices.rolling(long_window).mean().iloc[-1]
        
        # Normalize by long-term average price
        norm = long_ma / prices.mean()
        return (short_ma - long_ma) / (norm * prices.std())
    
    def calculate_volatility_factor(self, iv: float, hv: float) -> float:
        """
        Calculate volatility regime factor.
        
        Returns:
            > 1: IV > HV (expensive options, consider selling)
            < 1: IV < HV (cheap options, consider buying)
        """
        if hv == 0:
            return 1.0
        return iv / hv
    
    def calculate_momentum_factor(self, prices: pd.Series, 
                                  lookback: int = 20) -> float:
        """
        Calculate momentum factor.
        
        Returns:
            Positive for uptrend, negative for downtrend
        """
        if len(prices) < lookback:
            return 0.0
        
        recent = prices.tail(lookback)
        returns = recent.pct_change().dropna()
        
        if len(returns) == 0:
            return 0.0
        
        return returns.mean() / returns.std() if returns.std() > 0 else 0.0
    
    def evaluate_all(self, prices: pd.Series, iv: float = None) -> Dict[str, float]:
        """Run all factors and return scores"""
        hv = prices.pct_change().rolling(20).std().iloc[-1] * (252 ** 0.5)
        
        return {
            "trend": self.calculate_trend_factor(prices),
            "volatility_regime": self.calculate_volatility_factor(iv or hv, hv),
            "momentum": self.calculate_momentum_factor(prices)
        }


if __name__ == "__main__":
    # Test
    selector = OptionContractSelector()
    print("Available underlyings:", selector.get_available_underlyings())
    
    # Test strike selection
    strikes = selector.select_strikes("SPY", 500.0)
    print("\nSPY @ $500:")
    print(f"  ATM Strike: ${strikes['atm_strike']}")
    print(f"  Range: ${strikes['strike_range']['lower']:.2f} - ${strikes['strike_range']['upper']:.2f}")
