# services/data_providers/direct_yfinance.py
"""
Direct yFinance provider - use yFinance exactly as-is with no modifications
Let yFinance handle all the session management, rate limiting, and API calls internally
"""

import yfinance as yf
import asyncio
import time
import logging
from typing import Optional, List, Dict
from datetime import datetime
from app.models import PriceData, AssetType
import pandas as pd

logger = logging.getLogger(__name__)

class DirectYahooFinanceProvider:
    """
    Direct yFinance provider - minimal wrapper around yFinance library
    Let yFinance handle everything internally (sessions, rate limits, etc.)
    """
    
    def __init__(self):
        self.last_request_time = 0
        self.min_delay = 2.0  # Conservative delay between our calls
        
        logger.info("📈 Direct yFinance provider initialized")
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get single price using yFinance directly"""
        await self._rate_limit()
        
        try:
            # Use yFinance exactly as-is in a thread
            ticker_data = await asyncio.to_thread(self._get_yfinance_data, symbol)
            
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
                    source="direct_yfinance"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Direct yFinance error for {symbol}: {e}")
            return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """Get bulk prices using yFinance download (like HedgeFundAgent)"""
        if not symbols:
            return []
        
        logger.info(f"📊 yFinance bulk download for {len(symbols)} symbols")
        
        try:
            # Use yFinance download exactly like your working HedgeFundAgent
            bulk_data = await asyncio.to_thread(self._bulk_yfinance_download, symbols)
            
            # Convert to PriceData objects
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
                        source="direct_yfinance_bulk"
                    )
                    results.append(price_data)
                else:
                    results.append(None)
            
            success_count = sum(1 for r in results if r is not None)
            logger.info(f"✅ yFinance bulk: {success_count}/{len(symbols)} successful")
            
            return results
            
        except Exception as e:
            logger.error(f"yFinance bulk download failed: {e}")
            # Fallback to individual requests
            return await self._fallback_individual_requests(symbols)
    
    def _get_yfinance_data(self, symbol: str) -> Optional[dict]:
        """Get data for single symbol using yFinance (let it handle everything)"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Try method 1: .info (fast but sometimes limited)
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
            except:
                pass
            
            # Method 2: .history (more reliable but slower)
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
            except:
                pass
            
            logger.debug(f"No valid data found for {symbol}")
            return None
            
        except Exception as e:
            logger.debug(f"yFinance error for {symbol}: {e}")
            return None
    
    def _bulk_yfinance_download(self, symbols: List[str]) -> Dict[str, dict]:
        """
        Bulk download using yFinance download function
        Exact same approach as your working HedgeFundAgent
        """
        try:
            logger.info(f"🌐 yFinance downloading {len(symbols)} symbols...")
            
            # Use yFinance download exactly like HedgeFundAgent
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
                    # Handle single vs multiple symbols (same logic as HedgeFundAgent)
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
            logger.error(f"yFinance bulk download failed: {e}")
            return {symbol: None for symbol in symbols}
    
    async def _fallback_individual_requests(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """Fallback to individual requests if bulk fails"""
        logger.info(f"🔄 Fallback to individual requests for {len(symbols)} symbols")
        
        results = []
        for symbol in symbols:
            try:
                await asyncio.sleep(1)  # Add delay for individual requests
                result = await self.get_price(symbol)
                results.append(result)
            except Exception as e:
                logger.debug(f"Individual fallback failed for {symbol}: {e}")
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
    
    async def _rate_limit(self):
        """Simple rate limiting between our requests"""
        now = time.time()
        time_since_last = now - self.last_request_time
        
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()

# Factory function
def create_direct_yahoo_provider() -> DirectYahooFinanceProvider:
    """Factory function for dependency injection"""
    return DirectYahooFinanceProvider()