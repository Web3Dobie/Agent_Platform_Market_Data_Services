# services/aggregator.py (NO YAHOO FINANCE API CALLS)
"""
Market data aggregator WITHOUT Yahoo Finance to let rate limits reset
Uses only Binance, MEXC, and IG Index - no Yahoo API calls whatsoever
"""

import asyncio
import logging
from typing import List, Optional, Dict
from datetime import datetime

from .data_providers.binance import BinanceProvider
from .data_providers.mexc import MEXCProvider  
from .data_providers.ig_index import IGIndexProvider
# REMOVED: Yahoo Finance import to prevent any API calls
# from .data_providers.yahoo_finance import YahooFinanceProvider
from app.models import PriceData, AssetType

logger = logging.getLogger(__name__)

class DataAggregator:
    """
    Market data aggregator WITHOUT Yahoo Finance
    Prevents any Yahoo API calls to let rate limits reset over weekend
    """
    
    def __init__(self):
        # Initialize only working providers (NO YAHOO)
        self.providers = {
            'binance': BinanceProvider(),
            'mexc': MEXCProvider(),
            'ig_index': IGIndexProvider(),
            # 'yahoo': REMOVED to prevent API calls
        }
        
        # Provider priority WITHOUT Yahoo Finance
        self.provider_priority = {
            AssetType.CRYPTO: ['binance', 'mexc'],
            AssetType.FOREX: ['ig_index'],      # IG Index handles forex
            AssetType.EQUITY: ['ig_index'],     # IG Index fallback for equities
            AssetType.INDEX: ['ig_index'],      # IG Index excellent for indices  
            AssetType.COMMODITY: ['ig_index']   # IG Index handles commodities
        }
        
        logger.info("📊 Data Aggregator initialized WITHOUT Yahoo Finance")
        logger.info("🚫 Yahoo Finance disabled to allow rate limit reset")
    
    async def initialize(self):
        """Initialize services without Yahoo"""
        logger.info("✅ Aggregator initialized (Yahoo Finance disabled)")
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get single price WITHOUT Yahoo Finance"""
        asset_type = self._detect_asset_type(symbol)
        providers = self._get_providers_for_symbol(symbol, asset_type)
        
        logger.debug(f"💰 Getting price for {symbol} (type: {asset_type}) - providers: {providers}")
        
        for provider_name in providers:
            try:
                provider = self.providers[provider_name]
                result = await provider.get_price(symbol)
                
                if result:
                    logger.debug(f"✅ Price found for {symbol} via {provider_name}: ${result.price}")
                    return result
                    
            except Exception as e:
                logger.warning(f"⚠️ Provider {provider_name} failed for {symbol}: {e}")
                continue
        
        logger.warning(f"❌ No price found for {symbol} after trying providers: {providers}")
        logger.info(f"💡 {symbol} may be available when Yahoo Finance is re-enabled")
        return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """
        Get bulk prices with intelligent routing
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
                provider = self.providers[provider_name]
                
                # Use bulk method if available
                if hasattr(provider, 'get_bulk_prices'):
                    provider_results = await provider.get_bulk_prices(provider_symbols)
                    
                    # Map results back to symbols
                    for symbol, result in zip(provider_symbols, provider_results):
                        results[symbol] = result
                else:
                    # Fallback to individual requests
                    for symbol in provider_symbols:
                        result = await provider.get_price(symbol)
                        results[symbol] = result
                        # Small delay between individual requests
                        await asyncio.sleep(0.1)
                        
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
    
    def _get_providers_for_symbol(self, symbol: str, asset_type: AssetType) -> List[str]:
        """Get optimal provider list WITHOUT Yahoo Finance"""
        symbol_upper = symbol.upper()
        
        # Crypto routing
        if asset_type == AssetType.CRYPTO:
            if any(token in symbol_upper for token in ['USDT', 'BTC', 'ETH']):
                return ['binance', 'mexc']
            else:
                return ['mexc', 'binance']
        
        # Everything else goes to IG Index (no Yahoo)
        # IG Index handles: forex, indices, commodities, some equities
        return ['ig_index']
    
    def _group_symbols_by_provider(self, symbols: List[str]) -> Dict[str, List[str]]:
        """Smart symbol grouping WITHOUT Yahoo Finance"""
        groups = {
            'binance': [],
            'mexc': [],
            'ig_index': [],
            # 'yahoo': REMOVED
        }
        
        for symbol in symbols:
            asset_type = self._detect_asset_type(symbol)
            providers = self._get_providers_for_symbol(symbol, asset_type)
            
            # Assign to primary provider
            primary_provider = providers[0]
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
            providers = self._get_providers_for_symbol(symbol, asset_type)
            
            # Try alternative providers
            for provider_name in providers[1:]:  # Skip primary provider
                if results[symbol] is not None:  # Already succeeded
                    break
                    
                try:
                    provider = self.providers[provider_name]
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
        if any(fx in symbol_upper for fx in ['USD=X', 'EUR', 'GBP', '=X']) or 'USD' in symbol_upper:
            return AssetType.FOREX
        
        # Index patterns
        if symbol_upper.startswith('^') or symbol_upper in ['SPY', 'QQQ', 'IWM', 'VIX', 'DXY']:
            return AssetType.INDEX
        
        # Commodity patterns
        if any(comm in symbol_upper for comm in ['=F', 'GC=', 'CL=', 'NG=', 'GOLD', 'OIL']):
            return AssetType.COMMODITY
        
        # Default to equity
        return AssetType.EQUITY
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all providers"""
        results = {}
        
        # Check providers
        for name, provider in self.providers.items():
            try:
                if hasattr(provider, 'health_check'):
                    results[name] = await provider.health_check()
                else:
                    # Simple test if no health_check method
                    test_symbol = self._get_test_symbol_for_provider(name)
                    test_result = await provider.get_price(test_symbol)
                    results[name] = test_result is not None
            except Exception as e:
                logger.debug(f"Health check failed for {name}: {e}")
                results[name] = False
        
        return results
    
    def _get_test_symbol_for_provider(self, provider_name: str) -> str:
        """Get appropriate test symbol for each provider (NO YAHOO)"""
        test_symbols = {
            'binance': 'BTC',
            'mexc': 'BTC', 
            'ig_index': 'EURUSD=X',  # Use forex for IG Index health check
            # 'yahoo': REMOVED
        }
        return test_symbols.get(provider_name, 'BTC')

# Weekend reactivation functions
def add_yahoo_finance_provider(aggregator: DataAggregator):
    """
    Function to re-add Yahoo Finance when rate limits reset
    Call this over the weekend to reactivate Yahoo
    """
    try:
        # Import only when needed
        from .data_providers.yahoo_finance_provider import YahooFinanceProvider
        
        # Add Yahoo back to providers
        aggregator.providers['yahoo'] = YahooFinanceProvider(enable_api_calls=True)
        
        # Update provider priority to include Yahoo
        aggregator.provider_priority[AssetType.EQUITY] = ['yahoo', 'ig_index']
        aggregator.provider_priority[AssetType.INDEX] = ['ig_index', 'yahoo'] 
        
        logger.info("🚀 Yahoo Finance re-enabled!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to re-enable Yahoo Finance: {e}")
        return False

def check_yahoo_finance_available() -> bool:
    """
    Test if Yahoo Finance rate limits have reset
    Returns True if Yahoo is working again
    """
    try:
        # Quick test without affecting aggregator
        import yfinance as yf
        import asyncio
        
        async def test_yahoo():
            try:
                # Test with a simple symbol
                ticker = yf.Ticker("AAPL")
                data = ticker.history(period="1d")
                return not data.empty
            except:
                return False
        
        # Run test
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(test_yahoo())
        
    except Exception as e:
        logger.error(f"Yahoo Finance test failed: {e}")
        return False

# Dependency injection function (for compatibility)
async def get_aggregator() -> DataAggregator:
    """Get market data aggregator instance"""
    return DataAggregator()