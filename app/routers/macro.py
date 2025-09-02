# app/routers/macro.py - Final Corrected Version with Full Paths

import asyncio
from fastapi import APIRouter, HTTPException, Depends
import logging

from services.data_providers.fred_service import FredService
from app.models import MacroDataResponse

router = APIRouter()
logger = logging.getLogger(__name__)

def get_fred_service() -> FredService:
    """Dependency stub for FredService. This will be overridden in main.py."""
    pass

SERIES_MAP = {
    "cpi": ("CPIAUCSL", "Consumer Price Index"),
    "gdp": ("GDP", "Real Gross Domestic Product"),
    "unemployment": ("UNRATE", "Unemployment Rate"),
    "fedfunds": ("FEDFUNDS", "Federal Funds Rate"),
    "pmi": ("PMI", "ISM Manufacturing PMI"),
}

# --- THE STATIC PATH WITH THE FULL '/macro' PREFIX ---
@router.post("/macro/warm-cache", status_code=202)
async def warm_fred_cache(fred_service: FredService = Depends(get_fred_service)):
    """
    Manually triggers a cache refresh for all tracked FRED series.
    """
    # ... (function logic is correct and remains the same)
    series_to_warm = {
        "GDP": "Gross Domestic Product", "CPIAUCSL": "Consumer Price Index",
        "UNRATE": "Unemployment Rate", "FEDFUNDS": "Federal Funds Rate",
        "PMI": "ISM Manufacturing PMI"
    }
    logger.info("Manual FRED cache warmup triggered...")
    warmed_series = []
    loop = asyncio.get_event_loop()
    
    async def warm_series(series_id, series_name):
        try:
            await loop.run_in_executor(None, fred_service.get_series_data, series_id, series_name)
            warmed_series.append(series_id)
            logger.info(f"Successfully warmed cache for FRED series: {series_id}")
        except Exception as e:
            logger.error(f"Failed to warm cache for FRED series {series_id}: {e}")

    tasks = [warm_series(sid, name) for sid, name in series_to_warm.items()]
    await asyncio.gather(*tasks)

    return {
        "message": "FRED cache warmup process completed.",
        "warmed_series": warmed_series,
        "total": len(warmed_series)
    }

# --- THE DYNAMIC PATH WITH THE FULL '/macro' PREFIX ---
@router.get("/macro/{series_name}", response_model=MacroDataResponse)
async def get_macro_data(
    series_name: str,
    fred_service: FredService = Depends(get_fred_service)
):
    """
    Get the latest data for a key macroeconomic indicator.
    """
    if series_name.lower() not in SERIES_MAP:
        raise HTTPException(status_code=404, detail="Series not found.")
    
    series_id, friendly_name = SERIES_MAP[series_name.lower()]
    data = fred_service.get_series_data(series_id, friendly_name)
    
    if not data:
        raise HTTPException(status_code=503, detail=f"Failed to fetch data from FRED for {friendly_name}.")
        
    return data