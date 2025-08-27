# config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional
import os

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

DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'agents_platform'),
    'user': os.getenv('DB_USER', 'admin'),
    'password': os.getenv('DB_PASSWORD', 'secure_agents_password')
}

# Only require SSL for remote connections
# host.docker.internal should be treated as local
if DATABASE_CONFIG['host'] not in ['localhost', '127.0.0.1', 'host.docker.internal']:
    DATABASE_CONFIG['sslmode'] = 'require'

settings = Settings()