# services/data_providers/finnhub.py
"""
Finnhub data provider for news, market movers, and calendar events
Integrates with the existing market data service architecture
"""

import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from config.settings import settings

logger = logging.getLogger(__name__)

@dataclass
class NewsArticle:
    """News article data model"""
    headline: str
    summary: str
    url: str
    source: str
    timestamp: datetime
    symbol: Optional[str] = None
    
@dataclass  
class MarketMover:
    """Market mover data model"""
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: Optional[int] = None

@dataclass
class CalendarEvent:
    """Calendar event data model (IPO/Earnings)"""
    symbol: str
    event_type: str  # 'ipo' or 'earnings'
    date: datetime
    description: str
    estimate: Optional[float] = None
    actual: Optional[float] = None

class FinnhubProvider:
    """
    Finnhub API provider for news, market movers, and calendar data
    Designed to integrate with existing market data service patterns
    """
    
    def __init__(self):
        self.api_key = settings.finnhub_api_key
        self.base_url = "https://finnhub.io/api/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        self._initialized = False
        
        if not self.api_key:
            logger.warning("Finnhub API key not configured - news functionality disabled")
        
        logger.info("📰 Finnhub provider initialized")
    
    async def initialize(self):
        """Initialize the provider with connection testing"""
        if not self.api_key:
            logger.warning("Finnhub API key missing - skipping initialization")
            return False
            
        try:
            # Create session with proper headers
            self.session = aiohttp.ClientSession(
                headers={
                    'X-Finnhub-Token': self.api_key,
                    'User-Agent': 'HedgeFundAgent/1.0'
                },
                timeout=aiohttp.ClientTimeout(total=30)
            )
            
            # Test connection with a simple API call
            await self.health_check()
            self._initialized = True
            logger.info("✅ Finnhub provider initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Finnhub initialization failed: {e}")
            await self.close()
            return False
    
    async def health_check(self) -> bool:
        """Check if Finnhub API is accessible"""
        if not self.api_key or not self.session:
            return False
            
        try:
            # Simple API test - get market status
            url = f"{self.base_url}/stock/market-status?exchange=US"
            async with self.session.get(url) as response:
                if response.status == 200:
                    logger.debug("✅ Finnhub health check passed")
                    return True
                else:
                    logger.warning(f"⚠️ Finnhub health check failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.warning(f"⚠️ Finnhub health check error: {e}")
            return False
    
    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
            self.session = None
    
    # =============================================================================
    # NEWS METHODS
    # =============================================================================
    
    async def get_company_news(self, symbol: str, days: int = 1) -> List[NewsArticle]:
        """
        Get company-specific news for a symbol
        """
        if not self._initialized or not self.session:
            logger.warning("Finnhub provider not initialized")
            return []
        
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # FIX: Format dates as YYYY-MM-DD strings for the API
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            url = f"{self.base_url}/company-news"
            params = {
                'symbol': symbol.upper(),
                'from': start_date_str, # Use corrected string format
                'to': end_date_str     # Use corrected string format
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Finnhub news API error {response.status} for {symbol}")
                    return []
                
                data = await response.json()
                
                # Process news articles
                articles = []
                for item in data[:10]:  # Limit to 10 most recent
                    try:
                        article = NewsArticle(
                            headline=item.get('headline', ''),
                            summary=item.get('summary', ''),
                            url=item.get('url', ''),
                            source=item.get('source', 'Unknown'),
                            timestamp=datetime.fromtimestamp(item.get('datetime', 0)),
                            symbol=symbol.upper()
                        )
                        
                        if article.headline:
                            articles.append(article)
                            
                    except Exception as e:
                        logger.debug(f"Error processing news item: {e}")
                        continue
                
                logger.info(f"📰 Found {len(articles)} news articles for {symbol}")
                return articles
                
        except Exception as e:
            logger.error(f"❌ Error fetching news for {symbol}: {e}")
            return []
    
    async def get_market_news(self, category: str = "general", limit: int = 20) -> List[NewsArticle]:
        """
        Get general market news
        
        Args:
            category: News category (general, forex, crypto, merger)
            limit: Maximum number of articles to return
            
        Returns:
            List of general market news articles
        """
        if not self._initialized or not self.session:
            logger.warning("Finnhub provider not initialized")
            return []
        
        try:
            url = f"{self.base_url}/news"
            params = {'category': category}
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Finnhub market news API error: {response.status}")
                    return []
                
                data = await response.json()
                
                articles = []
                for item in data[:limit]:
                    try:
                        article = NewsArticle(
                            headline=item.get('headline', ''),
                            summary=item.get('summary', ''),
                            url=item.get('url', ''),
                            source=item.get('source', 'Unknown'),
                            timestamp=datetime.fromtimestamp(item.get('datetime', 0))
                        )
                        
                        if article.headline:
                            articles.append(article)
                            
                    except Exception as e:
                        logger.debug(f"Error processing market news item: {e}")
                        continue
                
                logger.info(f"📰 Found {len(articles)} market news articles")
                return articles
                
        except Exception as e:
            logger.error(f"❌ Error fetching market news: {e}")
            return []
    
    # =============================================================================
    # MARKET MOVERS METHODS
    # =============================================================================
    
    async def get_market_movers(self) -> Dict[str, List[MarketMover]]:
        """
        Get top market gainers and losers
        
        Returns:
            Dictionary with 'gainers' and 'losers' lists
        """
        if not self._initialized or not self.session:
            logger.warning("Finnhub provider not initialized") 
            return {'gainers': [], 'losers': []}
        
        try:
            # Get both gainers and losers concurrently
            gainers_task = self._get_movers_by_type('gainers')
            losers_task = self._get_movers_by_type('losers')
            
            gainers, losers = await asyncio.gather(gainers_task, losers_task)
            
            result = {
                'gainers': gainers,
                'losers': losers
            }
            
            logger.info(f"📈 Found {len(gainers)} gainers, {len(losers)} losers")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error fetching market movers: {e}")
            return {'gainers': [], 'losers': []}
    
    async def _get_movers_by_type(self, mover_type: str) -> List[MarketMover]:
        """
        Get movers by type (gainers/losers)
        
        Args:
            mover_type: 'gainers' or 'losers'
            
        Returns:
            List of MarketMover objects
        """
        try:
            url = f"{self.base_url}/stock/symbol"
            params = {
                'exchange': 'US',
                'mic': 'XNAS',  # NASDAQ
                'securityType': 'Common Stock',
                'currency': 'USD'
            }
            
            # Note: Finnhub doesn't have a direct movers endpoint
            # This is a placeholder that would need to be implemented
            # by getting stock prices and calculating changes
            # For now, return empty list and log the limitation
            
            logger.warning(f"📊 Finnhub movers endpoint not directly available - using fallback")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error fetching {mover_type}: {e}")
            return []
    
    # =============================================================================
    # CALENDAR METHODS  
    # =============================================================================
    
    async def get_ipo_calendar(self, days: int = 14) -> List[CalendarEvent]:
        """
        Get upcoming IPO calendar
        
        Args:
            days: Number of days to look ahead (default: 14)
            
        Returns:
            List of IPO calendar events
        """
        if not self._initialized or not self.session:
            logger.warning("Finnhub provider not initialized")
            return []
        
        try:
            # Calculate date range
            start_date = datetime.utcnow().date()
            end_date = start_date + timedelta(days=days)
            
            url = f"{self.base_url}/calendar/ipo"
            params = {
                'from': start_date.isoformat(),
                'to': end_date.isoformat()
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Finnhub IPO calendar API error: {response.status}")
                    return []
                
                data = await response.json()
                ipo_calendar = data.get('ipoCalendar', [])
                
                events = []
                for item in ipo_calendar:
                    try:
                        event = CalendarEvent(
                            symbol=item.get('symbol', ''),
                            event_type='ipo',
                            date=datetime.fromisoformat(item.get('date', '')),
                            description=f"IPO - {item.get('name', 'Unknown Company')}",
                        )
                        events.append(event)
                        
                    except Exception as e:
                        logger.debug(f"Error processing IPO item: {e}")
                        continue
                
                logger.info(f"📅 Found {len(events)} upcoming IPO events")
                return events
                
        except Exception as e:
            logger.error(f"❌ Error fetching IPO calendar: {e}")
            return []
    
    async def get_earnings_calendar(self, days: int = 7) -> List[CalendarEvent]:
        """
        Get upcoming earnings calendar
        
        Args:
            days: Number of days to look ahead (default: 7)
            
        Returns:
            List of earnings calendar events
        """
        if not self._initialized or not self.session:
            logger.warning("Finnhub provider not initialized")
            return []
        
        try:
            # Calculate date range
            start_date = datetime.utcnow().date()
            end_date = start_date + timedelta(days=days)
            
            url = f"{self.base_url}/calendar/earnings"
            params = {
                'from': start_date.isoformat(),
                'to': end_date.isoformat()
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Finnhub earnings calendar API error: {response.status}")
                    return []
                
                data = await response.json()
                earnings_calendar = data.get('earningsCalendar', [])
                
                events = []
                for item in earnings_calendar:
                    try:
                        event = CalendarEvent(
                            symbol=item.get('symbol', ''),
                            event_type='earnings',
                            date=datetime.fromisoformat(item.get('date', '')),
                            description=f"Earnings - EPS Est: ${item.get('epsEstimate', 'N/A')}",
                            estimate=item.get('epsEstimate')
                        )
                        events.append(event)
                        
                    except Exception as e:
                        logger.debug(f"Error processing earnings item: {e}")
                        continue
                
                logger.info(f"📅 Found {len(events)} upcoming earnings events")
                return events
                
        except Exception as e:
            logger.error(f"❌ Error fetching earnings calendar: {e}")
            return []
    
    # =============================================================================
    # CORE INDIVIDUAL METHODS FOR FLEXIBLE INTEGRATION
    # =============================================================================