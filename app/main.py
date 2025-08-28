# app/main.py
"""
Production Market Data Service with enhanced but safe Telegram integration
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.models import HealthResponse
from app.routers import prices, metadata, news, markets
from services.aggregator import DataAggregator
from services.data_providers.finnhub import FinnhubProvider
from services.telegram_notifier import (
    get_notifier, 
    notify_startup, 
    notify_error, 
    notify_health_issue
)
from config.settings import settings
from datetime import datetime
from typing import List, Dict, Any
import logging
import asyncio

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Global aggregator instance
aggregator = DataAggregator()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Market Data Service...")
    
    try:
        # Initialize aggregator
        await aggregator.initialize()
        logger.info("Market Data Service initialized")
        
        # Get provider list with improved error handling
        providers = []
        try:
            if hasattr(aggregator, 'providers') and aggregator.providers:
                providers = list(aggregator.providers.keys())
            else:
                # Fallback provider list
                providers = ['binance', 'yahoo', 'ig_index', 'mexc']
                logger.warning("Using fallback provider list")
        except Exception as e:
            logger.error(f"Error getting provider list: {e}")
            providers = ['unknown']
        
        # Send enhanced startup notification
        startup_success = notify_startup(settings.host, settings.port, providers)
        if startup_success:
            logger.info("Enhanced startup notification sent successfully")
        else:
            logger.warning("Startup notification failed - continuing anyway")
        
        # Start background heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat_background_task())
        logger.info("Heartbeat task started")
        
    except Exception as e:
        logger.error(f"Failed to start Market Data Service: {e}")
        notify_error("Service Startup", str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Market Data Service...")
    try:
        heartbeat_task.cancel()
        await heartbeat_task
    except:
        pass

async def heartbeat_background_task():
    """Background heartbeat task with enhanced monitoring"""
    while True:
        try:
            await asyncio.sleep(1800)  # 30 minutes
            
            # Check system health
            services = await aggregator.health_check()
            healthy_count = sum(1 for status in services.values() if status)
            total_count = len(services)
            
            # Get enhanced stats
            notifier = get_notifier()
            stats = notifier.get_stats()
            
            # Send appropriate notification based on health
            if healthy_count == total_count:
                # All healthy - send heartbeat
                heartbeat_msg = f"System Heartbeat\nAll {total_count} providers healthy\nRequests: {stats['total_requests']} | Success: {stats['success_rate']}"
                notifier.send_message(heartbeat_msg)
                logger.info("Heartbeat sent - all systems healthy")
            else:
                # Some issues - send health warning
                failed_providers = [k for k, v in services.items() if not v]
                notify_health_issue(
                    "Heartbeat Check", 
                    f"Providers down: {', '.join(failed_providers)} ({total_count-healthy_count}/{total_count})"
                )
                logger.warning(f"Heartbeat detected issues: {len(failed_providers)} providers down")
            
        except asyncio.CancelledError:
            logger.info("Heartbeat task cancelled")
            break
            
        except Exception as e:
            logger.error(f"Heartbeat task error: {e}")
            try:
                notify_error("Heartbeat Task", str(e))
            except:
                pass  # Don't let notification errors break heartbeat
            # Continue the loop

app = FastAPI(
    title="Market Data Service",
    version="1.0.0",
    description="High-performance market data API with enhanced Telegram monitoring",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Dependency injection
async def get_aggregator() -> DataAggregator:
    return aggregator

# Include routers with API prefix
app.include_router(prices.router, prefix="/api/v1")
app.include_router(metadata.router, prefix="/api/v1")
app.include_router(news.router, prefix="/api/v1")
app.include_router(markets.router, prefix="/api/v1")

# Get the initialized finnhub instance from the aggregator
def get_initialized_finnhub() -> FinnhubProvider:
    return aggregator.providers['finnhub']

# Override the dependency AFTER including the routers
app.dependency_overrides[prices.get_aggregator] = get_aggregator
app.dependency_overrides[metadata.get_aggregator] = get_aggregator
app.dependency_overrides[news.get_finnhub] = get_initialized_finnhub
app.dependency_overrides[markets.get_aggregator] = get_aggregator

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Enhanced service health check"""
    try:
        services = await aggregator.health_check()
        healthy_count = sum(1 for status in services.values() if status)
        total_count = len(services)
        
        # Determine status
        if healthy_count == total_count:
            status = "healthy"
        elif healthy_count > 0:
            status = "degraded"
        else:
            status = "unhealthy"
        
        # Notify on significant issues
        if status == "degraded":
            failed_providers = [k for k, v in services.items() if not v]
            notify_health_issue(
                "Service Degraded", 
                f"Failed: {', '.join(failed_providers)} ({total_count-healthy_count}/{total_count})"
            )
        elif status == "unhealthy":
            notify_health_issue("Service Unhealthy", "All providers failed")
        
        return HealthResponse(
            status=status,
            timestamp=datetime.utcnow(),
            services=services
        )
        
    except Exception as e:
        notify_error("Health Check", str(e))
        raise HTTPException(status_code=500, detail="Health check failed")

@app.get("/")
async def root():
    """Root endpoint with enhanced service information"""
    notifier = get_notifier()
    stats = notifier.get_stats()
    
    return {
        "service": "Market Data Service",
        "version": "1.0.0",
        "status": "running",
        "telegram": {
            "enabled": stats["enabled"],
            "version": stats["version"],
            "total_requests": stats["total_requests"],
            "failed_requests": stats["failed_requests"],
            "success_rate": stats["success_rate"],
            "features": stats["features"]
        },
        "endpoints": {
            "health": "/health",
            "search_markets": "/api/v1/markets/search/{search_term}",
            "single_price": "/api/v1/prices/{symbol}",
            "bulk_prices": "/api/v1/prices/bulk", 
            "major_crypto": "/api/v1/prices/crypto/major",
            "provider_status": "/api/v1/prices/status/providers",
            "metadata_by_epic": "/api/v1/metadata/{epic}",
            "metadata_by_symbol": "/api/v1/metadata/symbol/{symbol}",
            "database_symbols": "/api/v1/metadata/database/symbols",
            "company_news": "/api/v1/news/company/{symbol}",
            "market_news": "/api/v1/news/market",
            "ipo_calendar": "/api/v1/calendar/ipo",
            "earnings_calendar": "/api/v1/calendar/earnings",
            "telegram_status": "/telegram/status",
            "telegram_test": "/telegram/test"
        }
    }

@app.get("/telegram/status")
async def telegram_status():
    """Get enhanced Telegram status"""
    notifier = get_notifier()
    stats = notifier.get_stats()
    
    return {
        "telegram_notifier": stats,
        "configuration": {
            "bot_token_configured": bool(notify_startup.__module__),
            "chat_id_configured": stats["enabled"]
        },
        "capabilities": {
            "markdown_v2_support": True,
            "automatic_fallback": True,
            "safe_character_escaping": True,
            "enhanced_formatting": True
        }
    }

@app.post("/telegram/test")
async def test_telegram(message: str = "Enhanced test message with special chars: *bold* _italic_ `code` & symbols!"):
    """Test enhanced Telegram functionality"""
    notifier = get_notifier()
    
    if not notifier.enabled:
        return {
            "success": False,
            "message": "Telegram not configured",
            "help": "Set TG_BOT_TOKEN and TG_CHAT_ID environment variables"
        }
    
    try:
        # Build enhanced test message
        from services.telegram_notifier import build_safe_message, NotificationLevel
        
        test_message = build_safe_message(
            emoji="test",
            title="Enhanced Test Message", 
            body=message,
            fields={
                "Test Type": "API Test",
                "Special Characters": "Testing: *bold* _italic_ `code` [link] & more!",
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )
        
        success = notifier.send_message(test_message, NotificationLevel.INFO)
        
        return {
            "success": success,
            "message": "Enhanced test sent" if success else "Test failed",
            "features_used": ["markdown_v2", "safe_escaping", "structured_message"],
            "stats": notifier.get_stats()
        }
        
    except Exception as e:
        logger.error(f"Test error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Test failed with exception"
        }

@app.post("/telegram/heartbeat")
async def manual_heartbeat():
    """Trigger manual heartbeat"""
    try:
        # Get system status
        services = await aggregator.health_check()
        healthy_count = sum(1 for status in services.values() if status)
        total_count = len(services)
        
        # Get stats
        notifier = get_notifier()
        stats = notifier.get_stats()
        
        # Send heartbeat
        if healthy_count == total_count:
            heartbeat_msg = f"Manual Heartbeat\nAll {total_count} providers healthy\nRequests: {stats['total_requests']} | Success: {stats['success_rate']}"
            success = notifier.send_message(heartbeat_msg)
            
            return {
                "success": success,
                "status": "healthy",
                "message": "Manual heartbeat sent",
                "provider_stats": f"{healthy_count}/{total_count} healthy"
            }
        else:
            failed_providers = [k for k, v in services.items() if not v]
            notify_health_issue(
                "Manual Heartbeat", 
                f"Failed: {', '.join(failed_providers)}"
            )
            
            return {
                "success": True,
                "status": "degraded", 
                "failed_providers": failed_providers,
                "provider_stats": f"{healthy_count}/{total_count} healthy"
            }
            
    except Exception as e:
        notify_error("Manual Heartbeat", str(e))
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        log_level=settings.log_level.lower()
    )