# AGENTS.md - Market Data Service

## Service Overview

**Service Name:** Market Data Service  
**Version:** 1.0.0  
**Type:** FastAPI Microservice  
**Port:** 8001  
**Primary Purpose:** Multi-provider financial data aggregation with intelligent failover and caching

## Core Capabilities

### Data Providers
- **IG Index**: Primary provider for equities, indices, forex, commodities
- **Binance**: Primary crypto data (BTC, ETH, SOL, AVAX, MATIC, ADA, DOT, LINK, UNI, AAVE)
- **MEXC**: Alternative crypto tokens (WAI, custom tokens)
- **Finnhub**: News, market movers, IPO calendar, earnings calendar
- **FRED**: Macroeconomic data (GDP, CPI, unemployment, fed funds rate, PMI)

### Asset Type Support
- **CRYPTO**: Bitcoin, Ethereum, Solana, Avalanche, Polygon, Cardano, Polkadot, Chainlink, Uniswap, Aave, WAI
- **EQUITY**: Individual stocks (AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, etc.)
- **INDEX**: S&P 500 (SPY), NASDAQ (QQQ), Dow Jones, VIX, Russell 2000
- **FOREX**: Major currency pairs (EURUSD, GBPUSD, USDJPY, USDCHF, etc.)
- **COMMODITY**: Gold, Silver, Oil (WTI/Brent), Natural Gas, Copper

### Data Types Available
- **Real-time Prices**: Current price, change %, change absolute, volume
- **Market Metadata**: Symbol information, epic codes, asset classification
- **Company News**: Recent news articles for specific symbols
- **Market News**: General market news by category
- **Economic Calendar**: IPO dates, earnings announcements
- **Macroeconomic Indicators**: GDP, inflation, unemployment, interest rates

## API Endpoints

### Price Data
```
GET  /api/v1/prices/{symbol}                    # Single price
POST /api/v1/prices/bulk                        # Bulk prices
GET  /api/v1/prices/crypto/major                # Major cryptocurrencies
GET  /api/v1/prices/status/providers            # Provider health
POST /api/v1/prices/test/{symbol}               # Debug endpoint
```

### Market Discovery
```
GET /api/v1/markets/search/{search_term}        # Search for symbols/markets
```

### Metadata & Symbol Management
```
GET  /api/v1/metadata/{epic}                    # Get metadata by IG epic
GET  /api/v1/metadata/symbol/{symbol}           # Get metadata by symbol
POST /api/v1/metadata/discover/{symbol}         # Discover new symbol
GET  /api/v1/metadata/database/symbols          # List known symbols
```

### News & Calendar Data
```
GET /api/v1/news/company/{symbol}               # Company-specific news
GET /api/v1/news/market                         # General market news
GET /api/v1/calendar/ipo                        # IPO calendar
GET /api/v1/calendar/earnings                   # Earnings calendar
```

### Macroeconomic Data
```
GET  /api/v1/macro/{series_name}                # Economic indicators
POST /api/v1/macro/warm-cache                   # Refresh macro cache
```

### System Health
```
GET /health                                     # Service health check
GET /telegram/status                            # Telegram notification status
POST /telegram/test                             # Test notifications
POST /telegram/heartbeat                        # Manual heartbeat
```

## Data Models

### PriceData
```json
{
  "symbol": "string",
  "asset_type": "equity|crypto|forex|index|commodity",
  "price": "float",
  "change_percent": "float", 
  "change_absolute": "float",
  "volume": "float|null",
  "market_cap": "float|null",
  "timestamp": "datetime",
  "source": "string"
}
```

### BulkPriceRequest
```json
{
  "symbols": ["string"],
  "include_volume": "boolean",
  "include_market_cap": "boolean"
}
```

### MacroDataResponse
```json
{
  "name": "string",
  "series_id": "string",
  "latest_value": "float",
  "latest_date": "string",
  "change_from_previous": "float",
  "percent_change_from_previous": "float",
  "percent_change_year_ago": "float|null",
  "history": [{"date": "string", "value": "float"}]
}
```

## Provider-Specific Logic

### IG Index Provider
- **Authentication**: OAuth-based session with automatic renewal
- **Epic Codes**: Dynamic generation (e.g., AAPL -> UA.D.AAPL.DAILY.IP)
- **Price Normalization**: Converts pence to dollars for UK stocks
- **Asset Detection**: Infers asset type from epic patterns
- **Database Integration**: Stores/retrieves symbol metadata
- **Session Management**: Self-healing with proactive refresh

### Binance Provider  
- **Symbol Mapping**: Converts symbols to USDT pairs (BTC -> BTCUSDT)
- **Bulk Support**: Efficient batch processing via 24hr ticker endpoint
- **Timeout Handling**: 10-second timeout with graceful fallback

### MEXC Provider
- **Token Support**: Handles tokens not available on Binance
- **Symbol Registry**: Configurable token mapping (WAI -> WAIUSDT)
- **Batch Processing**: Single API call for multiple symbols

### Finnhub Provider
- **News Categories**: general, forex, crypto, merger
- **Calendar Events**: IPO and earnings with estimates
- **Rate Limiting**: Respectful API usage with delays

### FRED Service
- **Series Mapping**: Friendly names for economic indicators
- **Cache Strategy**: Long TTL (24 hours) for slow-changing data
- **Background Refresh**: Daily cache warmup at 16:00 UTC

## Intelligent Features

### Provider Selection Algorithm
1. **Asset Type Detection**: Analyzes symbol format and patterns
2. **Provider Priority**: Routes to optimal provider per asset type
3. **Failover Logic**: Attempts alternative providers on failure
4. **Health Monitoring**: Skips unhealthy providers

### Symbol Normalization
- **Dynamic Epic Generation**: Creates IG Index epic codes on-the-fly
- **Pattern Recognition**: Detects forex pairs, commodities, indices
- **Confidence Scoring**: Rates classification accuracy
- **Format Conversion**: Handles $SYMBOL, SYMBOL, company names

### Session Management
- **Proactive Refresh**: Prevents authentication timeouts
- **Error Detection**: Identifies session expiry patterns
- **Automatic Recovery**: Re-authenticates on failure
- **Concurrency Control**: Async locks prevent race conditions

### Caching Strategy
```
Asset Type     | TTL    | Reasoning
---------------|--------|------------------------------------------
Crypto         | 60s    | High volatility, frequent updates needed
Traditional    | 300s   | Moderate changes, balance speed/accuracy  
News           | 900s   | Stories remain relevant for 15 minutes
Macro          | 86400s | Economic data changes slowly
```

## Error Handling & Resilience

### Provider Failures
- **Graceful Degradation**: Returns partial data on provider failures
- **Timeout Management**: Configurable timeouts per provider type
- **Circuit Breaker Pattern**: Temporarily skips failing providers
- **Health Monitoring**: Continuous provider status tracking

### Authentication Issues
- **Session Recovery**: Automatic re-authentication on token expiry
- **Credential Validation**: Startup checks for required API keys
- **Error Classification**: Distinguishes between auth and network errors

### Data Quality
- **Price Validation**: Rejects zero/negative prices
- **Timestamp Freshness**: Ensures data recency
- **Format Standardization**: Normalizes response formats across providers
- **Null Handling**: Graceful handling of missing data fields

## Performance Optimizations

### Bulk Processing
- **Provider Grouping**: Routes symbols to optimal providers in batches
- **Concurrent Execution**: Parallel processing for non-IG providers  
- **IG Sequential Processing**: Rate-limited processing with backoff
- **Result Aggregation**: Maintains original request order

### Caching
- **Redis Integration**: Distributed caching with configurable TTL
- **Cache Keys**: Structured keys for easy management
- **Hit Rate Optimization**: Separate TTL per data type
- **Memory Management**: LRU eviction policy

### Database
- **Connection Pooling**: Efficient database connection reuse
- **Query Optimization**: Indexed lookups on symbol/epic
- **Async Operations**: Non-blocking database operations
- **Batch Inserts**: Efficient bulk symbol storage

## Monitoring & Observability

### Health Checks
- **Provider Status**: Individual provider health monitoring
- **Database Connectivity**: PostgreSQL connection validation
- **Cache Availability**: Redis connectivity checks
- **Background Tasks**: Heartbeat and cache warmup monitoring

### Telegram Notifications
- **Startup Alerts**: Service initialization status
- **Health Monitoring**: Provider failures and recovery
- **Error Notifications**: Critical error alerting
- **Performance Stats**: Request metrics and success rates
- **Heartbeat Messages**: Periodic system status (every 30 minutes)

### Logging
- **Request Tracing**: Full request/response logging
- **Error Context**: Detailed error information with stack traces
- **Performance Metrics**: Request timing and success rates
- **Provider Analytics**: Individual provider performance tracking

## Security Considerations

### API Key Management
- **Environment Variables**: Secure credential storage
- **Validation**: Startup checks for required credentials
- **Scope Limitation**: Minimal required permissions per provider

### Network Security
- **HTTPS Only**: Secure communication with external APIs
- **Timeout Configuration**: Prevents hanging connections
- **Rate Limiting**: Respectful API usage patterns

### Data Protection
- **No Credential Logging**: API keys excluded from logs
- **Secure Sessions**: Proper session lifecycle management
- **Input Validation**: Sanitized user inputs

## Integration Patterns

### Request Flow
1. **FastAPI Router**: Receives and validates request
2. **Symbol Normalization**: Converts to provider format
3. **Provider Selection**: Routes based on asset type
4. **Cache Check**: Attempts Redis cache lookup
5. **Provider Call**: Fetches from external API
6. **Data Normalization**: Standardizes response format
7. **Cache Storage**: Stores result with appropriate TTL
8. **Response**: Returns formatted data to client

### Background Tasks
- **FRED Cache Warmup**: Daily refresh at 16:00 UTC
- **Heartbeat Monitoring**: 30-minute health checks
- **Session Maintenance**: Proactive IG authentication refresh

### Event Patterns
- **Startup Sequence**: Provider initialization and health validation
- **Graceful Shutdown**: Clean resource cleanup
- **Error Recovery**: Automatic retry and fallback mechanisms

## Configuration Management

### Environment Variables
```bash
# Core Service
HOST=0.0.0.0
PORT=8001
LOG_LEVEL=INFO
WORKERS=1

# Primary Provider (Required)
IG_USERNAME=<username>
IG_PASSWORD=<password>
IG_API_KEY=<api_key>
IG_ACC_TYPE=DEMO

# Optional Providers
FINNHUB_API_KEY=<api_key>
FRED_API_KEY=<api_key>

# Infrastructure
REDIS_URL=redis://localhost:6379
DB_HOST=localhost
DB_PORT=5432
DB_NAME=agents_platform
DB_USER=admin
DB_PASSWORD=<password>

# Monitoring (Optional)
TG_BOT_TOKEN=<bot_token>
TG_CHAT_ID=<chat_id>
```

### Cache TTL Configuration
```bash
CRYPTO_CACHE_TTL=60        # 1 minute
TRADITIONAL_CACHE_TTL=300  # 5 minutes  
NEWS_CACHE_TTL=900         # 15 minutes
MACRO_CACHE_TTL=86400      # 24 hours
```

## Usage Examples

### Single Price Request
```python
import httpx

async def get_stock_price(symbol: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8001/api/v1/prices/{symbol}")
        return response.json()

# Usage
price_data = await get_stock_price("AAPL")
print(f"AAPL: ${price_data['price']:.2f} ({price_data['change_percent']:.2f}%)")
```

### Bulk Price Request
```python
async def get_portfolio_prices(symbols: list):
    async with httpx.AsyncClient() as client:
        payload = {"symbols": symbols, "include_volume": True}
        response = await client.post(
            "http://localhost:8001/api/v1/prices/bulk",
            json=payload
        )
        return response.json()

# Usage
portfolio = ["AAPL", "BTC", "SPY", "EURUSD"]
data = await get_portfolio_prices(portfolio)
for item in data["data"]:
    print(f"{item['symbol']}: ${item['price']:.2f}")
```

### Market Discovery
```python
async def search_markets(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8001/api/v1/markets/search/{query}"
        )
        return response.json()

# Usage  
results = await search_markets("apple")
for market in results:
    print(f"{market['instrumentName']}: {market['epic']}")
```

### News Retrieval
```python
async def get_company_news(symbol: str, days: int = 7):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8001/api/v1/news/company/{symbol}?days={days}"
        )
        return response.json()

# Usage
news = await get_company_news("AAPL", 3)
for article in news["articles"]:
    print(f"{article['headline']} - {article['source']}")
```

## Deployment Notes

### Docker Compose
- **Multi-container**: Service + Redis + Database
- **Volume Persistence**: Redis and PostgreSQL data persistence
- **Network Configuration**: Internal container networking
- **Health Checks**: Container health monitoring

### Production Scaling
- **Horizontal Scaling**: Multiple service instances behind load balancer
- **Database Clustering**: PostgreSQL read replicas for scaling
- **Redis Clustering**: Distributed caching for high availability
- **CDN Integration**: Static asset delivery optimization

### Monitoring Integration
- **Prometheus Metrics**: Custom metrics export
- **Grafana Dashboards**: Performance visualization
- **Alert Manager**: Critical error alerting
- **Log Aggregation**: Centralized log management

This service provides comprehensive financial data aggregation with enterprise-grade reliability, monitoring, and performance optimization.