from trading_ig import IGService
from trading_ig.config import config
from requests.exceptions import ConnectionError, HTTPError
import asyncio
import psycopg2
import psycopg2.extras
import os
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models import PriceData, AssetType
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class IGIndexProvider:
    def __init__(self):
        self.ig_service: Optional[IGService] = None
        self.authenticated = False
        self._lock = asyncio.Lock()
        logger.info("IG Index provider initialized with self-healing session and fully async logic.")

    async def initialize(self, force_reconnect: bool = False) -> bool:
        async with self._lock:
            if self.authenticated and not force_reconnect: 
                return True
            
            # If force_reconnect is True, reset the session
            if force_reconnect:
                logger.info("Force reconnect requested - resetting IG session...")
                self.authenticated = False
                self.ig_service = None
                
            logger.info("Attempting to establish IG Index session...")
            try:
                if not all([settings.ig_username, settings.ig_password, settings.ig_api_key]):
                    logger.error("IG credentials not found in settings.")
                    return False
                self.ig_service = IGService(
                    username=settings.ig_username, password=settings.ig_password,
                    api_key=settings.ig_api_key, acc_type=settings.ig_acc_type
                )
                await asyncio.to_thread(self.ig_service.create_session)
                self.authenticated = True
                logger.info(f"✅ IG Index session established successfully ({settings.ig_acc_type})")
                return True
            except Exception as e:
                logger.error(f"❌ IG authentication failed: {e}")
                self.authenticated = False
                self.ig_service = None
                return False

    async def _ensure_session_is_active(self):
        if not self.authenticated or not self.ig_service: await self.initialize()
        try:
            await asyncio.to_thread(self.ig_service.fetch_accounts)
        except Exception as e:
            error_message = str(e).lower()
            if isinstance(e, (ConnectionError, HTTPError)) or "security" in error_message or "token" in error_message:
                logger.warning(f"IG session appears dead ({type(e).__name__}). Re-authenticating...")
                self.authenticated = False
                await self.initialize()
            else:
                logger.error(f"Unexpected error checking IG session status: {e}")
                raise e

    def _get_db_params(self) -> dict:
        return {'host': os.getenv('DB_HOST', 'localhost'), 'port': os.getenv('DB_PORT', '5432'),
                'database': os.getenv('DB_NAME', 'agents_platform'), 'user': os.getenv('DB_USER', 'admin'),
                'password': os.getenv('DB_PASSWORD', 'secure_agents_password')}

    async def _lookup_symbol_in_db(self, ticker: str) -> Optional[Dict]:
        def db_call():
            try:
                with psycopg2.connect(**self._get_db_params()) as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                        cursor.execute("SELECT * FROM hedgefund_agent.stock_universe WHERE symbol = %s AND active = TRUE;", (ticker.upper(),))
                        return cursor.fetchone()
            except Exception as e:
                logger.error(f"Database lookup failed for {ticker}: {e}")
        result = await asyncio.to_thread(db_call)
        if result: return dict(result)

    async def _save_discovered_symbol(self, ticker: str, epic: str, display_name: str, asset_type: str) -> bool:
        def db_call():
            try:
                with psycopg2.connect(**self._get_db_params()) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT add_discovered_symbol(%s, %s, %s, %s);", (ticker.upper(), display_name, epic, asset_type))
                        return cursor.fetchone()
            except Exception as e:
                logger.error(f"Failed to save {ticker} to database: {e}")
        result = await asyncio.to_thread(db_call)
        if result and result[0]:
            logger.info(f"Saved discovered symbol: {ticker} -> {epic}")
            return True
        return False

    async def search_markets(self, search_term: str) -> List[Dict[str, Any]]:
        """Calls the IG API to search for markets matching the search_term."""
        try:
            await self._ensure_session_is_active()
            if not self.authenticated:
                return []
        except Exception as e:
            logger.error(f"Failed to ensure IG session for market search: {e}")
            return []
        
        logger.info(f"IG: Searching for markets matching '{search_term}'")
        try:
            markets_df: pd.DataFrame = await asyncio.to_thread(self.ig_service.search_markets, search_term)
            if markets_df.empty:
                logger.warning(f"IG: No markets found for search term '{search_term}'")
                return []
            return markets_df.to_dict(orient='records')
        except Exception as e:
            logger.error(f"IG: Error searching markets for '{search_term}': {e}")
            return []

    async def _discover_and_enhance_symbol(self, ticker: str) -> Optional[Dict]:
        logger.info(f"Starting new discovery process for symbol: {ticker}")
        search_results = await self.search_markets(ticker.upper())
        if not search_results: return None

        candidates = [m for m in search_results if m.get('marketStatus') == 'TRADEABLE' and m.get('streamingPricesAvailable')]
        if not candidates:
            logger.warning(f"No TRADEABLE market found for {ticker}")
            return None
        
        best_match = candidates[0]
        epic = best_match['epic']
        metadata = await self._get_market_metadata(epic)
        display_name = metadata.get('clean_name', ticker) if metadata else ticker
        asset_type = self._infer_asset_type(ticker, epic, metadata)
        
        if await self._save_discovered_symbol(ticker, epic, display_name, asset_type):
            return {'symbol': ticker, 'epic': epic, 'display_name': display_name, 'asset_type': asset_type}
        return None

    async def _get_market_metadata(self, epic: str) -> Optional[Dict]:
        try:
            await self._ensure_session_is_active()
            if not self.authenticated: return None
        except Exception as e:
            logger.error(f"Failed to ensure IG session for metadata: {e}")
            return None
        
        try:
            await asyncio.sleep(0.5)
            market_data = await asyncio.to_thread(self.ig_service.fetch_market_by_epic, epic)
            if not market_data or 'instrument' not in market_data: return None
            instrument = market_data['instrument']
            metadata = {'epic': epic, 'name': instrument.get('name', '')}
            if metadata['name']: metadata['clean_name'] = self._clean_instrument_name(metadata['name'])
            return metadata
        except Exception as e:
            logger.error(f"Failed to get metadata for {epic}: {e}")
            return None

    async def get_price(self, ticker: str, ensure_session: bool = True) -> Optional[PriceData]:
        try:
            if not self.authenticated: return None
            
            symbol_data = await self._lookup_symbol_in_db(ticker)
            if not symbol_data:
                symbol_data = await self._discover_and_enhance_symbol(ticker)
                if not symbol_data:
                    logger.warning(f"Could not find or discover {ticker}")
                    return None
            
            epic = symbol_data.get('epic')
            if not epic:
                logger.warning(f"No EPIC available for {ticker}")
                return None
            
            market_data = await asyncio.to_thread(self.ig_service.fetch_market_by_epic, epic)
            
            if not market_data or 'snapshot' not in market_data:
                logger.warning(f"No data for {ticker} ({epic})")
                return None
            
            snapshot = market_data['snapshot']
            bid_price, offer_price = snapshot.get('bid'), snapshot.get('offer')
            raw_price = float(bid_price) if bid_price is not None else float(offer_price) if offer_price is not None else 0.0
            
            if raw_price == 0:
                logger.warning(f"Zero or None price for {ticker} ({epic})")
                return None
            
            price = self._normalize_price(raw_price, epic)
            change_percent = float(snapshot.get('percentageChange') or 0.0)
            change_absolute = float(snapshot.get('netChange') or 0.0)
            asset_type_str = symbol_data.get('asset_type', 'stock')
            asset_type = AssetType[asset_type_str.upper()] if hasattr(AssetType, asset_type_str.upper()) else AssetType.EQUITY
            
            return PriceData(symbol=ticker, asset_type=asset_type, price=price, change_percent=change_percent, change_absolute=change_absolute, timestamp=datetime.utcnow(), source="ig_index")
        except Exception as e:
            logger.error(f"An unexpected error in get_price for {ticker}: {e}", exc_info=True)
            return None

    async def health_check(self) -> bool:
        def db_check_call():
            try:
                with psycopg2.connect(**self._get_db_params()) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1;")
                return True
            except Exception as e:
                logger.error(f"Health check failed to connect to DB: {e}")
                return False
        db_ok = await asyncio.to_thread(db_check_call)
        return self.authenticated and db_ok

    def _clean_instrument_name(self, raw_name: str) -> str:
        """Clean instrument names from IG API for better display"""
        if not raw_name: return raw_name
        suffixes_to_remove = [' DFB', ' CFD', ' Cash', ' (DFB)', ' (CFD)', ' - Cash', ' - DFB']
        cleaned = raw_name.strip()
        for suffix in suffixes_to_remove:
            if cleaned.endswith(suffix): cleaned = cleaned[:-len(suffix)].strip()
        cleaned = ' '.join(cleaned.split())
        replacements = {
            'US 500': 'S&P 500', 'US Tech 100': 'NASDAQ 100', 'US Wall St 30': 'Dow Jones 30',
            'Wall Street 30': 'Dow Jones 30', 'UK 100': 'FTSE 100', 'Germany 40': 'DAX',
            'Japan 225': 'Nikkei 225', 'Hong Kong 40': 'Hang Seng', 'France 40': 'CAC 40',
            'Spain 35': 'IBEX 35', 'Australia 200': 'ASX 200',
        }
        for old, new in replacements.items():
            if old in cleaned: cleaned = cleaned.replace(old, new)
        return cleaned

    def _infer_asset_type(self, ticker: str, epic: str, metadata: Optional[Dict] = None) -> str:
        """Infer asset type from ticker, EPIC, and metadata"""
        ticker = ticker.upper()
        if (ticker.startswith('^') or ticker in ['SPY', 'QQQ', 'DIA', 'IWM', 'VIX'] or epic.startswith('IX.')):
            return 'index'
        if (('USD' in ticker and len(ticker) == 6) or ticker.endswith('=X') or epic.startswith('CS.D.')):
            return 'forex'
        if (ticker in ['GOLD', 'SILVER', 'OIL', 'BRENT', 'NATGAS', 'COPPER'] or ticker.endswith('=F') or epic.startswith('CC.D.') or epic.startswith('MT.D.')):
            return 'commodity'
        if ticker in ['BTC', 'ETH'] or 'CRYPTO' in (metadata.get('type', '') if metadata else ''):
            return 'crypto'
        return 'stock'

    def _normalize_price(self, price: float, epic: str) -> float:
        """Normalize IG prices to standard format"""
        if epic.startswith(('UA.D.', 'UB.D.', 'UC.D.', 'UD.D.', 'UE.D.', 'UF.D.', 'UG.D.', 'UH.D.', 'UI.D.', 'UJ.D.', 'SH.D.', 'SA.D.', 'SB.D.', 'SC.D.', 'SD.D.', 'SE.D.', 'SF.D.', 'SG.D.', 'SI.D')) and epic.endswith('.DAILY.IP'):
            return price / 100
        return price