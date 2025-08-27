# app/routers/metadata.py
"""
Metadata router for symbol information and enhancement
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Dict, Any
from datetime import datetime
from services.aggregator import DataAggregator
from services.database_service import get_database_service
from services.telegram_notifier import notify_error, get_notifier
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metadata", tags=["metadata"])

# Dependency injection
def get_aggregator() -> DataAggregator:
    # This will be properly injected in main.py
    pass

@router.get("/{epic}")
async def get_market_metadata(
    epic: str,
    aggregator: DataAggregator = Depends(get_aggregator)
) -> Dict[str, Any]:
    """Get enhanced metadata for a specific EPIC from IG API"""
    try:
        logger.info(f"Fetching metadata for EPIC: {epic}")
        
        # Get the IG provider from aggregator
        ig_provider = None
        if hasattr(aggregator, 'providers'):
            ig_provider = aggregator.providers.get('ig_index')
        
        if not ig_provider:
            raise HTTPException(
                status_code=503, 
                detail="IG Index provider not available"
            )
        
        # Check if IG provider has the metadata method
        if not hasattr(ig_provider, '_get_market_metadata'):
            raise HTTPException(
                status_code=501,
                detail="Metadata functionality not implemented in IG provider"
            )
        
        # Get metadata from IG API
        metadata = await ig_provider._get_market_metadata(epic)
        
        if not metadata:
            logger.warning(f"No metadata found for EPIC: {epic}")
            raise HTTPException(
                status_code=404,
                detail=f"No metadata found for EPIC {epic}"
            )
        
        # Format response
        response = {
            "epic": epic,
            "name": metadata.get('name', ''),
            "clean_name": metadata.get('clean_name', ''),
            "type": metadata.get('type', ''),
            "market_id": metadata.get('market_id', ''),
            "currency": metadata.get('currency', ''),
            "country": metadata.get('country', ''),
            "timestamp": datetime.utcnow(),
            "source": "ig_index"
        }
        
        logger.info(f"Successfully retrieved metadata for {epic}: {metadata.get('clean_name', 'N/A')}")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        error_msg = f"Failed to get metadata for {epic}: {str(e)}"
        logger.error(error_msg)
        
        # Notify on unexpected errors
        notify_error(f"Metadata Request ({epic})", str(e))
        
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/symbol/{symbol}")
async def get_symbol_metadata(
    symbol: str,
    aggregator: DataAggregator = Depends(get_aggregator)
) -> Dict[str, Any]:
    """Get metadata for a symbol (looks up EPIC first, then gets metadata)"""
    try:
        logger.info(f"Looking up metadata for symbol: {symbol}")
        
        # Get the IG provider
        ig_provider = None
        if hasattr(aggregator, 'providers'):
            ig_provider = aggregator.providers.get('ig_index')
        
        if not ig_provider:
            raise HTTPException(
                status_code=503,
                detail="IG Index provider not available"
            )
        
        # First, look up the symbol in database to get EPIC
        if hasattr(ig_provider, '_lookup_symbol_in_db'):
            symbol_data = ig_provider._lookup_symbol_in_db(symbol)
        else:
            raise HTTPException(
                status_code=501,
                detail="Symbol lookup not implemented in IG provider"
            )
        
        if not symbol_data or not symbol_data.get('epic'):
            raise HTTPException(
                status_code=404,
                detail=f"No EPIC found for symbol {symbol}"
            )
        
        epic = symbol_data['epic']
        
        # Get metadata for the EPIC
        return await get_market_metadata(epic, aggregator)
        
    except HTTPException:
        raise
        
    except Exception as e:
        error_msg = f"Failed to get symbol metadata for {symbol}: {str(e)}"
        logger.error(error_msg)
        
        notify_error(f"Symbol Metadata Request ({symbol})", str(e))
        
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/discover/{symbol}")
async def discover_and_enhance_symbol(
    symbol: str,
    aggregator: DataAggregator = Depends(get_aggregator)
) -> Dict[str, Any]:
    """Discover EPIC for new symbol and enhance with IG API metadata"""
    try:
        logger.info(f"Discovering and enhancing symbol: {symbol}")
        
        # Get the IG provider
        ig_provider = None
        if hasattr(aggregator, 'providers'):
            ig_provider = aggregator.providers.get('ig_index')
        
        if not ig_provider:
            raise HTTPException(
                status_code=503,
                detail="IG Index provider not available"
            )
        
        # Check if discovery method exists
        if not hasattr(ig_provider, '_discover_and_enhance_symbol'):
            raise HTTPException(
                status_code=501,
                detail="Symbol discovery not implemented in IG provider"
            )
        
        # Discover and enhance the symbol
        result = await ig_provider._discover_and_enhance_symbol(symbol)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Could not discover EPIC for symbol {symbol}"
            )
        
        response = {
            "symbol": result['symbol'],
            "epic": result['epic'],
            "display_name": result['display_name'],
            "asset_type": result['asset_type'],
            "status": "discovered_and_saved",
            "timestamp": datetime.utcnow()
        }
        
        logger.info(f"Successfully discovered {symbol}: {result['epic']} -> {result['display_name']}")
        return response
        
    except HTTPException:
        raise
        
    except Exception as e:
        error_msg = f"Failed to discover symbol {symbol}: {str(e)}"
        logger.error(error_msg)
        
        notify_error(f"Symbol Discovery ({symbol})", str(e))
        
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def get_database_symbols(
    limit: int = 100,
    offset: int = 0,
    asset_type: Optional[str] = None,
    db_service: DatabaseService = Depends(get_database_service)
) -> Dict[str, Any]:
    """Get symbols from database with pagination"""
    try:
        logger.info(f"Fetching database symbols: limit={limit}, offset={offset}, asset_type={asset_type}")
        
        result = db_service.get_symbols_by_asset_type(asset_type, limit, offset)
        
        logger.info(f"Retrieved {len(result['symbols'])} symbols from database")
        return result
        
    except Exception as e:
        error_msg = f"Failed to get database symbols: {str(e)}"
        logger.error(error_msg)
        
        notify_error("Database Symbols Request", str(e))
        
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")