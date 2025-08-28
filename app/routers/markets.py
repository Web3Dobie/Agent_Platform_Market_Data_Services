# app/routers/markets.py

from fastapi import APIRouter, Depends, HTTPException
from services.aggregator import DataAggregator
from typing import List, Dict, Any
import logging

# Dependency to get the aggregator instance
async def get_aggregator() -> DataAggregator:
    # This function will be overridden by the dependency in main.py
    # to return the global aggregator instance.
    raise NotImplementedError("Aggregator dependency not overridden")

router = APIRouter(
    prefix="/markets",
    tags=["markets"]
)

logger = logging.getLogger(__name__)

@router.get("/search/{search_term}", response_model=List[Dict[str, Any]])
async def search_markets(
    search_term: str, 
    aggregator: DataAggregator = Depends(get_aggregator)
):
    """
    Searches for markets matching the search_term, primarily using the IG provider.
    This is the main endpoint for discovering new EPICs for unknown symbols.
    """
    try:
        # We will add the search_markets method to the aggregator next.
        # It will be responsible for calling the correct provider (ig_index).
        found_markets = await aggregator.search_markets(search_term)
        
        if not found_markets:
            raise HTTPException(
                status_code=404, 
                detail=f"No markets found matching '{search_term}'"
            )
            
        return found_markets
        
    except HTTPException:
        # Re-raise HTTP exceptions to let FastAPI handle them
        raise
    except Exception as e:
        logger.error(f"Error during market search for '{search_term}': {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"An internal error occurred while searching for '{search_term}'."
        )