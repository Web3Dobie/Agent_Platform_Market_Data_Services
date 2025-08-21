import redis.asyncio as redis
import json
import logging
from typing import Optional, Any
from datetime import datetime, timedelta
from config.settings import settings
from app.models import PriceData, AssetType

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.redis = None
    
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.redis = None
    
    async def get(self, key: str) -> Optional[PriceData]:
        """Get cached price data"""
        if not self.redis:
            return None
        
        try:
            data = await self.redis.get(key)
            if data:
                parsed = json.loads(data)
                return PriceData(**parsed)
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
        
        return None
    
    async def set(self, key: str, price_data: PriceData, ttl: int):
        """Cache price data with TTL"""
        if not self.redis:
            return
        
        try:
            data = price_data.model_dump_json()
            await self.redis.setex(key, ttl, data)
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
    
    def get_ttl_for_asset(self, asset_type: AssetType) -> int:
        """Get appropriate TTL based on asset type"""
        if asset_type == AssetType.CRYPTO:
            return settings.crypto_cache_ttl
        else:
            return settings.traditional_cache_ttl
    
    async def health_check(self) -> bool:
        """Check if Redis is healthy"""
        if not self.redis:
            return False
        
        try:
            await self.redis.ping()
            return True
        except:
            return False