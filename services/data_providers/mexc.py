# ==============================================================================
# MEXC PROVIDER - services/data_providers/mexc.py
# ==============================================================================

import httpx
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
import logging

from app.models import PriceData, AssetType

logger = logging.getLogger(__name__)

class MEXCProvider:
    """MEXC API for tokens not yet listed on Binance"""
    
    def __init__(self):
        self.base_url = "https://api.mexc.com/api/v3"
        self.client = httpx.AsyncClient(timeout=10.0)
        
        # Tokens available on MEXC but not Binance
        self.mexc_tokens = {
            "WAI": "WAIUSDT",
            # Add more tokens as needed
            "EXAMPLE": "EXAMPLEUSDT",
        }
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get token price from MEXC"""
        try:
            # Convert symbol format (WAI -> WAIUSDT)
            mexc_symbol = self._convert_symbol(symbol)
            if not mexc_symbol:
                logger.warning(f"Symbol {symbol} not available on MEXC")
                return None
            
            # Get 24hr ticker data
            response = await self.client.get(
                f"{self.base_url}/ticker/24hr",
                params={"symbol": mexc_symbol}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                return PriceData(
                    symbol=symbol,
                    asset_type=AssetType.CRYPTO,
                    price=float(data["lastPrice"]),
                    change_percent=float(data["priceChangePercent"]),
                    change_absolute=float(data["priceChange"]),
                    volume=float(data["volume"]),
                    timestamp=datetime.utcnow(),
                    source="mexc"
                )
            
            logger.warning(f"MEXC API returned {response.status_code} for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"MEXC API error for {symbol}: {e}")
            return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """Get multiple token prices from MEXC"""
        try:
            # MEXC supports getting all tickers at once
            response = await self.client.get(f"{self.base_url}/ticker/24hr")
            
            if response.status_code == 200:
                all_data = response.json()
                result = []
                
                for symbol in symbols:
                    mexc_symbol = self._convert_symbol(symbol)
                    if not mexc_symbol:
                        result.append(None)
                        continue
                    
                    # Find matching ticker data
                    ticker_data = next((d for d in all_data if d["symbol"] == mexc_symbol), None)
                    
                    if ticker_data:
                        result.append(PriceData(
                            symbol=symbol,
                            asset_type=AssetType.CRYPTO,
                            price=float(ticker_data["lastPrice"]),
                            change_percent=float(ticker_data["priceChangePercent"]),
                            change_absolute=float(ticker_data["priceChange"]),
                            volume=float(ticker_data["volume"]),
                            timestamp=datetime.utcnow(),
                            source="mexc"
                        ))
                    else:
                        result.append(None)
                
                return result
            
            return [None] * len(symbols)
            
        except Exception as e:
            logger.error(f"MEXC bulk API error: {e}")
            return [None] * len(symbols)
    
    def _convert_symbol(self, symbol: str) -> Optional[str]:
        """Convert symbol to MEXC format"""
        clean_symbol = symbol.replace("$", "").upper()
        return self.mexc_tokens.get(clean_symbol)
    
    def is_supported(self, symbol: str) -> bool:
        """Check if symbol is supported on MEXC"""
        clean_symbol = symbol.replace("$", "").upper()
        return clean_symbol in self.mexc_tokens
    
    async def health_check(self) -> bool:
        """Check if MEXC API is accessible"""
        try:
            response = await self.client.get(f"{self.base_url}/ping")
            return response.status_code == 200
        except:
            return False
    
    def get_supported_symbols(self) -> List[str]:
        """Get list of supported symbols"""
        return list(self.mexc_tokens.keys())

