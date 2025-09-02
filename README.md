# Market Data Service

A high-performance, production-ready market data API service that aggregates financial data from multiple providers with intelligent failover, caching, and enhanced monitoring capabilities.

## 🚀 Features

### Core Functionality
- **Multi-Provider Data Aggregation**: Binance (crypto), MEXC (tokens), IG Index (stocks/indices/forex/commodities), Finnhub (news), FRED (macro data)
- **Intelligent Provider Selection**: Automatic routing based on asset type with failover mechanisms
- **Real-time Price Data**: Single and bulk price requests with normalized responses
- **Market Discovery**: Search and discover new symbols through IG Index API
- **News & Calendar Data**: Company news, market news, IPO calendar, earnings calendar
- **Macroeconomic Data**: Key economic indicators from FRED (GDP, CPI, unemployment, etc.)

### Advanced Features
- **Smart Caching**: Redis-based caching with configurable TTLs per asset type
- **Session Management**: Self-healing IG Index authentication with automatic reconnection
- **Symbol Normalization**: Dynamic symbol conversion with IG Index epic code generation
- **Database Integration**: PostgreSQL for symbol metadata and discovery tracking
- **Enhanced Monitoring**: Telegram notifications with markdown support and fallback mechanisms
- **Health Monitoring**: Comprehensive health checks and proactive session refresh

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Architecture](#architecture)
- [Development](#development)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## 🏁 Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd market-data-service

# Create environment file
cp .env.example .env
# Edit .env with your API keys and configuration

# Start the service
docker-compose up -d

# Check service health
curl http://localhost:8001/health
```

### Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export IG_USERNAME="your_ig_username"
export IG_PASSWORD="your_ig_password"
export IG_API_KEY="your_ig_api_key"
export FINNHUB_API_KEY="your_finnhub_key"
export FRED_API_KEY="your_fred_key"

# Start the service
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## ⚙️ Configuration

### Required Environment Variables

```bash
# IG Index (Primary data provider)
IG_USERNAME=your_ig_username
IG_PASSWORD=your_ig_password
IG_API_KEY=your_ig_api_key
IG_ACC_TYPE=DEMO  # or LIVE

# Optional APIs
FINNHUB_API_KEY=your_finnhub_key    # For news and calendar data
FRED_API_KEY=your_fred_key          # For macroeconomic data

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=agents_platform
DB_USER=admin
DB_PASSWORD=secure_agents_password

# Redis Cache
REDIS_URL=redis://localhost:6379

# Telegram Notifications (Optional)
TG_BOT_TOKEN=your_telegram_bot_token
TG_CHAT_ID=your_telegram_chat_id
```

### Cache Configuration

```bash
# Cache TTL settings (seconds)
CRYPTO_CACHE_TTL=60        # 1 minute for crypto
TRADITIONAL_CACHE_TTL=300  # 5 minutes for stocks/indices
NEWS_CACHE_TTL=900         # 15 minutes for news
MACRO_CACHE_TTL=86400      # 1 day for macro data
```

## 📚 API Documentation

### Price Data Endpoints

#### Get Single Price
```http
GET /api/v1/prices/{symbol}
```

**Examples:**
- `GET /api/v1/prices/AAPL` - Apple stock
- `GET /api/v1/prices/BTC` - Bitcoin
- `GET /api/v1/prices/SPY` - S&P 500 ETF

**Response:**
```json
{
  "symbol": "AAPL",
  "original_symbol": "$AAPL",
  "asset_type": "equity",
  "price": 150.25,
  "change_percent": 2.5,
  "change_absolute": 3.75,
  "volume": 45000000,
  "timestamp": "2025-01-01T12:00:00Z",
  "source": "ig_index",
  "normalization": {
    "ig_epic": "UA.D.AAPL.DAILY.IP",
    "confidence": 0.95,
    "detected_type": "stock"
  }
}
```

#### Get Bulk Prices
```http
POST /api/v1/prices/bulk
Content-Type: application/json

{
  "symbols": ["AAPL", "BTC", "SPY", "EURUSD"],
  "include_volume": true
}
```

#### Get Major Cryptocurrencies
```http
GET /api/v1/prices/crypto/major
```

### Market Discovery

#### Search Markets
```http
GET /api/v1/markets/search/apple
```

**Response:**
```json
[
  {
    "epic": "UA.D.AAPL.DAILY.IP",
    "instrumentName": "Apple Inc",
    "marketStatus": "TRADEABLE",
    "streamingPricesAvailable": true
  }
]
```

### News & Calendar Data

#### Company News
```http
GET /api/v1/news/company/AAPL?days=7
```

#### Market News
```http
GET /api/v1/news/market?category=general&limit=20
```

#### IPO Calendar
```http
GET /api/v1/calendar/ipo?days=14
```

#### Earnings Calendar
```http
GET /api/v1/calendar/earnings?days=7
```

### Macroeconomic Data

#### Get Economic Indicators
```http
GET /api/v1/macro/gdp        # GDP
GET /api/v1/macro/cpi        # Consumer Price Index
GET /api/v1/macro/unemployment # Unemployment Rate
GET /api/v1/macro/fedfunds   # Federal Funds Rate
```

**Response:**
```json
{
  "name": "Gross Domestic Product",
  "series_id": "GDP",
  "latest_value": 26854.6,
  "latest_date": "2024-Q3",
  "change_from_previous": 324.8,
  "percent_change_from_previous": 1.22,
  "percent_change_year_ago": 2.84,
  "history": [...]
}
```

### Metadata & Discovery

#### Get Symbol Metadata
```http
GET /api/v1/metadata/symbol/AAPL
```

#### Discover New Symbol
```http
POST /api/v1/metadata/discover/NVDA
```

#### Database Symbols
```http
GET /api/v1/metadata/database/symbols?asset_type=stock&limit=100
```

### System Endpoints

#### Health Check
```http
GET /health
```

#### Provider Status
```http
GET /api/v1/prices/status/providers
```

#### Telegram Status
```http
GET /telegram/status
```

## 🏗️ Architecture

### System Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   DataAggregator │    │   Data Providers│
│                 │    │                  │    │                 │
│ • Routers       │────│ • Provider       │────│ • IG Index      │
│ • Middleware    │    │   Selection      │    │ • Binance       │
│ • Dependencies  │    │ • Failover       │    │ • MEXC          │
│                 │    │ • Caching        │    │ • Finnhub       │
└─────────────────┘    └──────────────────┘    │ • FRED          │
                                               └─────────────────┘
           │                       │                       │
           ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      Redis       │    │   External APIs │
│                 │    │                  │    │                 │
│ • Symbol        │    │ • Price Cache    │    │ • IG Index API  │
│   Metadata      │    │ • News Cache     │    │ • Binance API   │
│ • Discovery     │    │ • Macro Cache    │    │ • Finnhub API   │
│   Tracking      │    │                  │    │ • FRED API      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Data Flow

1. **Request Processing**: FastAPI receives requests and validates inputs
2. **Symbol Normalization**: Dynamic conversion to provider-specific formats
3. **Provider Selection**: Intelligent routing based on asset type and availability
4. **Cache Check**: Redis cache lookup for recent data
5. **API Calls**: Fetch from external providers with failover
6. **Data Normalization**: Standardize response format
7. **Cache Storage**: Store results with appropriate TTL
8. **Response**: Return normalized data to client

### Provider Priority

| Asset Type | Primary | Secondary | Tertiary |
|------------|---------|-----------|----------|
| Crypto     | Binance | MEXC      | -        |
| Forex      | IG Index| -         | -        |
| Equity     | IG Index| -         | -        |
| Index      | IG Index| -         | -        |
| Commodity  | IG Index| -         | -        |

## 🔧 Development

### Project Structure

```
market-data-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # Pydantic models
│   └── routers/
│       ├── __init__.py
│       ├── prices.py        # Price endpoints
│       ├── metadata.py      # Symbol metadata
│       ├── news.py          # News & calendar
│       ├── markets.py       # Market search
│       └── macro.py         # Macroeconomic data
├── services/
│   ├── __init__.py
│   ├── aggregator.py        # Main data aggregator
│   ├── cache_service.py     # Redis caching
│   ├── database_service.py  # PostgreSQL operations
│   ├── symbol_normalizer.py # Symbol conversion
│   ├── telegram_notifier.py # Notifications
│   └── data_providers/
│       ├── __init__.py
│       ├── binance.py       # Binance API
│       ├── mexc.py          # MEXC API
│       ├── ig_index.py      # IG Index API
│       ├── finnhub.py       # Finnhub API
│       └── fred_service.py  # FRED API
├── config/
│   ├── __init__.py
│   ├── settings.py          # Configuration
│   └── rate_limits.py       # Rate limiting
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

### Adding New Providers

1. Create provider class in `services/data_providers/`
2. Implement required methods: `get_price()`, `health_check()`, `initialize()`
3. Add provider to `DataAggregator` in `services/aggregator.py`
4. Update provider priority mapping
5. Add tests and documentation

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=services --cov-report=html
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f market-data-service

# Scale service
docker-compose up -d --scale market-data-service=3
```

### Production Considerations

1. **Load Balancing**: Use nginx or cloud load balancer
2. **SSL/TLS**: Configure HTTPS with proper certificates  
3. **Database**: Use managed PostgreSQL service
4. **Redis**: Use managed Redis service with clustering
5. **Monitoring**: Set up Prometheus/Grafana or similar
6. **API Keys**: Use secure secret management
7. **Rate Limiting**: Implement proper rate limiting per client

### Environment Setup

```bash
# Production environment variables
ENVIRONMENT=production
LOG_LEVEL=INFO
WORKERS=4

# Database (use managed service)
DB_HOST=your-postgres-host
DB_PORT=5432

# Redis (use managed service) 
REDIS_URL=redis://your-redis-host:6379

# API Keys (use secret management)
IG_USERNAME=your_production_ig_username
IG_API_KEY=your_production_ig_key
```

## 📊 Monitoring

### Telegram Notifications

The service includes comprehensive Telegram monitoring:

- **Startup Notifications**: Service initialization status
- **Health Alerts**: Provider failures and recovery
- **Error Notifications**: Critical errors and exceptions
- **Heartbeat Messages**: Periodic system health reports
- **Performance Stats**: Request counts and success rates

### Health Checks

```bash
# Check overall service health
curl http://localhost:8001/health

# Check provider status
curl http://localhost:8001/api/v1/prices/status/providers

# Check Telegram status
curl http://localhost:8001/telegram/status
```

### Metrics & Logging

- **Request Logging**: All API requests logged with timing
- **Provider Stats**: Success/failure rates per provider
- **Cache Metrics**: Hit/miss rates and performance
- **Session Management**: IG Index authentication status
- **Background Tasks**: FRED cache warmup and heartbeat status

## 🛠️ Troubleshooting

### Common Issues

#### IG Index Authentication Fails
```bash
# Check credentials
echo "Username: $IG_USERNAME"
echo "API Key configured: $([ -n "$IG_API_KEY" ] && echo "Yes" || echo "No")"

# Test connection
curl -X POST http://localhost:8001/telegram/test
```

#### Database Connection Issues
```bash
# Test database connectivity
docker-compose exec market-data-service python -c "
from services.database_service import get_database_service
db = get_database_service()
print(db.health_check())
"
```

#### Redis Cache Issues
```bash
# Test Redis connection
docker-compose exec market-data-service python -c "
from services.cache_service import CacheService
cache = CacheService()
print('Redis healthy:', cache.health_check())
"
```

#### High API Failure Rates
1. Check provider health: `GET /api/v1/prices/status/providers`
2. Review logs for authentication issues
3. Verify API key limits and quotas
4. Check network connectivity to external APIs

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debug mode
uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level debug
```

### Performance Tuning

1. **Redis Configuration**: Increase memory limit and enable persistence
2. **Database Indexing**: Ensure proper indexes on symbol lookups
3. **Connection Pooling**: Configure appropriate pool sizes
4. **Rate Limiting**: Implement client-side rate limiting
5. **Caching Strategy**: Adjust TTL values based on usage patterns

## 📄 License

This project is proprietary software. All rights reserved.

## 🤝 Support

For support and questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review application logs for error details
3. Test individual components using health check endpoints
4. Monitor Telegram notifications for real-time status updates

---

**Built with ❤️ for high-performance financial data aggregation**
