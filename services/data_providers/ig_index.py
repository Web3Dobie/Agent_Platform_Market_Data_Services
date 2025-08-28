# ==============================================================================
# IG INDEX PROVIDER - SEARCH-BASED DISCOVERY REFACTOR
# services/data_providers/ig_index.py
# ==============================================================================

from trading_ig import IGService
from trading_ig.config import config
import asyncio
import psycopg2
import psycopg2.extras
import os
import pandas as pd
from typing import Optional, List, Dict, Any # Added Any
from datetime import datetime
from app.models import PriceData, AssetType
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class IGIndexProvider:
    """IG Index API with database-first symbol management and search-based discovery"""
    
    def __init__(self):
        self.ig_service = None
        self.authenticated = False
        
        # --- REMOVED --- self.prefixes is no longer needed.
        
        logger.info("IG Index provider initialized with search-based discovery")
    
    # --- NO CHANGES to _get_db_params, _lookup_symbol_in_db, _save_discovered_symbol ---
    def _get_db_params(self) -> dict:
        """Helper to get database connection parameters from environment variables."""
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', os.getenv('DB_DATABASE', 'agents_platform')),
            'user': os.getenv('DB_USER', 'admin'),
            'password': os.getenv('DB_PASSWORD', 'secure_agents_password')
        }
    
    def _lookup_symbol_in_db(self, ticker: str) -> Optional[Dict]:
        """Look up symbol in database with on-demand connection."""
        try:
            with psycopg2.connect(**self._get_db_params()) as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, symbol, display_name, epic, asset_type, active
                        FROM hedgefund_agent.stock_universe 
                        WHERE symbol = %s AND active = TRUE;
                    """, (ticker.upper(),))
                    
                    result = cursor.fetchone()
            
            if result:
                logger.debug(f"Found {ticker} in database: {result['epic']}")
                return dict(result)
            else:
                logger.debug(f"Symbol {ticker} not found in database")
                return None
                
        except Exception as e:
            logger.error(f"Database lookup failed for {ticker}: {e}")
            return None
    
    def _save_discovered_symbol(self, ticker: str, epic: str, display_name: str, asset_type: str = 'stock') -> bool:
        """Save newly discovered symbol to database with on-demand connection."""
        try:
            with psycopg2.connect(**self._get_db_params()) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT add_discovered_symbol(%s, %s, %s, %s);
                    """, (ticker.upper(), display_name, epic, asset_type))
                    
                    result = cursor.fetchone()
                    conn.commit()

            if result and result[0]:
                logger.info(f"Saved discovered symbol: {ticker} -> {epic} -> {display_name}")
                return True
            else:
                logger.error(f"Database function returned no result for {ticker}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to save {ticker} to database: {e}")
            return False
    
    # --- REMOVED --- _get_symbol_variations and _discover_epic are replaced by search.

    # --- NEW METHOD --- Implements the actual API search call.
    async def search_markets(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Calls the IG API to search for markets matching the search_term.
        It now correctly handles the Pandas DataFrame returned by the library.
        """
        if not self.authenticated:
            if not await self.authenticate():
                return []
                
        logger.info(f"IG: Searching for markets matching '{search_term}'")
        try:
            # The trading_ig library returns a Pandas DataFrame
            markets_df: pd.DataFrame = await asyncio.to_thread(
                self.ig_service.search_markets, search_term
            )
            
            # --- FIX 1: Use .empty to check for results ---
            if markets_df.empty:
                logger.warning(f"IG: No markets found for search term '{search_term}'")
                return []
            
            # --- FIX 2: Convert DataFrame to the expected List[Dict] format ---
            return markets_df.to_dict(orient='records')

        except Exception as e:
            logger.error(f"IG: Error searching markets for '{search_term}': {e}")
            return []


    # --- REPLACED --- This is the new, intelligent discovery workflow.
    async def _discover_and_enhance_symbol(self, ticker: str) -> Optional[Dict]:
        """
        New workflow: search for a symbol, filter results, select the best match,
        get its metadata, and save it to the database.
        """
        logger.info(f"Starting new discovery process for symbol: {ticker}")
        search_term = ticker.upper()

        # Step 1: Search for the symbol
        search_results = await self.search_markets(search_term)
        if not search_results:
            return None

        # Step 2: Filter for the best candidates
        candidates = [
            m for m in search_results
            if m.get('marketStatus') == 'TRADEABLE' and m.get('streamingPricesAvailable') is True
        ]
        
        if not candidates:
            logger.warning(f"No TRADEABLE market with streaming prices found for {search_term}")
            return None

        # Step 3: Select the best match
        best_match = None
        if len(candidates) == 1:
            best_match = candidates[0]
        else:
            # Tie-breaker logic: prefer exact instrument name match, otherwise take the first
            exact_matches = [m for m in candidates if m.get('instrumentName', '').lower() == search_term.lower()]
            best_match = exact_matches[0] if exact_matches else candidates[0]
        
        epic = best_match['epic']
        logger.info(f"Selected best match for {search_term}: EPIC {epic}")

        # Step 4: Get enhanced metadata for the chosen EPIC
        metadata = await self._get_market_metadata(epic)
        display_name = ticker  # Fallback
        asset_type = 'stock' # Fallback
        
        if metadata:
            display_name = metadata.get('clean_name', display_name)
            asset_type = self._infer_asset_type(ticker, epic, metadata)

        # Step 5: Save to database
        if self._save_discovered_symbol(ticker, epic, display_name, asset_type):
            return {
                'symbol': ticker, 'epic': epic, 'display_name': display_name, 'asset_type': asset_type
            }
        
        return None

    # --- NO CHANGES to _get_market_metadata, _clean_instrument_name, or _infer_asset_type ---
    async def _get_market_metadata(self, epic: str) -> Optional[Dict]:
        """Get market metadata including display name from IG API"""
        if not self.authenticated:
            if not await self.authenticate(): return None
        try:
            await asyncio.sleep(0.5) # Reduced rate limit delay
            market_data = await asyncio.to_thread(self.ig_service.fetch_market_by_epic, epic)
            if not market_data or 'instrument' not in market_data:
                logger.warning(f"No instrument data for EPIC {epic}")
                return None
            instrument = market_data['instrument']
            metadata = {
                'epic': epic, 'name': instrument.get('name', ''),
                'type': instrument.get('type', ''), 'market_id': instrument.get('marketId', ''),
                'currency': instrument.get('currencies', [{}])[0].get('code') if instrument.get('currencies') else None,
                'country': instrument.get('country', ''),
            }
            if metadata['name']:
                metadata['clean_name'] = self._clean_instrument_name(metadata['name'])
            logger.debug(f"Retrieved metadata for {epic}: {metadata['name']}")
            return metadata
        except Exception as e:
            logger.error(f"Failed to get metadata for {epic}: {e}")
            return None

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

    # --- NO CHANGES to authenticate or _normalize_price ---
    async def authenticate(self) -> bool:
        """Authenticate with IG Index"""
        try:
            if not all([settings.ig_username, settings.ig_password, settings.ig_api_key]):
                logger.error("IG credentials not configured")
                return False
            
            config.username = settings.ig_username
            config.password = settings.ig_password
            config.api_key = settings.ig_api_key
            config.acc_type = settings.ig_acc_type
            
            self.ig_service = IGService(config.username, config.password, config.api_key, config.acc_type)
            
            await asyncio.to_thread(self.ig_service.create_session)
            self.authenticated = True
            logger.info(f"IG Index authenticated ({config.acc_type})")
            return True
            
        except Exception as e:
            logger.error(f"IG authentication failed: {e}")
            self.authenticated = False
            return False

    def _normalize_price(self, price: float, epic: str) -> float:
        """Normalize IG prices to standard format"""
        if epic.startswith(('UA.D.', 'UB.D.', 'UC.D.', 'UD.D.', 'UE.D.', 'UF.D.', 'UG.D.', 'UH.D.', 'UI.D.', 'UJ.D.', 'SH.D.', 'SA.D.', 'SB.D.', 'SC.D.', 'SD.D.', 'SE.D.', 'SF.D.', 'SG.D.', 'SI.D')) and epic.endswith('.DAILY.IP'):
            return price / 100
        return price

    # --- UPDATED get_price --- This method's logic remains the same, but it now calls the new discovery function.
    async def get_price(self, ticker: str) -> Optional[PriceData]:
        """Get price for ticker - database-first approach with search-based discovery"""
        if not self.authenticated:
            if not await self.authenticate():
                return None
        
        ticker = ticker.upper()
        
        # Step 1: Look up symbol in database
        symbol_data = self._lookup_symbol_in_db(ticker)
        
        # Step 2: If not found, discover and save using the NEW method
        if not symbol_data:
            # This now calls our new, smarter discovery function
            symbol_data = await self._discover_and_enhance_symbol(ticker)
            if not symbol_data:
                logger.warning(f"Could not find or discover {ticker}")
                return None
        
        epic = symbol_data['epic']
        if not epic:
            logger.warning(f"No EPIC available for {ticker}")
            return None
        
        try:
            market_data = await asyncio.to_thread(self.ig_service.fetch_market_by_epic, epic)
            
            if not market_data or 'snapshot' not in market_data:
                logger.warning(f"No data for {ticker} ({epic})")
                return None
            
            snapshot = market_data['snapshot']
            raw_price = float(snapshot.get('bid', 0) or snapshot.get('offer', 0))
            if raw_price == 0:
                logger.warning(f"Zero price for {ticker}")
                return None
            
            price = self._normalize_price(raw_price, epic)
            change_percent = float(snapshot.get('percentageChange', 0))
            change_absolute = float(snapshot.get('netChange', 0))
            
            if epic.startswith(('UA.D.', 'UB.D.', 'UC.D.', 'UD.D.', 'UE.D.', 'UF.D.', 'UG.D.', 'UH.D.', 'UI.D.', 'UJ.D.', 'SH.D.', 'SA.D.', 'SB.D.', 'SC.D.', 'SD.D.', 'SE.D.', 'SF.D.', 'SG.D.')):
                change_absolute = change_absolute / 100
            
            return PriceData(
                symbol=ticker, asset_type=AssetType.EQUITY, price=price,
                change_percent=change_percent, change_absolute=change_absolute,
                volume=None, timestamp=datetime.utcnow(), source="ig_index"
            )
            
        except Exception as e:
            logger.error(f"IG API error for {ticker}: {e}")
            return None
            
    # --- NO CHANGES to get_bulk_prices, can_handle_symbol, or health_check ---
    async def get_bulk_prices(self, tickers: List[str]) -> List[Optional[PriceData]]:
        """Get prices for multiple tickers with proper rate limiting"""
        results = []
        for ticker in tickers:
            result = await self.get_price(ticker)
            results.append(result)
        return results
    
    def can_handle_symbol(self, ticker: str) -> bool:
        """Check if we can handle this ticker"""
        ticker = ticker.upper()
        return (len(ticker) <= 6 and 
                ticker.replace('.', '').isalpha() and 
                not ticker.startswith('^') and
                not ticker.endswith('=X') and
                not ticker.endswith('=F'))
    
    async def health_check(self) -> bool:
        """Check if IG API and database are working."""
        try:
            with psycopg2.connect(**self._get_db_params()) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1;")
            
            if not self.authenticated:
                return await self.authenticate()
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False