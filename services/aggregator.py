import asyncio
from typing import List, Optional
from datetime import datetime, timedelta
from services.cache_service import CacheService
from services.data_providers.binance import BinanceProvider
from services.data_providers.yahoo_finance import YahooFinanceProvider
from services.data_providers.ig_index import IGIndexProvider
from services.data_providers.mexc import MEXCProvider
from app.models import PriceData, AssetType
from config.settings import settings

import logging

logger = logging.getLogger(__name__)

class DataAggregator:
    """Aggregates data from providers with intelligent routing and fallback"""
    
    def __init__(self):
        self.providers = {
            'binance': BinanceProvider(),
            'yahoo': YahooFinanceProvider(),
            'ig_index': IGIndexProvider(), 
            'mexc': MEXCProvider(),
        }
        self.cache = CacheService()
    
    async def initialize(self):
        """Initialize all services"""
        await self.cache.connect()
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get price with provider selection and caching"""
        
        # Check cache first
        cache_key = f"price:{symbol}"
        cached_data = await self.cache.get(cache_key)
        
        if cached_data and not self._is_stale(cached_data):
            return cached_data
        
        # Determine best provider for this symbol
        provider_order = self._get_provider_order(symbol)
        
        for provider_name in provider_order:
            try:
                provider = self.providers[provider_name]
                price_data = await provider.get_price(symbol)
                
                if price_data:
                    # Cache with appropriate TTL
                    ttl = self.cache.get_ttl_for_asset(price_data.asset_type)
                    await self.cache.set(cache_key, price_data, ttl)
                    return price_data
                    
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed for {symbol}: {e}")
                continue
        
        # Return stale cache if all providers fail
        if cached_data:
            logger.warning(f"All providers failed for {symbol}, returning stale cache")
            return cached_data
        
        return None
    
    async def get_bulk_prices(self, symbols: List[str], **kwargs) -> List[Optional[PriceData]]:
        """Get multiple prices concurrently"""
        tasks = [self.get_price(symbol) for symbol in symbols]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    def _get_provider_order(self, symbol: str) -> List[str]:
        """Determine provider priority based on symbol (corrected routing)"""
        symbol_upper = symbol.upper().replace("$", "")

        # Check MEXC-specific tokens first
        if symbol_upper in ["WAI"]:  # Add more MEXC-only tokens here
            return ["mexc"]
        
        # Crypto - Binance primary, MEXC fallback
        if symbol_upper in ["BTC", "ETH", "SOL", "AVAX", "MATIC", "ADA", "DOT", "LINK", "UNI", "AAVE"]:
            return ["binance"]
        
        # Indices - IG Index PRIMARY, Yahoo Finance fallback
        elif symbol_upper in ["^GSPC", "SPY", "^IXIC", "QQQ", "^DJI", "^RUT", "IWM",
                            "^GDAXI", "^FTSE", "^STOXX50E", "^FCHI", 
                            "^N225", "^HSI", "000001.SS", "^KS11", "^VIX", "VIX", "DXY"]:
            return ["ig_index", "yahoo"]  # IG FIRST!
        
        # FX - IG Index PRIMARY, Yahoo Finance fallback
        elif any(symbol_upper.startswith(pair) for pair in [
            "EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD", "EURGBP", "EURJPY"
        ]):
            return ["ig_index", "yahoo"]  # IG FIRST!
        
        # Commodities - IG Index PRIMARY, Yahoo Finance fallback
        elif symbol_upper in ["GC=F", "GOLD", "SI=F", "SILVER", "CL=F", "OIL",
                            "BZ=F", "BRENT", "NG=F", "NATGAS", "HG=F", "COPPER"]:
            return ["ig_index", "yahoo"]  # IG FIRST!
        
        # Equities - Yahoo Finance ONLY
        else:
            return ["yahoo"]
    
    def _is_stale(self, cached_data: PriceData) -> bool:
        """Check if cached data is stale based on asset type"""
        now = datetime.utcnow()
        age = (now - cached_data.timestamp).total_seconds()
        
        if cached_data.asset_type == AssetType.CRYPTO:
            return age > settings.crypto_cache_ttl
        else:
            return age > settings.traditional_cache_ttl
    
    async def health_check(self) -> dict:
        """Check health of all providers"""
        results = {}
        
        # Check cache
        results['cache'] = await self.cache.health_check()
        
        # Check providers
        for name, provider in self.providers.items():
            try:
                results[name] = await provider.health_check()
            except:
                results[name] = False
        
        return results
