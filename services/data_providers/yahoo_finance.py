import yfinance as yf
import asyncio
import time
from typing import Optional, List
from datetime import datetime
from app.models import PriceData, AssetType
import logging

logger = logging.getLogger(__name__)

class YahooFinanceProvider:
    """Yahoo Finance for equity data"""
    
    def __init__(self):
        self.last_request_time = 0
        self.min_delay = 1.0  # 1 second between requests
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        # Add delay to avoid rate limits
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_delay:
            await asyncio.sleep(self.min_delay - time_since_last)
        
        self.last_request_time = time.time()
        
        """Get equity price from Yahoo Finance"""
        try:
            # Run yfinance in thread pool (it's synchronous)
            ticker_data = await asyncio.to_thread(self._get_ticker_data, symbol)
            
            if ticker_data:
                return PriceData(
                    symbol=symbol,
                    asset_type=AssetType.EQUITY,
                    price=ticker_data['price'],
                    change_percent=ticker_data['change_percent'],
                    change_absolute=ticker_data['change_absolute'],
                    volume=ticker_data.get('volume'),
                    market_cap=ticker_data.get('market_cap'),
                    timestamp=datetime.utcnow(),
                    source="yahoo_finance"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Yahoo Finance API error for {symbol}: {e}")
            return None
    
    def _get_ticker_data(self, symbol: str) -> Optional[dict]:
        """Synchronous Yahoo Finance data fetch"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info or 'regularMarketPrice' not in info:
                return None
            
            current_price = info['regularMarketPrice']
            previous_close = info.get('previousClose', current_price)
            
            change_absolute = current_price - previous_close
            change_percent = (change_absolute / previous_close) * 100 if previous_close else 0
            
            return {
                'price': float(current_price),
                'change_percent': float(change_percent),
                'change_absolute': float(change_absolute),
                'volume': info.get('regularMarketVolume'),
                'market_cap': info.get('marketCap')
            }
            
        except Exception as e:
            logger.error(f"Yahoo Finance sync error for {symbol}: {e}")
            return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """Get multiple equity prices"""
        tasks = [self.get_price(symbol) for symbol in symbols]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    async def health_check(self) -> bool:
        """Check if Yahoo Finance is accessible"""
        try:
            test_data = await self.get_price("AAPL")
            return test_data is not None
        except:
            return False
