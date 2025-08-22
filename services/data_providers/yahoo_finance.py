# services/data_providers/session_yahoo_finance.py
"""
Session-based Yahoo Finance provider that replicates yFinance's successful approach
Based on investigation showing that persistent sessions bypass rate limiting
"""

import asyncio
import time
import logging
import requests
from typing import Optional, List, Dict
from datetime import datetime
import json
from app.models import PriceData, AssetType

logger = logging.getLogger(__name__)

class SessionYahooFinanceProvider:
    """
    Yahoo Finance provider using persistent sessions (the key to avoiding 429s)
    Replicates exactly what yFinance does successfully
    """
    
    def __init__(self):
        # Create persistent session (this is the key!)
        self.session = requests.Session()
        
        # Use exact headers that work from our investigation
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
        })
        
        # Rate limiting (conservative)
        self.last_request_time = 0
        self.min_delay = 1.0
        
        # Use the working endpoint from investigation
        self.base_url = "https://query2.finance.yahoo.com"
        
        logger.info("🔧 Session-based Yahoo Finance provider initialized")
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get single price using session-based approach"""
        await self._enforce_rate_limit()
        
        try:
            # Use the exact approach that worked in our test
            ticker_data = await asyncio.to_thread(self._get_chart_data, symbol)
            
            if ticker_data:
                return PriceData(
                    symbol=symbol,
                    asset_type=self._detect_asset_type(symbol),
                    price=ticker_data['price'],
                    change_percent=ticker_data['change_percent'],
                    change_absolute=ticker_data['change_absolute'],
                    volume=ticker_data.get('volume'),
                    market_cap=None,
                    timestamp=datetime.utcnow(),
                    source="session_yahoo"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Session Yahoo Finance error for {symbol}: {e}")
            return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """Get bulk prices using session approach with rate limiting"""
        if not symbols:
            return []
        
        logger.info(f"📊 Processing {len(symbols)} symbols with session-based requests")
        
        results = []
        for i, symbol in enumerate(symbols):
            try:
                # Add delay between requests (but much shorter since sessions work)
                if i > 0:
                    await asyncio.sleep(0.5)  # Short delay between symbols
                
                result = await self.get_price(symbol)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to get price for {symbol}: {e}")
                results.append(None)
        
        success_count = sum(1 for r in results if r is not None)
        logger.info(f"✅ Session bulk processing complete: {success_count}/{len(symbols)} successful")
        
        return results
    
    def _get_chart_data(self, symbol: str) -> Optional[dict]:
        """
        Get chart data using persistent session (the working approach)
        Replicates exactly what yFinance does
        """
        try:
            # Use exact URL and parameters that worked
            url = f"{self.base_url}/v8/finance/chart/{symbol}"
            params = {
                'range': '2d',
                'interval': '1d',
                'includePrePost': False,
                'events': 'div,splits,capitalGains'
            }
            
            logger.debug(f"🌐 Session request: {url}")
            
            # Use the persistent session (this is the key!)
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse the response (same format as yFinance expects)
                if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
                    result = data['chart']['result'][0]
                    
                    # Extract price data
                    if 'meta' in result:
                        meta = result['meta']
                        current_price = meta.get('regularMarketPrice')
                        previous_close = meta.get('previousClose', current_price)
                        
                        if current_price and previous_close:
                            change_absolute = current_price - previous_close
                            change_percent = (change_absolute / previous_close * 100) if previous_close > 0 else 0
                            
                            # Get volume if available
                            volume = None
                            if 'timestamp' in result and 'indicators' in result:
                                indicators = result['indicators']
                                if 'quote' in indicators and indicators['quote']:
                                    quote = indicators['quote'][0]
                                    if 'volume' in quote and quote['volume']:
                                        volumes = [v for v in quote['volume'] if v is not None]
                                        if volumes:
                                            volume = volumes[-1]
                            
                            return {
                                'price': round(float(current_price), 4),
                                'change_percent': round(change_percent, 2),
                                'change_absolute': round(change_absolute, 4),
                                'volume': volume,
                                'timestamp': datetime.now()
                            }
                
                logger.debug(f"⚠️ No valid price data in response for {symbol}")
                return None
                
            elif response.status_code == 429:
                logger.warning(f"⚠️ Rate limited for {symbol} (even with session)")
                return None
            else:
                logger.warning(f"⚠️ HTTP {response.status_code} for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Chart data fetch failed for {symbol}: {e}")
            return None
    
    def _detect_asset_type(self, symbol: str) -> AssetType:
        """Detect asset type from symbol"""
        symbol_upper = symbol.upper()
        
        if any(crypto in symbol_upper for crypto in ['-USD', '-USDT', 'BTC', 'ETH']):
            return AssetType.CRYPTO
        elif any(fx in symbol_upper for fx in ['USD=X', 'EUR', 'GBP', '=X']):
            return AssetType.FOREX
        elif symbol_upper.startswith('^') or any(idx in symbol_upper for idx in ['SPX', 'DJI', 'IXIC']):
            return AssetType.INDEX
        elif any(comm in symbol_upper for comm in ['=F', 'GC=', 'CL=', 'NG=']):
            return AssetType.COMMODITY
        else:
            return AssetType.EQUITY
    
    async def _enforce_rate_limit(self):
        """Conservative rate limiting"""
        now = time.time()
        time_since_last = now - self.last_request_time
        
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def close(self):
        """Close the session when done"""
        if self.session:
            self.session.close()

# Factory function
def create_session_yahoo_provider() -> SessionYahooFinanceProvider:
    """Factory function for dependency injection"""
    return SessionYahooFinanceProvider()