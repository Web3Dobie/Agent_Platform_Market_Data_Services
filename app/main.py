from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.models import HealthResponse
from app.routers import prices
from services.aggregator import DataAggregator
from config.settings import settings
from datetime import datetime
import logging

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
    logger.info("🚀 Starting Market Data Service...")
    await aggregator.initialize()
    logger.info("✅ Market Data Service initialized")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Market Data Service...")

app = FastAPI(
    title="Market Data Service",
    version="1.0.0",
    description="High-performance market data API with intelligent caching",
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

# Include routers
app.include_router(prices.router)    

# CRITICAL: Override the dependency AFTER including the router
app.dependency_overrides[prices.get_aggregator] = get_aggregator

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check"""
    services = await aggregator.health_check()
    
    # Determine overall status
    status = "healthy" if all(services.values()) else "degraded"
    
    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        services=services
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Market Data Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "single_price": "/prices/{symbol}",
            "bulk_prices": "/prices/bulk",
            "major_crypto": "/prices/crypto/major"
        }
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