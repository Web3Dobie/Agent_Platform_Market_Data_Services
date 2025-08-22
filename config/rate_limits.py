# services/data_aggregator.py (Updated version)
import asyncio
import logging
from typing import List, Optional, Dict
from datetime import datetime

from .data_providers.binance_provider import BinanceProvider
from .data_providers.mexc_provider import MexcProvider  
from .data_providers.ig_provider import IGProvider
from .data_providers.enhanced_yahoo_finance import EnhancedYahooFinanceProvider
from app.models import PriceData, AssetType

logger = logging.getLogger(__name__)

class DataAggregator:
    """
    Enhanced data aggregator with improved Yahoo Finance integration
    """
    
    def __init__(self):
        # Initialize providers
        self.binance = BinanceProvider()
        self.mexc = MexcProvider()
        self.ig = IGProvider()
        self.yahoo = EnhancedYahooFinanceProvider()  # Enhanced provider
        
        # Provider priority for different asset types
        self.provider_priority = {
            AssetType.CRYPTO: ['binance', 'mexc', 'yahoo'],
            AssetType.FOREX: ['ig', 'yahoo'],
            AssetType.EQUITY: ['yahoo', 'ig'],  # Yahoo first for equities
            AssetType.INDEX: ['yahoo', 'ig'],
            AssetType.COMMODITY: ['ig', 'yahoo']
        }
        
        logger.info("📊 Enhanced Data Aggregator initialized with batch processing")
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get single price with enhanced provider selection"""
        asset_type = self._detect_asset_type(symbol)
        providers = self.provider_priority.get(asset_type, ['yahoo'])
        
        logger.debug(f"💰 Getting price for {symbol} (type: {asset_type}) - providers: {providers}")
        
        for provider_name in providers:
            try:
                provider = getattr(self, provider_name)
                result = await provider.get_price(symbol)
                
                if result:
                    logger.debug(f"✅ Price found for {symbol} via {provider_name}: ${result.price}")
                    return result
                    
            except Exception as e:
                logger.warning(f"⚠️ Provider {provider_name} failed for {symbol}: {e}")
                continue
        
        logger.warning(f"❌ No price found for {symbol} after trying all providers")
        return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """
        Enhanced bulk price fetching with smart provider routing
        Key improvement: Use batch processing for Yahoo Finance
        """
        if not symbols:
            return []
        
        logger.info(f"📊 Bulk request for {len(symbols)} symbols")
        
        # Group symbols by optimal provider
        symbol_groups = self._group_symbols_by_provider(symbols)
        
        # Results dictionary to maintain order
        results = {}
        
        # Process each provider group
        for provider_name, provider_symbols in symbol_groups.items():
            if not provider_symbols:
                continue
                
            logger.info(f"🔄 Processing {len(provider_symbols)} symbols via {provider_name}")
            
            try:
                provider = getattr(self, provider_name)
                
                # Use bulk method if available (Yahoo has enhanced bulk processing)
                if hasattr(provider, 'get_bulk_prices'):
                    provider_results = await provider.get_bulk_prices(provider_symbols)
                    
                    # Map results back to symbols
                    for symbol, result in zip(provider_symbols, provider_results):
                        results[symbol] = result
                else:
                    # Fallback to individual requests for other providers
                    for symbol in provider_symbols:
                        result = await provider.get_price(symbol)
                        results[symbol] = result
                        
            except Exception as e:
                logger.error(f"❌ Provider {provider_name} bulk request failed: {e}")
                # Mark all symbols as failed for this provider
                for symbol in provider_symbols:
                    results[symbol] = None
        
        # Handle failed symbols with fallback providers
        failed_symbols = [symbol for symbol, result in results.items() if result is None]
        
        if failed_symbols:
            logger.info(f"🔄 Retrying {len(failed_symbols)} failed symbols with fallback providers")
            await self._retry_failed_symbols(failed_symbols, results)
        
        # Return results in original order
        final_results = [results.get(symbol) for symbol in symbols]
        
        success_count = sum(1 for r in final_results if r is not None)
        logger.info(f"✅ Bulk request complete: {success_count}/{len(symbols)} successful")
        
        return final_results
    
    def _group_symbols_by_provider(self, symbols: List[str]) -> Dict[str, List[str]]:
        """
        Smart symbol grouping by optimal provider
        This is key for efficient batch processing
        """
        groups = {
            'binance': [],
            'mexc': [],
            'ig': [],
            'yahoo': []
        }
        
        for symbol in symbols:
            asset_type = self._detect_asset_type(symbol)
            primary_provider = self.provider_priority.get(asset_type, ['yahoo'])[0]
            groups[primary_provider].append(symbol)
        
        # Log grouping decisions
        for provider, provider_symbols in groups.items():
            if provider_symbols:
                logger.debug(f"📋 {provider}: {len(provider_symbols)} symbols")
        
        return groups
    
    async def _retry_failed_symbols(self, failed_symbols: List[str], results: Dict):
        """Retry failed symbols with alternative providers"""
        for symbol in failed_symbols:
            asset_type = self._detect_asset_type(symbol)
            providers = self.provider_priority.get(asset_type, ['yahoo'])
            
            # Try alternative providers
            for provider_name in providers[1:]:  # Skip primary provider
                try:
                    provider = getattr(self, provider_name)
                    result = await provider.get_price(symbol)
                    
                    if result:
                        results[symbol] = result
                        logger.debug(f"✅ Fallback success: {symbol} via {provider_name}")
                        break
                        
                except Exception as e:
                    logger.debug(f"Fallback failed: {symbol} via {provider_name}: {e}")
                    continue
    
    def _detect_asset_type(self, symbol: str) -> AssetType:
        """Detect asset type from symbol format"""
        symbol_upper = symbol.upper()
        
        # Crypto patterns
        if any(crypto in symbol_upper for crypto in ['-USD', '-USDT', 'BTC', 'ETH', 'USDT']):
            return AssetType.CRYPTO
        
        # Forex patterns
        if any(fx in symbol_upper for fx in ['USD=X', 'EUR', 'GBP', '=X']):
            return AssetType.FOREX
        
        # Index patterns
        if symbol_upper.startswith('^') or any(idx in symbol_upper for idx in ['SPX', 'DJI', 'IXIC']):
            return AssetType.INDEX
        
        # Commodity patterns
        if any(comm in symbol_upper for comm in ['=F', 'GC=', 'CL=', 'NG=']):
            return AssetType.COMMODITY
        
        # Default to equity
        return AssetType.EQUITY

# Dependency injection function
async def get_aggregator() -> DataAggregator:
    """Get data aggregator instance"""
    return DataAggregator()