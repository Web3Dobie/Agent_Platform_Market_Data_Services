from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class AssetType(str, Enum):
    EQUITY = "equity"
    COMMODITY = "commodity"
    FOREX = "forex"
    INDEX = "index"
    CRYPTO = "crypto"

class PriceData(BaseModel):
    symbol: str
    asset_type: AssetType
    price: float
    change_percent: float
    change_absolute: float
    volume: Optional[float] = None
    market_cap: Optional[float] = None
    timestamp: datetime
    source: str

class BulkPriceRequest(BaseModel):
    symbols: List[str]
    include_volume: bool = False
    include_market_cap: bool = False

class BulkPriceResponse(BaseModel):
    data: List[PriceData]
    failed_symbols: List[str]
    timestamp: datetime

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    services: dict

class NewsItem(BaseModel):
    headline: str
    summary: Optional[str] = None
    url: Optional[str] = None
    source: str
    timestamp: datetime

class MarketMoversResponse(BaseModel):
    gainers: List[dict]
    losers: List[dict]
    timestamp: datetime

class MacroDataPoint(BaseModel):
    date: str
    value: float

class MacroDataResponse(BaseModel):
    name: str
    series_id: str
    latest_value: float
    latest_date: str
    change_from_previous: float
    percent_change_from_previous: float
    percent_change_year_ago: Optional[float] = None
    history: List[MacroDataPoint]
