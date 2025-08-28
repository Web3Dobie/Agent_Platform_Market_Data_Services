# services/aggregator.py - Enhanced with Finnhub integration and improved reliability

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from .data_providers.binance import BinanceProvider
from .data_providers.mexc import MEXCProvider  
from .data_providers.ig_index import IGIndexProvider
from .data_providers.finnhub import FinnhubProvider
from app.models import PriceData, AssetType

logger = logging.getLogger(__name__)

class DataAggregator:
    """
    Enhanced DataAggregator with Finnhub news integration and improved reliability
    """
    
    def __init__(self):
        # Initialize all providers
        self.providers = {
            'binance': BinanceProvider(),
            'mexc': MEXCProvider(),
            'ig_index': IGIndexProvider(),
            'finnhub': FinnhubProvider(),  # NEW - News and calendar data
        }
        
        # Track initialization and health status
        self._initialized = False
        self._provider_ready = {
            'binance': False,
            'mexc': False, 
            'ig_index': False,
            'finnhub': False,
        }
        
        # Provider priority for price data (Finnhub doesn't provide prices)
        self.provider_priority = {
            AssetType.CRYPTO: ['binance', 'mexc'],
            AssetType.FOREX: ['ig_index'],
            AssetType.EQUITY: ['ig_index'],
            AssetType.INDEX: ['ig_index'],
            AssetType.COMMODITY: ['ig_index']
        }
        
        # Request statistics for monitoring
        self._request_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'provider_stats': {name: {'requests': 0, 'successes': 0} for name in self.providers.keys()}
        }
        
        logger.info("Data Aggregator initialized with enhanced reliability and Finnhub news")
        logger.info("Providers: Binance, MEXC, IG Index (prices) + Finnhub (news/calendar)")
    
    async def initialize(self):
        """
        Enhanced provider initialization with better error handling and parallel processing
        """
        logger.info("Starting enhanced provider initialization...")
        
        initialization_results = {}
        initialization_tasks = []
        
        # Create initialization tasks for parallel execution
        for name, provider in self.providers.items():
            task = self._initialize_provider(name, provider)
            initialization_tasks.append(task)
        
        # Execute all initializations in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*initialization_tasks, return_exceptions=True),
                timeout=60.0  # 60 second total timeout for all providers
            )
            
            # Process results
            for i, (name, provider) in enumerate(self.providers.items()):
                result = results[i]
                if isinstance(result, Exception):
                    logger.error(f"Provider {name} initialization failed: {result}")
                    initialization_results[name] = f"error: {str(result)}"
                else:
                    initialization_results[name] = result
                    
        except asyncio.TimeoutError:
            logger.error("Provider initialization timed out after 60 seconds")
            for name in self.providers.keys():
                if name not in initialization_results:
                    initialization_results[name] = "timeout"
        
        # Mark as initialized regardless of individual provider status
        self._initialized = True
        
        # Log comprehensive summary
        ready_providers = [name for name, ready in self._provider_ready.items() if ready]
        failed_providers = [name for name, ready in self._provider_ready.items() if not ready]
        
        logger.info("Provider initialization complete:")
        logger.info(f"  Ready providers: {ready_providers}")
        
        if failed_providers:
            logger.warning(f"  Failed providers: {failed_providers}")
            logger.info("Service will continue with available providers")
        
        # Log provider capabilities
        price_providers = [p for p in ready_providers if p != 'finnhub']
        news_available = 'finnhub' in ready_providers
        
        logger.info(f"  Price data: {len(price_providers)} providers available")
        logger.info(f"  News data: {'Available' if news_available else 'Not available'}")
        
        return initialization_results
    
    async def _initialize_provider(self, name: str, provider) -> str:
        """Initialize a single provider with comprehensive testing"""
        logger.debug(f"Initializing {name} provider...")
        
        try:
            # Step 1: Run provider's initialize method if available
            if hasattr(provider, 'initialize'):
                init_result = await provider.initialize()
                if init_result is False:  # Explicit False means initialization failed
                    return "initialization_failed"
                logger.debug(f"{name} initialize() completed")
            
            # Step 2: Health check
            if hasattr(provider, 'health_check'):
                health_result = await provider.health_check()
                if not health_result:
                    logger.warning(f"{name} health check failed")
                    return "health_check_failed"
                logger.debug(f"{name} health check passed")
            
            # Step 3: Functional test based on provider type
            if name == 'finnhub':
                # Test news functionality
                test_result = await self._test_news_provider(provider)
                if test_result:
                    self._provider_ready[name] = True
                    logger.info(f"{name} news provider ready")
                    return "ready"
                else:
                    logger.warning(f"{name} functional test failed")
                    return "functional_test_failed"
            else:
                # Test price functionality for other providers
                test_result = await self._test_price_provider(name, provider)
                if test_result:
                    self._provider_ready[name] = True
                    logger.info(f"{name} price provider ready")
                    return "ready"
                else:
                    logger.warning(f"{name} functional test failed")
                    return "functional_test_failed"
                    
        except asyncio.TimeoutError:
            logger.error(f"{name} initialization timed out")
            return "timeout"
        except Exception as e:
            logger.error(f"{name} initialization error: {e}")
            return f"error: {str(e)}"
    
    async def _test_price_provider(self, name: str, provider) -> bool:
        """Test price provider with a simple request"""
        try:
            # Test with common symbols based on provider type
            test_symbols = {
                'binance': 'BTC',
                'mexc': 'WAI', 
                'ig_index': 'SPY'  # S&P 500
            }
            
            test_symbol = test_symbols.get(name, 'BTCUSDT')
            
            # Timeout for individual provider test
            result = await asyncio.wait_for(
                provider.get_price(test_symbol),
                timeout=10.0
            )
            
            if result and hasattr(result, 'price') and result.price > 0:
                logger.debug(f"{name} test successful: {test_symbol} = ${result.price:.2f}")
                return True
            else:
                logger.debug(f"{name} test returned invalid data")
                return False
                
        except asyncio.TimeoutError:
            logger.debug(f"{name} test timed out")
            return False
        except Exception as e:
            logger.debug(f"{name} test failed: {e}")
            return False
    
    async def _test_news_provider(self, provider) -> bool:
        """Test Finnhub provider with a simple request"""
        try:
            # Test with a simple market news request
            result = await asyncio.wait_for(
                provider.get_market_news(limit=1),
                timeout=15.0  # Longer timeout for news API
            )
            
            if isinstance(result, list):
                logger.debug(f"Finnhub test successful: got {len(result)} news items")
                return True
            else:
                logger.debug("Finnhub test returned invalid data")
                return False
                
        except asyncio.TimeoutError:
            logger.debug("Finnhub test timed out")
            return False
        except Exception as e:
            logger.debug(f"Finnhub test failed: {e}")
            return False
    
    async def health_check(self) -> Dict[str, bool]:
        """
        Enhanced health check with detailed provider status
        """
        if not self._initialized:
            logger.warning("Health check called before initialization")
            return {name: False for name in self.providers.keys()}
        
        results = {}
        
        # Run health checks in parallel with timeout
        health_tasks = []
        for name, provider in self.providers.items():
            if hasattr(provider, 'health_check'):
                task = self._check_provider_health(name, provider)
            else:
                # Assume healthy if no health check method
                task = asyncio.create_task(asyncio.sleep(0, result=(name, True)))
            health_tasks.append(task)
        
        try:
            health_results = await asyncio.wait_for(
                asyncio.gather(*health_tasks, return_exceptions=True),
                timeout=30.0
            )
            
            # Process results
            for i, (name, _) in enumerate(self.providers.items()):
                result = health_results[i]
                if isinstance(result, Exception):
                    results[name] = False
                    logger.warning(f"Health check exception for {name}: {result}")
                elif isinstance(result, tuple):
                    provider_name, is_healthy = result
                    results[provider_name] = is_healthy
                else:
                    results[name] = False
                    
        except asyncio.TimeoutError:
            logger.error("Health check timed out")
            results = {name: False for name in self.providers.keys()}
        
        # Update provider ready status based on health check
        for name, is_healthy in results.items():
            if not is_healthy and self._provider_ready.get(name, False):
                logger.warning(f"Provider {name} failed health check - marking as not ready")
                self._provider_ready[name] = False
            elif is_healthy and not self._provider_ready.get(name, False):
                logger.info(f"Provider {name} recovered - marking as ready")
                self._provider_ready[name] = True
        
        return results
    
    async def _check_provider_health(self, name: str, provider) -> tuple:
        """Check health of a single provider"""
        try:
            health_result = await asyncio.wait_for(
                provider.health_check(),
                timeout=10.0
            )
            return (name, bool(health_result))
        except Exception as e:
            logger.debug(f"Health check failed for {name}: {e}")
            return (name, False)
    
    # PRICE DATA METHODS (Enhanced)
    # =============================================================================
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """
        Get single price with enhanced error handling and statistics tracking
        """
        self._request_stats['total_requests'] += 1
        
        asset_type = self._detect_asset_type(symbol)
        providers = self._get_providers_for_symbol(symbol, asset_type)
        
        logger.debug(f"Getting price for {symbol} (type: {asset_type}) - trying: {providers}")
        
        for provider_name in providers:
            if not self._provider_ready.get(provider_name, False):
                continue
            
            self._request_stats['provider_stats'][provider_name]['requests'] += 1
            
            try:
                provider = self.providers[provider_name]
                result = await asyncio.wait_for(
                    provider.get_price(symbol),
                    timeout=15.0
                )
                
                if result and hasattr(result, 'price') and result.price > 0:
                    self._request_stats['successful_requests'] += 1
                    self._request_stats['provider_stats'][provider_name]['successes'] += 1
                    
                    logger.debug(f"Price for {symbol}: ${result.price:.2f} from {provider_name}")
                    return result
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout getting price for {symbol} via {provider_name}")
                continue
            except Exception as e:
                logger.warning(f"Error getting price for {symbol} via {provider_name}: {e}")
                continue
        
        self._request_stats['failed_requests'] += 1
        logger.warning(f"Failed to get price for {symbol} from all available providers")
        return None
    
    async def get_bulk_prices(self, symbols: List[str], max_concurrent: int = 10) -> List[PriceData]:
        """
        Enhanced bulk price fetching with concurrency control and better error handling
        """
        if not symbols:
            return []
        
        logger.info(f"Fetching bulk prices for {len(symbols)} symbols (max concurrent: {max_concurrent})")
        
        results = []
        failed_symbols = []
        
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def get_single_with_semaphore(symbol: str):
            async with semaphore:
                try:
                    price_data = await self.get_price(symbol)
                    if price_data:
                        return symbol, price_data
                    else:
                        failed_symbols.append(symbol)
                        return symbol, None
                except Exception as e:
                    logger.warning(f"Bulk request failed for {symbol}: {e}")
                    failed_symbols.append(symbol)
                    return symbol, None
        
        # Create tasks for all symbols
        tasks = [get_single_with_semaphore(symbol) for symbol in symbols]
        
        try:
            # Execute all requests with overall timeout
            task_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=120.0  # 2 minute timeout for bulk operation
            )
            
            # Process results
            for result in task_results:
                if isinstance(result, tuple) and len(result) == 2:
                    symbol, price_data = result
                    if price_data:
                        results.append(price_data)
                elif isinstance(result, Exception):
                    logger.warning(f"Bulk request task failed: {result}")
        
        except asyncio.TimeoutError:
            logger.error("Bulk price request timed out")
        except Exception as e:
            logger.error(f"Bulk price request failed: {e}")
        
        success_count = len(results)
        total_count = len(symbols)
        
        logger.info(f"Bulk request complete: {success_count}/{total_count} successful")
        
        if failed_symbols:
            logger.warning(f"Failed symbols: {failed_symbols[:10]}{'...' if len(failed_symbols) > 10 else ''}")
        
        return results

    # EPIC discovery through markets endpoint
    #==============================================================================

    async def search_markets(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Delegates market search to the IG Index provider.
        """
        if 'ig_index' in self.providers:
            provider = self.providers['ig_index']
            # Ensure the provider has the method before calling it
            if hasattr(provider, 'search_markets'):
                return await provider.search_markets(search_term)
            else:
                self.logger.warning("ig_index provider does not have a search_markets method.")
                return []
        else:
            self.logger.warning("IG Index provider not available for market search.")
            return []
    
    # NEWS AND CALENDAR METHODS (New Finnhub Integration)
    # =============================================================================
    
    async def get_company_news(self, symbol: str, days: int = 1) -> List[Any]:
        """Get company news via Finnhub provider"""
        if not self._provider_ready.get('finnhub', False):
            logger.warning("Finnhub provider not ready for news")
            return []
        
        try:
            finnhub_provider = self.providers['finnhub']
            result = await asyncio.wait_for(
                finnhub_provider.get_company_news(symbol, days),
                timeout=30.0
            )
            logger.debug(f"Got {len(result)} news articles for {symbol}")
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting news for {symbol}")
            return []
        except Exception as e:
            logger.error(f"Error getting company news for {symbol}: {e}")
            return []
    
    async def get_market_news(self, category: str = "general", limit: int = 20) -> List[Any]:
        """Get market news via Finnhub provider"""
        if not self._provider_ready.get('finnhub', False):
            logger.warning("Finnhub provider not ready for news")
            return []
        
        try:
            finnhub_provider = self.providers['finnhub']
            result = await asyncio.wait_for(
                finnhub_provider.get_market_news(category, limit),
                timeout=30.0
            )
            logger.debug(f"Got {len(result)} market news articles")
            return result
        except asyncio.TimeoutError:
            logger.warning("Timeout getting market news")
            return []
        except Exception as e:
            logger.error(f"Error getting market news: {e}")
            return []
    
    async def get_ipo_calendar(self, days: int = 14) -> List[Any]:
        """Get IPO calendar via Finnhub provider"""
        if not self._provider_ready.get('finnhub', False):
            logger.warning("Finnhub provider not ready for calendar")
            return []
        
        try:
            finnhub_provider = self.providers['finnhub']
            result = await asyncio.wait_for(
                finnhub_provider.get_ipo_calendar(days),
                timeout=30.0
            )
            logger.debug(f"Got {len(result)} IPO calendar events")
            return result
        except asyncio.TimeoutError:
            logger.warning("Timeout getting IPO calendar")
            return []
        except Exception as e:
            logger.error(f"Error getting IPO calendar: {e}")
            return []
    
    async def get_earnings_calendar(self, days: int = 7) -> List[Any]:
        """Get earnings calendar via Finnhub provider"""
        if not self._provider_ready.get('finnhub', False):
            logger.warning("Finnhub provider not ready for calendar")
            return []
        
        try:
            finnhub_provider = self.providers['finnhub']
            result = await asyncio.wait_for(
                finnhub_provider.get_earnings_calendar(days),
                timeout=30.0
            )
            logger.debug(f"Got {len(result)} earnings calendar events")
            return result
        except asyncio.TimeoutError:
            logger.warning("Timeout getting earnings calendar")
            return []
        except Exception as e:
            logger.error(f"Error getting earnings calendar: {e}")
            return []
    
    # UTILITY AND MONITORING METHODS
    # =============================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics for monitoring"""
        total_requests = self._request_stats['total_requests']
        successful_requests = self._request_stats['successful_requests']
        
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': self._request_stats['failed_requests'],
            'success_rate': f"{success_rate:.1f}%",
            'provider_ready': dict(self._provider_ready),
            'provider_stats': dict(self._request_stats['provider_stats']),
            'initialized': self._initialized
        }
    
    async def close(self):
        """Clean up all providers"""
        logger.info("Closing all providers...")
        close_tasks = []
        
        for name, provider in self.providers.items():
            if hasattr(provider, 'close'):
                close_tasks.append(self._close_provider(name, provider))
        
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        logger.info("All providers closed")
    
    async def _close_provider(self, name: str, provider):
        """Close a single provider"""
        try:
            await provider.close()
            logger.debug(f"Closed {name} provider")
        except Exception as e:
            logger.warning(f"Error closing {name} provider: {e}")
    
    # HELPER METHODS
    # =============================================================================
    
    def _get_providers_for_symbol(self, symbol: str, asset_type: AssetType) -> List[str]:
        """Get ordered list of providers for a symbol (price providers only)"""
        base_providers = self.provider_priority.get(asset_type, ['ig_index'])
        
        # Filter to only ready price providers (exclude Finnhub)
        available_providers = [p for p in base_providers if self._provider_ready.get(p, False)]
        
        if not available_providers:
            # Fall back to any ready price provider
            price_providers = ['binance', 'mexc', 'ig_index']
            available_providers = [name for name in price_providers if self._provider_ready.get(name, False)]
        
        return available_providers
    
    def _detect_asset_type(self, symbol: str) -> AssetType:
        """Detect asset type from symbol"""
        symbol_upper = symbol.upper().replace("$", "")
        
        # Crypto detection
        crypto_symbols = ["BTC", "ETH", "SOL", "AVAX", "DOT", "ADA", "XRP", "DOGE", "MATIC", "LINK"]
        if any(crypto in symbol_upper for crypto in crypto_symbols):
            return AssetType.CRYPTO
        
        # Forex detection - look for currency pairs
        forex_pairs = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]
        if len(symbol_upper) >= 6 and any(fx in symbol_upper for fx in forex_pairs):
            return AssetType.FOREX
        
        # Index detection
        index_symbols = ["SPX", "SPY", "QQQ", "DJI", "VIX", "NASDAQ", "FTSE", "DAX", "CAC", "NIKKEI"]
        if any(idx in symbol_upper for idx in index_symbols):
            return AssetType.INDEX
        
        # Commodity detection
        commodity_symbols = ["GOLD", "SILVER", "OIL", "WTI", "BRENT", "GAS", "WHEAT", "CORN"]
        if any(comm in symbol_upper for comm in commodity_symbols):
            return AssetType.COMMODITY
        
        # Default to equity
        return AssetType.EQUITY