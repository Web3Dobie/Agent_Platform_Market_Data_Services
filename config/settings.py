# config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Service configuration
    host: str = "0.0.0.0"
    port: int = 8001
    workers: int = 1
    log_level: str = "INFO"
    
    # Redis configuration
    redis_url: str = "redis://localhost:6379"
    
    # IG Index Configuration
    ig_username: Optional[str] = None
    ig_password: Optional[str] = None
    ig_api_key: Optional[str] = None
    ig_acc_type: str = "LIVE"  # DEMO or LIVE
    
    # Other API Keys
    finnhub_api_key: Optional[str] = None
    
    # Telegram Configuration
    tg_bot_token: Optional[str] = None
    tg_chat_id: Optional[str] = None
    telegram_enabled: bool = True  # Can be disabled via env var
    
    # Cache TTL (seconds)
    crypto_cache_ttl: int = 60      # 1 minute for crypto
    traditional_cache_ttl: int = 300 # 5 minutes for traditional assets
    news_cache_ttl: int = 900       # 15 minutes for news
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # IMPORTANT: Allows extra fields in .env

settings = Settings()