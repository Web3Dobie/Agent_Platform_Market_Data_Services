# services/aggregator.py - Clean aggregator with initialization fix, no Yahoo Finance

import asyncio
import logging
from typing import List, Optional, Dict
from datetime import datetime

from .data_providers.binance import BinanceProvider
from .data_providers.mexc import MEXCProvider  
from .data_providers.ig_index import IGIndexProvider
from app.models import PriceData, AssetType

logger = logging.getLogger(__name__)

class DataAggregator:
    """Clean DataAggregator - Initialization fix + PriceData support, NO Yahoo Finance"""
    
    def __init__(self):
        # Initialize providers but don't consider them ready yet
        self.providers = {
            'binance': BinanceProvider(),
            'mexc': MEXCProvider(),
            'ig_index': IGIndexProvider(),
        }
        
        # Track initialization status (KEEP THIS - fixes first requests timing out)
        self._initialized = False
        self._provider_ready = {
            'binance': False,
            'mexc': False, 
            'ig_index': False
        }
        
        # Provider priority
        self.provider_priority = {
            AssetType.CRYPTO: ['binance', 'mexc'],
            AssetType.FOREX: ['ig_index'],
            AssetType.EQUITY: ['ig_index'],
            AssetType.INDEX: ['ig_index'],
            AssetType.COMMODITY: ['ig_index']
        }
        
        logger.info("📊 Clean Data Aggregator created - NO Yahoo Finance")
        logger.info("🚀 Using: Binance, MEXC, IG Index only")
    
    async def initialize(self):
        """
        KEEP THIS - Properly initialize all providers with connection testing
        This ensures providers are ready before handling requests
        """
        logger.info("🚀 Starting provider initialization...")
        
        initialization_results = {}
        
        for name, provider in self.providers.items():
            logger.info(f"🔧 Initializing {name} provider...")
            
            try:
                # Check if provider has an initialize method
                if hasattr(provider, 'initialize'):
                    await provider.initialize()
                    logger.info(f"✅ {name} initialize() method completed")
                
                # Test the provider with a health check
                if hasattr(provider, 'health_check'):
                    health_result = await provider.health_check()
                    if health_result:
                        self._provider_ready[name] = True
                        logger.info(f"✅ {name} health check passed")
                        initialization_results[name] = "healthy"
                    else:
                        logger.warning(f"⚠️ {name} health check failed")
                        initialization_results[name] = "unhealthy"
                else:
                    # Test with a simple price request if no health check
                    test_symbol = self._get_test_symbol_for_provider(name)
                    logger.info(f"🧪 Testing {name} with symbol {test_symbol}...")
                    
                    test_result = await provider.get_price(test_symbol)
                    if test_result:  # PriceData object or dict - either is fine for testing
                        self._provider_ready[name] = True
                        logger.info(f"✅ {name} test request successful")
                        initialization_results[name] = "healthy"
                    else:
                        logger.warning(f"⚠️ {name} test request failed")
                        initialization_results[name] = "unhealthy"
                
                # Small delay between provider initializations
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize {name}: {e}")
                initialization_results[name] = f"error: {str(e)}"
        
        # Mark as initialized
        self._initialized = True
        
        # Log summary
        ready_providers = [name for name, ready in self._provider_ready.items() if ready]
        failed_providers = [name for name, ready in self._provider_ready.items() if not ready]
        
        logger.info(f"🎉 Aggregator initialization complete!")
        logger.info(f"✅ Ready providers: {ready_providers}")
        
        if failed_providers:
            logger.warning(f"⚠️ Failed providers: {failed_providers}")
        
        return initialization_results
    
    def _get_test_symbol_for_provider(self, provider_name: str) -> str:
        """Get appropriate test symbol for each provider"""
        test_symbols = {
            'binance': 'BTC',
            'mexc': 'BTC', 
            'ig_index': 'SPY',  # Use SPY since it worked in your tests
        }
        return test_symbols.get(provider_name, 'BTC')
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """
        MODIFIED - Get single price but handle both PriceData objects AND dicts
        """
        # Ensure aggregator is initialized (KEEP THIS - fixes timing issues)
        if not self._initialized:
            logger.warning("⚠️ Aggregator not initialized - initializing now...")
            await self.initialize()
        
        asset_type = self._detect_asset_type(symbol)
        providers = self._get_providers_for_symbol(symbol, asset_type)
        
        logger.debug(f"💰 Getting price for {symbol} using providers: {providers}")
        
        # Try each provider in order
        for provider_name in providers:
            if not self._provider_ready.get(provider_name, False):
                logger.debug(f"⏭️ Skipping {provider_name} - not ready")
                continue
                
            try:
                provider = self.providers[provider_name]
                logger.debug(f"🔍 Trying {provider_name} for {symbol}")
                
                result = await provider.get_price(symbol)
                
                if result:
                    # HANDLE BOTH PriceData objects AND dictionaries
                    if isinstance(result, PriceData):
                        # It's already a PriceData object - return it
                        logger.debug(f"✅ {provider_name} returned PriceData for {symbol}")
                        return result
                    elif isinstance(result, dict):
                        # It's a dictionary - convert to PriceData (no price manipulation here)
                        logger.debug(f"✅ {provider_name} returned dict for {symbol}")
                        return PriceData(
                            symbol=result.get('symbol', symbol),
                            asset_type=AssetType.EQUITY,
                            price=result.get('price', 0),  # Use price as-is from IG provider (already normalized)
                            change_percent=result.get('change_percent', 0),
                            change_absolute=result.get('change_absolute', 0),
                            volume=result.get('volume'),
                            market_cap=result.get('market_cap'),
                            timestamp=datetime.utcnow(),
                            source=result.get('source', provider_name)
                        )
                    else:
                        logger.warning(f"⚠️ {provider_name} returned unexpected type: {type(result)}")
                else:
                    logger.debug(f"⚠️ {provider_name} returned no data for {symbol}")
                    
            except Exception as e:
                logger.warning(f"❌ {provider_name} failed for {symbol}: {e}")
                continue
        
        logger.warning(f"💔 No provider could fetch {symbol}")
        return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[PriceData]:
        """
        Get prices for multiple symbols efficiently
        
        Args:
            symbols: List of symbol strings
            
        Returns:
            List of PriceData objects for successful requests
        """
        if not symbols:
            return []
        
        # Ensure aggregator is initialized
        if not self._initialized:
            logger.warning("⚠️ Aggregator not initialized for bulk request - initializing now...")
            await self.initialize()
        
        logger.info(f"📦 Bulk price request for {len(symbols)} symbols: {symbols}")
        
        results = []
        failed_symbols = []
        
        # Process symbols concurrently but with reasonable limits
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def get_single_with_semaphore(symbol):
            async with semaphore:
                try:
                    price_data = await self.get_price(symbol)
                    if price_data:
                        return symbol, price_data
                    else:
                        failed_symbols.append(symbol)
                        return symbol, None
                except Exception as e:
                    logger.warning(f"❌ Bulk request failed for {symbol}: {e}")
                    failed_symbols.append(symbol)
                    return symbol, None
        
        # Create tasks for all symbols
        tasks = [get_single_with_semaphore(symbol) for symbol in symbols]
        
        try:
            # Execute all requests concurrently
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in task_results:
                if isinstance(result, tuple) and len(result) == 2:
                    symbol, price_data = result
                    if price_data:
                        results.append(price_data)
                elif isinstance(result, Exception):
                    logger.warning(f"❌ Bulk request task failed: {result}")
        
        except Exception as e:
            logger.error(f"❌ Bulk request failed: {e}")
        
        success_count = len(results)
        total_count = len(symbols)
        
        logger.info(f"📊 Bulk request complete: {success_count}/{total_count} successful")
        
        if failed_symbols:
            logger.warning(f"⚠️ Failed symbols: {failed_symbols}")
        
        return results
    
    def _get_providers_for_symbol(self, symbol: str, asset_type: AssetType) -> List[str]:
        """Get ordered list of providers for a symbol"""
        # Get base priority list
        base_providers = self.provider_priority.get(asset_type, ['ig_index'])
        
        # Filter to only ready providers
        available_providers = [p for p in base_providers if self._provider_ready.get(p, False)]
        
        if not available_providers:
            # Fall back to any ready provider
            available_providers = [name for name, ready in self._provider_ready.items() if ready]
        
        return available_providers
    
    def _detect_asset_type(self, symbol: str) -> AssetType:
        """Detect asset type from symbol"""
        symbol_upper = symbol.upper()
        
        # Crypto detection
        crypto_symbols = ['BTC', 'ETH', 'SOL', 'AVAX', 'MATIC', 'ADA', 'DOT', 'LINK']
        if symbol_upper in crypto_symbols or 'USD' in symbol_upper:
            return AssetType.CRYPTO
        
        # Forex detection  
        forex_pairs = ['EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
        if any(pair in symbol_upper for pair in forex_pairs) and '=' in symbol_upper:
            return AssetType.FOREX
        
        # Index detection
        index_symbols = ['SPY', 'QQQ', 'VIX', 'DJI', 'IXIC']
        if symbol_upper in index_symbols or symbol_upper.startswith('^'):
            return AssetType.INDEX
        
        # Commodity detection
        if any(comm in symbol_upper for comm in ['=F', 'GC=', 'CL=', 'NG=', 'GOLD', 'OIL']):
            return AssetType.COMMODITY
        
        # Default to equity
        return AssetType.EQUITY
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all providers"""
        results = {}
        
        # If not initialized, try to initialize first
        if not self._initialized:
            await self.initialize()
        
        # Check each provider
        for name, provider in self.providers.items():
            try:
                if hasattr(provider, 'health_check'):
                    results[name] = await provider.health_check()
                else:
                    # Use ready status if no health check method
                    results[name] = self._provider_ready.get(name, False)
            except Exception as e:
                logger.debug(f"Health check failed for {name}: {e}")
                results[name] = False
        
        return results
    
    def get_initialization_status(self) -> Dict[str, any]:
        """Get detailed initialization status"""
        return {
            "initialized": self._initialized,
            "provider_ready": self._provider_ready.copy(),
            "ready_count": sum(1 for ready in self._provider_ready.values() if ready),
            "total_providers": len(self._provider_ready)
        }