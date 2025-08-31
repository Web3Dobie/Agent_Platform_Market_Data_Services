# services/cache_service.py - Corrected with generic, synchronous logic

import redis # Use the synchronous library
import json
import logging
from typing import Optional, Any
from config.settings import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.redis = None
        self.connect() # Connect immediately on initialization

    def connect(self):
        """Initialize Redis connection synchronously."""
        if self.redis:
            return
        try:
            # Use the standard synchronous from_url
            self.redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True # This is important
            )
            self.redis.ping()
            logger.info("✅ Synchronous Redis connection established")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.redis = None

    def get(self, key: str) -> Optional[Any]:
        """Get any JSON-serializable data from the cache."""
        if not self.redis:
            return None
        
        try:
            data = self.redis.get(key)
            if data:
                # Return the parsed JSON data (e.g., a dictionary)
                return json.loads(data)
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
        
        return None

    def set(self, key: str, value: Any, ttl: int):
        """Cache any JSON-serializable data with TTL."""
        if not self.redis:
            return
        
        try:
            # Convert the value (e.g., a dictionary) to a JSON string
            data_to_cache = json.dumps(value)
            self.redis.setex(key, ttl, data_to_cache)
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")

    def health_check(self) -> bool:
        """Check if Redis is healthy."""
        if not self.redis:
            return False
        try:
            self.redis.ping()
            return True
        except Exception:
            return False