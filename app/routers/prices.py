# app/routers/prices.py
"""
Complete prices router with minimal Telegram logging
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime
from app.models import PriceData, BulkPriceRequest, BulkPriceResponse
from services.aggregator import DataAggregator
from services.telegram_notifier import notify_error, get_notifier
from services.symbol_normalizer import DynamicSymbolNormalizer
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prices", tags=["prices"])
normalizer = DynamicSymbolNormalizer()

# Dependency injection
def get_aggregator() -> DataAggregator:
    # This will be properly injected in main.py
    pass

@router.get("/{symbol}", response_model=PriceData)
async def get_price(
    symbol: str, 
    aggregator: DataAggregator = Depends(get_aggregator)
) -> PriceData:
    """Get current price for a single symbol with error logging"""
    try:
        logger.info(f"📊 Fetching price for symbol: {symbol}")
        
        # Increment request counter
        notifier = get_notifier()
        notifier.total_requests += 1
        
        # DEBUG: Check if aggregator is properly initialized
        logger.debug(f"Aggregator type: {type(aggregator)}")
        if hasattr(aggregator, 'providers'):
            logger.debug(f"Providers: {list(aggregator.providers.keys())}")
        
        # Get price data
        price_data = await aggregator.get_price(symbol)
        
        if not price_data:
            error_msg = f"Symbol {symbol} not found"
            logger.warning(f"⚠️ {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        
        logger.info(f"✅ Successfully fetched {symbol}: ${price_data.price}")
        return price_data
        
    except HTTPException:
        # Re-raise HTTP exceptions (already handled above)
        notifier.failed_requests += 1
        raise
        
    except Exception as e:
        notifier.failed_requests += 1
        error_msg = f"Internal error fetching {symbol}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        # Notify on unexpected errors
        notify_error(f"Price Request ({symbol})", str(e))
        
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/bulk", response_model=BulkPriceResponse)
async def get_bulk_prices(
    request: BulkPriceRequest,
    aggregator: DataAggregator = Depends(get_aggregator)
) -> BulkPriceResponse:
    """Get prices for multiple symbols with error logging"""
    symbol_count = len(request.symbols)
    
    try:
        logger.info(f"📊 Bulk price request for {symbol_count} symbols: {request.symbols[:5]}{'...' if symbol_count > 5 else ''}")
        
        # Increment request counter
        notifier = get_notifier()
        notifier.total_requests += symbol_count
        
        # Get bulk prices
        results = await aggregator.get_bulk_prices(request.symbols)
        
        # Process results
        successful = [r for r in results if r is not None]
        failed = [s for s, r in zip(request.symbols, results) if r is None]
        
        success_count = len(successful)
        failed_count = len(failed)
        
        logger.info(f"✅ Bulk request completed: {success_count}/{symbol_count} successful")
        
        # Only notify on high failure rates (>50%)
        if failed_count > symbol_count / 2:
            failure_rate = (failed_count / symbol_count) * 100
            notify_error(
                "Bulk Request High Failure", 
                f"{failed_count}/{symbol_count} failed ({failure_rate:.1f}%) - Symbols: {', '.join(failed[:3])}{'...' if len(failed) > 3 else ''}"
            )
            notifier.failed_requests += failed_count
            logger.warning(f"⚠️ High failure rate: {failure_rate:.1f}%")
        
        return BulkPriceResponse(
            data=successful,
            failed_symbols=failed,
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        notifier.failed_requests += symbol_count
        error_msg = f"Bulk request failed for {symbol_count} symbols: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        # Always notify bulk request failures
        notify_error("Bulk Price Request", str(e))
        
        raise HTTPException(status_code=500, detail=f"Bulk request failed: {str(e)}")

@router.get("/crypto/major")
async def get_major_crypto(aggregator: DataAggregator = Depends(get_aggregator)):
    """Get major cryptocurrencies with error logging"""
    try:
        logger.info("📊 Fetching major cryptocurrency prices")
        
        crypto_symbols = ["BTC", "ETH", "SOL", "AVAX", "MATIC", "ADA", "DOT", "LINK"]
        request = BulkPriceRequest(symbols=crypto_symbols, include_volume=True)
        
        # Use the bulk endpoint
        result = await get_bulk_prices(request, aggregator)
        
        success_count = len(result.data)
        
        # Only notify if most cryptos failed
        if success_count < len(crypto_symbols) / 2:
            notify_error(
                "Crypto Update Issues", 
                f"Only {success_count}/{len(crypto_symbols)} cryptos updated"
            )
        
        return result
        
    except Exception as e:
        error_msg = f"Major crypto request failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        notify_error("Major Crypto Request", str(e))
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/status/providers")
async def get_provider_status(aggregator: DataAggregator = Depends(get_aggregator)):
    """Get detailed provider status information"""
    try:
        provider_health = await aggregator.health_check()
        
        # Calculate stats
        total_providers = len(provider_health)
        healthy_providers = sum(1 for status in provider_health.values() if status)
        
        # Get notifier stats
        notifier = get_notifier()
        stats = notifier.get_stats()
        
        return {
            "providers": provider_health,
            "summary": {
                "total_providers": total_providers,
                "healthy_providers": healthy_providers,
                "health_percentage": (healthy_providers / total_providers * 100) if total_providers > 0 else 0
            },
            "performance": {
                "total_requests": stats["total_requests"],
                "failed_requests": stats["failed_requests"],
                "success_rate": ((stats["total_requests"] - stats["failed_requests"]) / max(stats["total_requests"], 1) * 100)
            },
            "telegram": {
                "enabled": stats["enabled"]
            }
        }
        
    except Exception as e:
        notify_error("Provider Status Check", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get provider status: {str(e)}")

@router.post("/test/{symbol}")
async def test_symbol_request(
    symbol: str,
    aggregator: DataAggregator = Depends(get_aggregator)
):
    """Test endpoint for debugging specific symbol requests"""
    try:
        logger.info(f"🧪 Test request for symbol: {symbol}")
        
        # Send test notification
        notifier = get_notifier()
        notifier.send_message(f"🧪 **Test Symbol Request**: {symbol}")
        
        # Get price data
        price_data = await aggregator.get_price(symbol)
        
        if price_data:
            result = {
                "symbol": symbol,
                "success": True,
                "price_data": {
                    "price": price_data.price,
                    "change_percent": price_data.change_percent,
                    "currency": price_data.currency,
                    "timestamp": price_data.timestamp
                }
            }
            
            # Send success notification
            notifier.send_message(f"✅ **Test Success**: {symbol} = ${price_data.price}")
            
        else:
            result = {
                "symbol": symbol,
                "success": False,
                "error": "No price data returned"
            }
            
            # Send failure notification
            notifier.send_message(f"❌ **Test Failed**: {symbol} - No data")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        
        # Send error notification
        notifier = get_notifier()
        notifier.send_message(f"🚨 **Test Error**: {symbol} - {error_msg[:100]}")
        
        return {
            "symbol": symbol,
            "success": False,
            "error": error_msg
        }

@router.get("/{symbol}")
async def get_price(symbol: str, aggregator: DataAggregator = Depends(get_aggregator)):
    """Get price for a symbol with automatic normalization"""
    try:
        # 🆕 Normalize the symbol first
        normalized = normalizer.normalize_symbol(symbol)
        
        logger.info(f"📊 Price request: {symbol} -> {normalized.clean_symbol} ({normalized.asset_type})")
        
        # Use the clean symbol for the existing logic
        price_data = await aggregator.get_price(normalized.clean_symbol)
        
        if price_data:
            # Add normalization info to response
            response_data = {
                "symbol": normalized.clean_symbol,
                "original_symbol": symbol,
                "asset_type": price_data.asset_type.value,
                "price": price_data.price,
                "change_percent": price_data.change_percent,
                "change_absolute": price_data.change_absolute,
                "volume": price_data.volume,
                "market_cap": price_data.market_cap,
                "timestamp": price_data.timestamp,
                "source": price_data.source,
                # 🆕 Add normalization metadata
                "normalization": {
                    "ig_epic": normalized.ig_epic,
                    "confidence": normalized.confidence,
                    "detected_type": normalized.asset_type
                }
            }
            return response_data
        else:
            raise HTTPException(status_code=404, detail=f"Price data not found for {symbol}")
            
    except Exception as e:
        logger.error(f"Price fetch error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))