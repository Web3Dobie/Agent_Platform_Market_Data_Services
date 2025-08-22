# ==============================================================================
# IG INDEX PROVIDER - COMPLETE IMPLEMENTATION WITH FX NORMALIZATION
# services/data_providers/ig_index.py
# ==============================================================================

from trading_ig import IGService, IGStreamService
from trading_ig.config import config
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from app.models import PriceData, AssetType
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class IGIndexProvider:
    """IG Index API for indices, FX, commodities + equity fallback"""
    
    def __init__(self):
        self.ig_service = None
        self.authenticated = False
        self.session_tokens = None
        
        # Epic mappings for IG Index (EXACT MATCH to existing ig_market_data.py)
        self.epic_map = {
            # US EQUITY (all working)
            "^GSPC": "IX.D.SPTRD.DAILY.IP",      # S&P 500
            "SPY": "IX.D.SPTRD.DAILY.IP",        # S&P 500 ETF (alias)
            "^IXIC": "IX.D.NASDAQ.CASH.IP",      # NASDAQ Composite
            "QQQ": "IX.D.NASDAQ.CASH.IP",        # NASDAQ ETF (alias)
            "^DJI": "IX.D.DOW.DAILY.IP",         # Dow Jones
            "^RUT": "IX.D.RUSSELL.DAILY.IP",     # Russell 2000
            "IWM": "IX.D.RUSSELL.DAILY.IP",      # Russell 2000 ETF (alias)
            
            # EUROPE EQUITY (all working)
            "^GDAXI": "IX.D.DAX.DAILY.IP",       # DAX
            "^FTSE": "IX.D.FTSE.DAILY.IP",       # FTSE 100
            "^STOXX50E": "IX.D.STXE.CASH.IP",    # Euro Stoxx 50
            "^FCHI": "IX.D.CAC.DAILY.IP",        # CAC 40
            
            # ASIA EQUITY (all working)
            "^N225": "IX.D.NIKKEI.DAILY.IP",     # Nikkei 225
            "^HSI": "IX.D.HANGSENG.DAILY.IP",    # Hang Seng
            "000001.SS": "IX.D.XINHUA.DFB.IP",   # Shanghai Composite
            "^KS11": "IX.D.EMGMKT.DFB.IP",       # KOSPI
            
            # FOREX (all working)
            "EURUSD=X": "CS.D.EURUSD.TODAY.IP",
            "EURUSD": "CS.D.EURUSD.TODAY.IP",    # Alias without =X
            "USDJPY=X": "CS.D.USDJPY.TODAY.IP",
            "USDJPY": "CS.D.USDJPY.TODAY.IP",    # Alias without =X
            "GBPUSD=X": "CS.D.GBPUSD.TODAY.IP",
            "GBPUSD": "CS.D.GBPUSD.TODAY.IP",    # Alias without =X
            "USDCHF=X": "CS.D.USDCHF.TODAY.IP",
            "USDCHF": "CS.D.USDCHF.TODAY.IP",    # Alias without =X
            "AUDUSD=X": "CS.D.AUDUSD.TODAY.IP",
            "AUDUSD": "CS.D.AUDUSD.TODAY.IP",    # Alias without =X
            "USDCAD=X": "CS.D.USDCAD.TODAY.IP",
            "USDCAD": "CS.D.USDCAD.TODAY.IP",    # Alias without =X
            "EURGBP=X": "CS.D.EURGBP.TODAY.IP",
            "EURGBP": "CS.D.EURGBP.TODAY.IP",    # Alias without =X
            "EURJPY=X": "CS.D.EURJPY.TODAY.IP",
            "EURJPY": "CS.D.EURJPY.TODAY.IP",    # Alias without =X
            
            # COMMODITIES (all working)
            "GC=F": "CS.D.USCGC.TODAY.IP",       # Gold
            "GOLD": "CS.D.USCGC.TODAY.IP",       # Gold alias
            "SI=F": "CS.D.USCSI.TODAY.IP",       # Spot Silver
            "SILVER": "CS.D.USCSI.TODAY.IP",     # Silver alias
            "CL=F": "CC.D.CL.USS.IP",            # Oil - US Crude
            "OIL": "CC.D.CL.USS.IP",             # Oil alias
            "BZ=F": "CC.D.LCO.USS.IP",           # Oil - Brent Crude
            "BRENT": "CC.D.LCO.USS.IP",          # Brent alias
            "NG=F": "CC.D.NG.USS.IP",            # Natural Gas
            "NATGAS": "CC.D.NG.USS.IP",          # Natural Gas alias
            "HG=F": "MT.D.HG.Month1.IP",         # High Grade Copper
            "COPPER": "MT.D.HG.Month1.IP",       # Copper alias
            
            # RATES (commented out as in original, but kept for reference)
            # "^TNX": "IX.D.US10Y.DAILY.IP",     # 10-Year Treasury
            # "^IRX": "IX.D.US13W.DAILY.IP",     # 13-Week Treasury
            # "^TYX": "IX.D.US30Y.DAILY.IP",     # 30-Year Treasury
            
            # VIX and Dollar Index (commonly requested)
            "^VIX": "IX.D.VIX.DAILY.IP",         # VIX (if available)
            "VIX": "IX.D.VIX.DAILY.IP",          # VIX alias
            "DXY": "IX.D.DOLLAR.DAILY.IP",       # Dollar Index (if available)
            
            # NOTE: IG Index does NOT provide individual stock data
            # Individual equities (AAPL, MSFT, etc.) should use Yahoo Finance only
        }
    
    async def authenticate(self) -> bool:
        """Authenticate with IG Index using correct credentials"""
        try:
            if not all([settings.ig_username, settings.ig_password, settings.ig_api_key]):
                logger.error("IG credentials not configured")
                return False
            
            # Configure IG Service
            config.username = settings.ig_username
            config.password = settings.ig_password
            config.api_key = settings.ig_api_key
            config.acc_type = settings.ig_acc_type  # DEMO or LIVE
            
            # Initialize service
            self.ig_service = IGService(
                config.username, 
                config.password, 
                config.api_key, 
                config.acc_type
            )
            
            # Create session (this authenticates)
            await asyncio.to_thread(self.ig_service.create_session)
            
            self.authenticated = True
            logger.info(f"✅ IG Index authenticated successfully ({config.acc_type})")
            return True
            
        except Exception as e:
            logger.error(f"❌ IG Index authentication failed: {e}")
            self.authenticated = False
            return False
    
    def _normalize_ig_price(self, price: float, epic: str, symbol: str) -> float:
        """
        Normalize IG prices to standard format
        Spread betting account uses specific scaling
        
        Returns:
            float: normalized_price
        """
        
        # Forex pairs with .TODAY.IP (spread betting) - divide by 10,000
        if "CS.D." in epic and ".TODAY.IP" in epic:
            # Check if it's actually a commodity (Gold, Silver, etc.)
            if any(commodity in epic.upper() for commodity in ["GOLD", "SILVER", "COPPER", "USC"]):
                # Spot commodities - return as-is, no division needed
                logger.debug(f"Spot commodity {symbol}: {price} (no normalization)")
                return price
            elif "USDJPY" in symbol:
                # USD/JPY special case: divide by 100
                normalized_price = price / 100
                logger.debug(f"Normalized USD/JPY spread bet: {price} -> {normalized_price} (÷100)")
                return normalized_price
            else:
                # All other forex pairs: divide by 10,000
                normalized_price = price / 10000
                logger.debug(f"Normalized forex spread bet {symbol}: {price} -> {normalized_price} (÷10000)")
                return normalized_price
        
        # Forex pairs with .CFD.IP - divide by 10,000
        elif "CS.D." in epic and ".CFD.IP" in epic:
            if "USDJPY" in symbol:
                normalized_price = price / 100
                logger.debug(f"Normalized USD/JPY CFD: {price} -> {normalized_price} (÷100)")
                return normalized_price
            else:
                normalized_price = price / 10000
                logger.debug(f"Normalized forex CFD {symbol}: {price} -> {normalized_price} (÷10000)")
                return normalized_price
        
        # Index and commodity spread bets/CFDs - usually correct as-is
        elif "IX.D." in epic:
            logger.debug(f"Index {symbol}: {price} (no normalization)")
            return price
        
        # Commodity futures (CC.D.) - usually correct as-is
        elif "CC.D." in epic:
            logger.debug(f"Commodity future {symbol}: {price} (no normalization)")
            return price
            
        # Metal futures (MT.D.) - usually correct as-is
        elif "MT.D." in epic:
            logger.debug(f"Metal future {symbol}: {price} (no normalization)")
            return price
        
        # Default: return as-is
        logger.debug(f"Default {symbol}: {price} (no normalization)")
        return price
    
    def _get_normalization_factor(self, epic: str, symbol: str) -> float:
        """
        Get the normalization factor used for a given epic/symbol
        
        Returns:
            float: The factor by which prices are divided
        """
        
        # Forex pairs with .TODAY.IP (spread betting) - divide by 10,000
        if "CS.D." in epic and ".TODAY.IP" in epic:
            # Check if it's actually a commodity (Gold, Silver, etc.)
            if any(commodity in epic.upper() for commodity in ["GOLD", "SILVER", "COPPER", "USC"]):
                return 1.0  # No normalization for commodities
            elif "USDJPY" in symbol:
                return 100.0  # USD/JPY special case
            else:
                return 10000.0  # All other forex pairs
        
        # Forex pairs with .CFD.IP - divide by 10,000
        elif "CS.D." in epic and ".CFD.IP" in epic:
            if "USDJPY" in symbol:
                return 100.0
            else:
                return 10000.0
        
        # All others - no normalization
        else:
            return 1.0
    
    async def get_price(self, symbol: str) -> Optional[PriceData]:
        """Get price from IG Index with proper FX normalization"""
        if not self.authenticated:
            auth_success = await self.authenticate()
            if not auth_success:
                return None
        
        try:
            epic = self.epic_map.get(symbol.upper())
            if not epic:
                logger.warning(f"No IG epic found for symbol: {symbol}")
                return None
            
            # Get market data (run in thread as it's synchronous)
            market_data = await asyncio.to_thread(
                self.ig_service.fetch_market_by_epic, epic
            )
            
            if not market_data or 'snapshot' not in market_data:
                logger.warning(f"No market data returned for {symbol} ({epic})")
                return None
            
            snapshot = market_data['snapshot']
            
            # Get raw price from IG (bid/offer)
            raw_price = float(snapshot.get('bid', 0))
            if raw_price == 0:
                # Try offer price if bid is 0
                raw_price = float(snapshot.get('offer', 0))
            
            if raw_price == 0:
                logger.warning(f"Zero price returned for {symbol}")
                return None
            
            # 🔥 CRITICAL FIX: Normalize the price using the proven logic
            current_price = self._normalize_ig_price(raw_price, epic, symbol)
            
            # Get percentage change and absolute change
            change_percent = float(snapshot.get('percentageChange', 0))
            raw_change_absolute = float(snapshot.get('netChange', 0))
            
            # 🔥 ALSO NORMALIZE THE ABSOLUTE CHANGE by the same factor
            normalization_factor = self._get_normalization_factor(epic, symbol)
            change_absolute = raw_change_absolute / normalization_factor
            
            # For debugging
            if symbol.upper() in ["EURUSD=X", "EURUSD"]:
                logger.info(f"🔍 {symbol} normalization:")
                logger.info(f"   Price: {raw_price} -> {current_price} (÷{normalization_factor})")
                logger.info(f"   Change: {raw_change_absolute} -> {change_absolute} (÷{normalization_factor})")
                logger.info(f"   Epic: {epic}")
            
            # Determine asset type
            asset_type = self._get_asset_type(symbol)
            
            return PriceData(
                symbol=symbol,
                asset_type=asset_type,
                price=current_price,
                change_percent=change_percent,
                change_absolute=change_absolute,
                volume=None,  # IG doesn't always provide volume
                timestamp=datetime.utcnow(),
                source="ig_index"
            )
            
        except Exception as e:
            logger.error(f"IG Index API error for {symbol}: {e}")
            # Mark as not authenticated to retry auth next time
            self.authenticated = False
            return None
    
    async def get_bulk_prices(self, symbols: List[str]) -> List[Optional[PriceData]]:
        """Get multiple prices from IG Index"""
        # IG doesn't have efficient bulk API, so we'll do concurrent requests
        tasks = [self.get_price(symbol) for symbol in symbols]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    def _get_asset_type(self, symbol: str) -> AssetType:
        """Determine asset type from symbol (matches your existing system)"""
        symbol_upper = symbol.upper()
        
        # US, Europe, Asia Indices
        if symbol_upper in ["^GSPC", "SPY", "^IXIC", "QQQ", "^DJI", "^RUT", "IWM", 
                           "^GDAXI", "^FTSE", "^STOXX50E", "^FCHI",
                           "^N225", "^HSI", "000001.SS", "^KS11", "^VIX", "VIX", "DXY"]:
            return AssetType.INDEX
        
        # FX Pairs (with and without =X suffix)
        elif any(symbol_upper.startswith(pair) for pair in [
            "EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD", "EURGBP", "EURJPY"
        ]):
            return AssetType.FOREX
        
        # Commodities (with =F suffix and aliases)
        elif symbol_upper in ["GC=F", "GOLD", "SI=F", "SILVER", "CL=F", "OIL", 
                             "BZ=F", "BRENT", "NG=F", "NATGAS", "HG=F", "COPPER"]:
            return AssetType.COMMODITY
        
        # Default to equity (for fallback cases)
        else:
            return AssetType.EQUITY
    
    async def health_check(self) -> bool:
        """Check if IG Index API is accessible"""
        try:
            if not self.authenticated:
                return await self.authenticate()
            
            # Try to fetch a simple market (SPY)
            test_data = await self.get_price("EURUSD=X")
            return test_data is not None
            
        except Exception as e:
            logger.error(f"IG Index health check failed: {e}")
            return False
    
    def get_supported_symbols(self) -> List[str]:
        """Get list of all supported symbols"""
        return list(self.epic_map.keys())
    
    async def close_session(self):
        """Clean up IG session"""
        try:
            if self.ig_service and self.authenticated:
                await asyncio.to_thread(self.ig_service.logout)
                logger.info("IG Index session closed")
        except Exception as e:
            logger.error(f"Error closing IG session: {e}")