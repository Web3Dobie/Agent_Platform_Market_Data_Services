from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime
from app.models import PriceData, BulkPriceRequest, BulkPriceResponse
from services.aggregator import DataAggregator

router = APIRouter(prefix="/prices", tags=["prices"])

# Dependency injection
def get_aggregator() -> DataAggregator:
    # This will be properly injected in main.py
    pass

@router.get("/{symbol}", response_model=PriceData)
async def get_price(
    symbol: str, 
    aggregator: DataAggregator = Depends(get_aggregator)
) -> PriceData:
    """Get current price for a single symbol"""
    try:
        # DEBUG: Check if aggregator is properly initialized
        print(f"DEBUG: Aggregator type: {type(aggregator)}")
        print(f"DEBUG: Providers: {list(aggregator.providers.keys())}")
        print(f"DEBUG: IG Index provider: {aggregator.providers.get('ig_index')}")

        price_data = await aggregator.get_price(symbol)
        
        if not price_data:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
            
        return price_data
    except Exception as e:
        print(f"DEBUG: Exception: {e}")
        print(f"DEBUG: Exception type: {type(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk", response_model=BulkPriceResponse)
async def get_bulk_prices(
    request: BulkPriceRequest,
    aggregator: DataAggregator = Depends(get_aggregator)
) -> BulkPriceResponse:
    """Get prices for multiple symbols efficiently"""
    try:
        results = await aggregator.get_bulk_prices(request.symbols)
        
        successful = [r for r in results if r is not None]
        failed = [s for s, r in zip(request.symbols, results) if r is None]
        
        return BulkPriceResponse(
            data=successful,
            failed_symbols=failed,
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crypto/major")
async def get_major_crypto(aggregator: DataAggregator = Depends(get_aggregator)):
    """Get major cryptocurrencies via Binance"""
    crypto_symbols = ["BTC", "ETH", "SOL", "AVAX", "MATIC", "ADA", "DOT", "LINK"]
    request = BulkPriceRequest(symbols=crypto_symbols, include_volume=True)
    return await get_bulk_prices(request, aggregator)
