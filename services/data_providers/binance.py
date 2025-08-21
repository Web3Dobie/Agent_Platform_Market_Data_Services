import httpx
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from app.models import PriceData, AssetType
import logging

logger = logging.getLogger(__name__)

class BinanceProvider:
    """Binance API for crypto data - superior to CoinGecko"""
    
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self.client = httpx.AsyncClient(timeout=10.0)
        
        # Symbol mapping for common crypto
        self.symbol_map = {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT", 
            "SOL": "SOLUSDT",
            "AVAX": "AVAXUSDT",
            "MATIC": "MATICUSDT",
            "ADA": "ADAUSDT",
            "DOT": "DOTUSDT",
            "LINK": "LINKUSDT",
            "UNI": "UNIUSDT",
            "AAVE": "AAVEUSDT"
        }
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get crypto price from Binance"""
        try:
            # Convert symbol format (BTC -> BTCUSDT)
            binance_symbol = self._convert_symbol(symbol)
            
            response = await self.client.get(
                f"{self.base_url}/ticker/24hr",
                params={"symbol": binance_symbol}
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
                    source="binance"
                )
            
            logger.warning(f"Binance API returned {response.status_code} for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Binance API error for {symbol}: {e}")
            return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """Get multiple crypto prices efficiently"""
        try:
            # Convert all symbols
            binance_symbols = [self._convert_symbol(s) for s in symbols]
            
            response = await self.client.get(f"{self.base_url}/ticker/24hr")
            
            if response.status_code == 200:
                all_data = response.json()
                result = []
                
                for i, original_symbol in enumerate(symbols):
                    binance_symbol = binance_symbols[i]
                    ticker_data = next((d for d in all_data if d["symbol"] == binance_symbol), None)
                    
                    if ticker_data:
                        result.append(PriceData(
                            symbol=original_symbol,
                            asset_type=AssetType.CRYPTO,
                            price=float(ticker_data["lastPrice"]),
                            change_percent=float(ticker_data["priceChangePercent"]),
                            change_absolute=float(ticker_data["priceChange"]),
                            volume=float(ticker_data["volume"]),
                            timestamp=datetime.utcnow(),
                            source="binance"
                        ))
                    else:
                        result.append(None)
                
                return result
            
            return [None] * len(symbols)
            
        except Exception as e:
            logger.error(f"Binance bulk API error: {e}")
            return [None] * len(symbols)
    
    def _convert_symbol(self, symbol: str) -> str:
        """Convert symbol to Binance format"""
        clean_symbol = symbol.replace("$", "").upper()
        return self.symbol_map.get(clean_symbol, f"{clean_symbol}USDT")
    
    async def health_check(self) -> bool:
        """Check if Binance API is accessible"""
        try:
            response = await self.client.get(f"{self.base_url}/ping")
            return response.status_code == 200
        except:
            return False