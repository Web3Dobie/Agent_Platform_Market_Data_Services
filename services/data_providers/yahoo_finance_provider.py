# services/data_providers/yahoo_finance_provider.py
"""
yFinance provider scaffolding - complete implementation ready for testing
NO API CALLS - just mock responses until weekend testing
"""

import asyncio
import time
import logging
from typing import Optional, List, Dict
from datetime import datetime
from app.models import PriceData, AssetType
import random

logger = logging.getLogger(__name__)

class YahooFinanceProvider:
    """
    Complete yFinance provider scaffolding
    Ready to activate when rate limits reset
    """
    
    def __init__(self, enable_api_calls: bool = False):
        self.enable_api_calls = enable_api_calls  # Set to False for now
        self.last_request_time = 0
        self.min_delay = 2.0  # Conservative delay
        
        # Rate limiting tracking
        self.requests_this_hour = 0
        self.hour_start_time = time.time()
        self.max_requests_per_hour = 50  # Very conservative
        
        logger.info(f"📈 Yahoo Finance provider initialized (API calls: {'ON' if enable_api_calls else 'OFF'})")
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get single price - scaffolded implementation"""
        if not self.enable_api_calls:
            return self._mock_price_data(symbol)
        
        await self._enforce_rate_limit()
        
        try:
            # Real implementation (activate on weekend)
            ticker_data = await asyncio.to_thread(self._get_real_yfinance_data, symbol)
            
            if ticker_data:
                return PriceData(
                    symbol=symbol,
                    asset_type=self._detect_asset_type(symbol),
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
            logger.error(f"Yahoo Finance error for {symbol}: {e}")
            return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """Get bulk prices - scaffolded implementation"""
        if not self.enable_api_calls:
            return [self._mock_price_data(symbol) for symbol in symbols]
        
        logger.info(f"📊 Yahoo Finance bulk request for {len(symbols)} symbols")
        
        # Check rate limits
        if not self._check_rate_limits(len(symbols)):
            logger.warning("⚠️ Rate limit would be exceeded, skipping bulk request")
            return [None] * len(symbols)
        
        try:
            # Real bulk implementation (activate on weekend)
            if len(symbols) > 5:
                # Use yf.download for bulk
                return await self._bulk_download_approach(symbols)
            else:
                # Use individual requests for small batches
                return await self._individual_requests_approach(symbols)
            
        except Exception as e:
            logger.error(f"Yahoo Finance bulk error: {e}")
            return [None] * len(symbols)
    
    def _mock_price_data(self, symbol: str) -> Optional[PriceData]:
        """Generate mock data for testing (no API calls)"""
        # Generate realistic mock data based on symbol type
        if symbol.startswith('^TNX'):
            base_price = 4.2  # 10Y yield
        elif symbol.startswith('^IRX'):
            base_price = 5.1  # 13W yield
        elif symbol.startswith('^TYX'):
            base_price = 4.4  # 30Y yield
        elif symbol == 'AAPL':
            base_price = 180.0
        elif symbol == 'MSFT':
            base_price = 420.0
        elif symbol.startswith('^'):
            base_price = random.uniform(15000, 35000)  # Index
        else:
            base_price = random.uniform(50, 500)  # Generic stock
        
        # Add some realistic variation
        variation = random.uniform(-0.02, 0.02)  # ±2%
        current_price = base_price * (1 + variation)
        change_percent = variation * 100
        change_absolute = base_price * variation
        
        return PriceData(
            symbol=symbol,
            asset_type=self._detect_asset_type(symbol),
            price=round(current_price, 4),
            change_percent=round(change_percent, 2),
            change_absolute=round(change_absolute, 4),
            volume=random.randint(1000000, 10000000) if not symbol.startswith('^') else None,
            market_cap=None,
            timestamp=datetime.utcnow(),
            source="yahoo_finance_mock"
        )
    
    def _get_real_yfinance_data(self, symbol: str) -> Optional[dict]:
        """
        Real yFinance implementation (activate on weekend)
        Currently disabled to prevent API calls
        """
        if not self.enable_api_calls:
            return None
        
        try:
            # Import yfinance only when we're ready to use it
            import yfinance as yf
            import pandas as pd
            
            ticker = yf.Ticker(symbol)
            
            # Method 1: Try .info first (faster)
            try:
                info = ticker.info
                if info and 'regularMarketPrice' in info:
                    current_price = info['regularMarketPrice']
                    previous_close = info.get('previousClose', current_price)
                    
                    if current_price and previous_close:
                        change_absolute = current_price - previous_close
                        change_percent = (change_absolute / previous_close * 100) if previous_close > 0 else 0
                        
                        return {
                            'price': round(float(current_price), 4),
                            'change_percent': round(change_percent, 2),
                            'change_absolute': round(change_absolute, 4),
                            'volume': info.get('volume'),
                            'market_cap': info.get('marketCap')
                        }
            except Exception:
                pass
            
            # Method 2: Try .history (more reliable)
            try:
                hist = ticker.history(period="2d")
                if not hist.empty and len(hist) > 0:
                    current_price = float(hist['Close'].iloc[-1])
                    prev_price = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
                    
                    change_absolute = current_price - prev_price
                    change_percent = (change_absolute / prev_price * 100) if prev_price > 0 else 0
                    
                    volume = None
                    if 'Volume' in hist.columns and not pd.isna(hist['Volume'].iloc[-1]):
                        volume = int(hist['Volume'].iloc[-1])
                    
                    return {
                        'price': round(current_price, 4),
                        'change_percent': round(change_percent, 2),
                        'change_absolute': round(change_absolute, 4),
                        'volume': volume
                    }
            except Exception:
                pass
            
            return None
            
        except Exception as e:
            logger.debug(f"Real yFinance error for {symbol}: {e}")
            return None
    
    async def _bulk_download_approach(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """
        Bulk download using yf.download (like HedgeFundAgent)
        Ready to activate on weekend
        """
        if not self.enable_api_calls:
            return [self._mock_price_data(symbol) for symbol in symbols]
        
        try:
            # Import only when ready to use
            import yfinance as yf
            import pandas as pd
            
            logger.info(f"🌐 yFinance bulk download for {len(symbols)} symbols")
            
            # Use exact same approach as working HedgeFundAgent
            bulk_data = await asyncio.to_thread(self._yfinance_download, symbols)
            
            results = []
            for symbol in symbols:
                if symbol in bulk_data and bulk_data[symbol]:
                    data = bulk_data[symbol]
                    price_data = PriceData(
                        symbol=symbol,
                        asset_type=self._detect_asset_type(symbol),
                        price=data['price'],
                        change_percent=data['change_percent'],
                        change_absolute=data['change_absolute'],
                        volume=data.get('volume'),
                        market_cap=None,
                        timestamp=datetime.utcnow(),
                        source="yahoo_finance_bulk"
                    )
                    results.append(price_data)
                else:
                    results.append(None)
            
            return results
            
        except Exception as e:
            logger.error(f"Bulk download failed: {e}")
            # Fallback to individual requests
            return await self._individual_requests_approach(symbols)
    
    def _yfinance_download(self, symbols: List[str]) -> Dict[str, dict]:
        """
        Core yFinance download function (exact HedgeFundAgent pattern)
        Ready to activate on weekend
        """
        if not self.enable_api_calls:
            return {}
        
        try:
            import yfinance as yf
            import pandas as pd
            
            # Exact same call as HedgeFundAgent
            data = yf.download(
                symbols, 
                period="2d", 
                interval="1d", 
                group_by="ticker",
                progress=False,
                show_errors=False
            )
            
            results = {}
            
            for symbol in symbols:
                try:
                    # Same logic as HedgeFundAgent
                    if len(symbols) == 1:
                        symbol_data = data
                    else:
                        if hasattr(data.columns, 'levels') and symbol in data.columns.levels[0]:
                            symbol_data = data[symbol]
                        else:
                            symbol_data = None
                    
                    if symbol_data is not None and not symbol_data.empty and len(symbol_data) > 0:
                        current_price = float(symbol_data['Close'].iloc[-1])
                        prev_price = float(symbol_data['Close'].iloc[-2]) if len(symbol_data) > 1 else current_price
                        
                        change_absolute = current_price - prev_price
                        change_percent = (change_absolute / prev_price * 100) if prev_price > 0 else 0
                        
                        volume = None
                        if 'Volume' in symbol_data.columns and len(symbol_data) > 0:
                            vol_val = symbol_data['Volume'].iloc[-1]
                            volume = int(vol_val) if not pd.isna(vol_val) else None
                        
                        results[symbol] = {
                            'price': round(current_price, 4),
                            'change_percent': round(change_percent, 2),
                            'change_absolute': round(change_absolute, 4),
                            'volume': volume
                        }
                    else:
                        results[symbol] = None
                        
                except Exception as e:
                    logger.debug(f"Error processing {symbol} in bulk: {e}")
                    results[symbol] = None
            
            return results
            
        except Exception as e:
            logger.error(f"yFinance download core failed: {e}")
            return {symbol: None for symbol in symbols}
    
    async def _individual_requests_approach(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """Individual requests with proper delays"""
        results = []
        
        for i, symbol in enumerate(symbols):
            try:
                if i > 0:
                    await asyncio.sleep(self.min_delay)  # Rate limiting
                
                result = await self.get_price(symbol)
                results.append(result)
                
            except Exception as e:
                logger.debug(f"Individual request failed for {symbol}: {e}")
                results.append(None)
        
        return results
    
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
    
    def _check_rate_limits(self, num_requests: int) -> bool:
        """Check if we can make this many requests without hitting limits"""
        now = time.time()
        
        # Reset hourly counter
        if now - self.hour_start_time >= 3600:
            self.requests_this_hour = 0
            self.hour_start_time = now
        
        # Check if this request would exceed limits
        if self.requests_this_hour + num_requests > self.max_requests_per_hour:
            return False
        
        return True
    
    async def _enforce_rate_limit(self):
        """Enforce rate limiting between requests"""
        now = time.time()
        time_since_last = now - self.last_request_time
        
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.requests_this_hour += 1
    
    def enable_api(self):
        """Enable API calls (call this on weekend)"""
        self.enable_api_calls = True
        logger.info("🚀 Yahoo Finance API calls ENABLED")
    
    def disable_api(self):
        """Disable API calls (safety)"""
        self.enable_api_calls = False
        logger.info("🛑 Yahoo Finance API calls DISABLED")

# Factory function
def create_yahoo_provider(enable_api: bool = False) -> YahooFinanceProvider:
    """Factory function for dependency injection"""
    return YahooFinanceProvider(enable_api_calls=enable_api)