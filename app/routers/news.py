# app/routers/news.py
"""
News and calendar data API endpoints using Finnhub provider
Designed for briefings module integration
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from services.data_providers.finnhub import FinnhubProvider, NewsArticle, CalendarEvent
from services.cache_service import get_cache_service, CacheService

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["news"])

# Global provider instance (will be initialized by main.py)
finnhub_provider = FinnhubProvider()

async def get_finnhub() -> FinnhubProvider:
    """Dependency injection for Finnhub provider"""
    return finnhub_provider

# =============================================================================
# NEWS ENDPOINTS
# =============================================================================

@router.get("/news/company/{symbol}")
async def get_company_news(
    symbol: str,
    days: int = Query(default=1, ge=1, le=30, description="Days to look back"),
    cache: CacheService = Depends(get_cache_service),
    provider: FinnhubProvider = Depends(get_finnhub)
) -> Dict[str, Any]:
    """
    Get company-specific news for a symbol
    
    - **symbol**: Stock ticker symbol (e.g., AAPL, MSFT)
    - **days**: Number of days to look back (1-30)
    """
    symbol = symbol.upper()
    cache_key = f"news:company:{symbol}:{days}"
    
    # Check cache first (15 minute TTL)
    cached_result = await cache.get(cache_key)
    if cached_result:
        logger.debug(f"📰 Returning cached news for {symbol}")
        return cached_result
    
    try:
        articles = await provider.get_company_news(symbol, days=days)
        
        # Convert to dict format for JSON response
        result = {
            "symbol": symbol,
            "days_back": days,
            "articles_count": len(articles),
            "articles": [
                {
                    "headline": article.headline,
                    "summary": article.summary,
                    "url": article.url,
                    "source": article.source,
                    "timestamp": article.timestamp.isoformat(),
                    "symbol": article.symbol
                }
                for article in articles
            ]
        }
        
        # Cache result
        await cache.set(cache_key, result, ttl=900)  # 15 minutes
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error getting company news for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch news for {symbol}")

@router.get("/news/market")
async def get_market_news(
    category: str = Query(default="general", description="News category"),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum articles"),
    cache: CacheService = Depends(get_cache_service),
    provider: FinnhubProvider = Depends(get_finnhub)
) -> Dict[str, Any]:
    """
    Get general market news
    
    - **category**: News category (general, forex, crypto, merger)
    - **limit**: Maximum number of articles (1-50)
    """
    cache_key = f"news:market:{category}:{limit}"
    
    # Check cache first (15 minute TTL)
    cached_result = await cache.get(cache_key)
    if cached_result:
        logger.debug(f"📰 Returning cached market news")
        return cached_result
    
    try:
        articles = await provider.get_market_news(category=category, limit=limit)
        
        result = {
            "category": category,
            "articles_count": len(articles),
            "articles": [
                {
                    "headline": article.headline,
                    "summary": article.summary,
                    "url": article.url,
                    "source": article.source,
                    "timestamp": article.timestamp.isoformat()
                }
                for article in articles
            ]
        }
        
        # Cache result
        await cache.set(cache_key, result, ttl=900)  # 15 minutes
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error getting market news: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch market news")

# Removed bulk endpoint - keeping individual endpoints for flexibility


@router.get("/calendar/ipo")
async def get_ipo_calendar(
    days: int = Query(default=14, ge=1, le=30, description="Days to look ahead"),
    cache: CacheService = Depends(get_cache_service),
    provider: FinnhubProvider = Depends(get_finnhub)
) -> Dict[str, Any]:
    """
    Get upcoming IPO calendar
    
    - **days**: Number of days to look ahead (1-30)
    """
    cache_key = f"calendar:ipo:{days}"
    
    # Check cache first (1 hour TTL for calendar data)
    cached_result = await cache.get(cache_key)
    if cached_result:
        logger.debug(f"Returning cached IPO calendar")
        return cached_result
    
    try:
        events = await provider.get_ipo_calendar(days=days)
        
        result = {
            "days_ahead": days,
            "events_count": len(events),
            "events": [
                {
                    "symbol": event.symbol,
                    "date": event.date.isoformat(),
                    "description": event.description
                }
                for event in events
            ]
        }
        
        # Cache result (1 hour)
        await cache.set(cache_key, result, ttl=3600)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting IPO calendar: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch IPO calendar")

@router.get("/calendar/earnings")  
async def get_earnings_calendar(
    days: int = Query(default=7, ge=1, le=30, description="Days to look ahead"),
    cache: CacheService = Depends(get_cache_service),
    provider: FinnhubProvider = Depends(get_finnhub)
) -> Dict[str, Any]:
    """
    Get upcoming earnings calendar
    
    - **days**: Number of days to look ahead (1-30)
    """
    cache_key = f"calendar:earnings:{days}"
    
    # Check cache first (1 hour TTL)
    cached_result = await cache.get(cache_key)
    if cached_result:
        logger.debug(f"Returning cached earnings calendar")
        return cached_result
    
    try:
        events = await provider.get_earnings_calendar(days=days)
        
        result = {
            "days_ahead": days,
            "events_count": len(events),
            "events": [
                {
                    "symbol": event.symbol,
                    "date": event.date.isoformat(),
                    "description": event.description,
                    "estimate": event.estimate
                }
                for event in events
            ]
        }
        
        # Cache result (1 hour)
        await cache.set(cache_key, result, ttl=3600)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting earnings calendar: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch earnings calendar")