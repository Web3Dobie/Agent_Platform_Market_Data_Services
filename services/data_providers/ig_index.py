# ==============================================================================
# IG INDEX PROVIDER - DATABASE-FIRST REFACTOR
# services/data_providers/ig_index.py
# ==============================================================================

from trading_ig import IGService
from trading_ig.config import config
import asyncio
import psycopg2
import psycopg2.extras
import os
from typing import Optional, List, Dict
from datetime import datetime
from app.models import PriceData, AssetType
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class IGIndexProvider:
    """IG Index API with database-first symbol management"""
    
    def __init__(self):
        self.ig_service = None
        self.authenticated = False
        self.db_connection = None
        
        # All known prefixes to try for discovery
        self.prefixes = [
            'UA', 'UB', 'UC', 'UD', 'UE', 'UF', 'UG', 'UH', 'UI', 'UJ',
            'SA', 'SB', 'SC', 'SD', 'SE', 'SF', 'SG', 'SH',
            'IX', 'CS', 'CC', 'MT', 'SI'
        ]
        
        logger.info("IG Index provider initialized with database-first approach")
    
    def _get_db_connection(self):
        """Get database connection, create if needed"""
        if self.db_connection is None or self.db_connection.closed:
            try:
                self.db_connection = psycopg2.connect(
                    host=os.getenv('DB_HOST', 'localhost'),
                    port=os.getenv('DB_PORT', '5432'),
                    database=os.getenv('DB_NAME', os.getenv('DB_DATABASE', 'agents_platform')),
                    user=os.getenv('DB_USER', 'admin'),
                    password=os.getenv('DB_PASSWORD', 'secure_agents_password')
                )
                logger.debug("Connected to PostgreSQL database")
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                raise
        return self.db_connection
    
    def _lookup_symbol_in_db(self, ticker: str) -> Optional[Dict]:
        """Look up symbol in database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute("""
                SELECT id, symbol, display_name, epic, asset_type, active
                FROM hedgefund_agent.stock_universe 
                WHERE symbol = %s AND active = TRUE;
            """, (ticker.upper(),))
            
            result = cursor.fetchone()
            cursor.close()
            
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
        """Save newly discovered symbol to database using the database function"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Use the existing database function
            cursor.execute("""
                SELECT add_discovered_symbol(%s, %s, %s, %s);
            """, (ticker.upper(), display_name, epic, asset_type))
            
            result = cursor.fetchone()
            conn.commit()
            cursor.close()
            
            if result and result[0]:
                logger.info(f"Saved discovered symbol: {ticker} -> {epic} -> {display_name}")
                return True
            else:
                logger.error(f"Database function returned no result for {ticker}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to save {ticker} to database: {e}")
            if conn:
                conn.rollback()
            return False
    
    def _get_symbol_variations(self, ticker: str) -> List[str]:
        """Generate symbol variations to try"""
        variations = [
            ticker,                 # ABBV
            f"{ticker}US",         # ABBVUS  
        ]
        return variations
    
    async def _discover_epic(self, ticker: str) -> Optional[str]:
        """Try to discover EPIC for ticker using all prefix/suffix combinations"""
        
        original_ticker = ticker.upper()
        logger.info(f"Discovering EPIC for {original_ticker}")
        
        variations = self._get_symbol_variations(original_ticker)
        
        for variation in variations:
            for prefix in self.prefixes:
                epic = f"{prefix}.D.{variation}.DAILY.IP"
                
                try:
                    # Test if this EPIC works
                    market_data = await asyncio.to_thread(
                        self.ig_service.fetch_market_by_epic, epic
                    )
                    
                    if market_data and 'snapshot' in market_data:
                        logger.info(f"Discovered EPIC: {original_ticker} -> {epic}")
                        return epic
                        
                except Exception:
                    # Small delay to avoid rate limits
                    await asyncio.sleep(2)
                    continue
                    
        logger.warning(f"No EPIC found for {original_ticker}")
        return None
    
    async def _get_market_metadata(self, epic: str) -> Optional[Dict]:
        """Get market metadata including display name from IG API"""
        
        if not self.authenticated:
            if not await self.authenticate():
                return None
        
        try:
            # Rate limiting delay
            await asyncio.sleep(2)
            
            # Fetch market details using existing IG service
            market_data = await asyncio.to_thread(
                self.ig_service.fetch_market_by_epic, epic
            )
            
            if not market_data or 'instrument' not in market_data:
                logger.warning(f"No instrument data for EPIC {epic}")
                return None
            
            instrument = market_data['instrument']
            
            # Extract relevant metadata
            metadata = {
                'epic': epic,
                'name': instrument.get('name', ''),
                'type': instrument.get('type', ''),
                'market_id': instrument.get('marketId', ''),
                'currency': instrument.get('currencies', [{}])[0].get('code') if instrument.get('currencies') else None,
                'country': instrument.get('country', ''),
            }
            
            # Clean the name for better display
            if metadata['name']:
                metadata['clean_name'] = self._clean_instrument_name(metadata['name'])
            
            logger.debug(f"Retrieved metadata for {epic}: {metadata['name']}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get metadata for {epic}: {e}")
            return None
    
    def _clean_instrument_name(self, raw_name: str) -> str:
        """Clean instrument names from IG API for better display"""
        if not raw_name:
            return raw_name
        
        # Remove IG-specific suffixes
        suffixes_to_remove = [
            ' DFB',      # Daily Funded Bet
            ' CFD',      # Contract for Difference  
            ' Cash',     # Cash market
            ' (DFB)',
            ' (CFD)',
            ' - Cash',
            ' - DFB'
        ]
        
        cleaned = raw_name.strip()
        
        for suffix in suffixes_to_remove:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
        
        # Remove double spaces
        cleaned = ' '.join(cleaned.split())
        
        # Specific improvements for common IG naming patterns
        replacements = {
            'US 500': 'S&P 500',
            'US Tech 100': 'NASDAQ 100', 
            'US Wall St 30': 'Dow Jones 30',
            'Wall Street 30': 'Dow Jones 30',
            'UK 100': 'FTSE 100',
            'Germany 40': 'DAX',
            'Japan 225': 'Nikkei 225',
            'Hong Kong 40': 'Hang Seng',
            'France 40': 'CAC 40',
            'Spain 35': 'IBEX 35',
            'Australia 200': 'ASX 200',
        }
        
        for old, new in replacements.items():
            if old in cleaned:
                cleaned = cleaned.replace(old, new)
        
        return cleaned
    
    def _infer_asset_type(self, ticker: str, epic: str, metadata: Optional[Dict] = None) -> str:
        """Infer asset type from ticker, EPIC, and metadata"""
        ticker = ticker.upper()
        
        # Index patterns
        if (ticker.startswith('^') or 
            ticker in ['SPY', 'QQQ', 'DIA', 'IWM', 'VIX'] or
            epic.startswith('IX.')):
            return 'index'
        
        # Forex patterns
        if (('USD' in ticker and len(ticker) == 6) or
            ticker.endswith('=X') or
            epic.startswith('CS.D.')):
            return 'forex'
        
        # Commodity patterns
        if (ticker in ['GOLD', 'SILVER', 'OIL', 'BRENT', 'NATGAS', 'COPPER'] or
            ticker.endswith('=F') or
            epic.startswith('CC.D.') or epic.startswith('MT.D.')):
            return 'commodity'
        
        # Crypto patterns
        if ticker in ['BTC', 'ETH'] or 'CRYPTO' in (metadata.get('type', '') if metadata else ''):
            return 'crypto'
        
        # Default to stock
        return 'stock'
    
    async def _discover_and_enhance_symbol(self, ticker: str) -> Optional[Dict]:
        """Complete workflow: discover EPIC, get metadata, save to database"""
        
        ticker = ticker.upper()
        
        # Step 1: Try to discover EPIC
        epic = await self._discover_epic(ticker)
        if not epic:
            logger.warning(f"Could not discover EPIC for {ticker}")
            return None
        
        # Step 2: Get enhanced metadata
        metadata = await self._get_market_metadata(epic)
        display_name = ticker  # fallback
        asset_type = 'stock'   # fallback
        
        if metadata:
            if metadata.get('clean_name'):
                display_name = metadata['clean_name']
            asset_type = self._infer_asset_type(ticker, epic, metadata)
        
        # Step 3: Save to database
        success = self._save_discovered_symbol(ticker, epic, display_name, asset_type)
        
        if success:
            return {
                'symbol': ticker,
                'epic': epic,
                'display_name': display_name,
                'asset_type': asset_type
            }
        
        return None
    
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
            
            self.ig_service = IGService(
                config.username, 
                config.password, 
                config.api_key, 
                config.acc_type
            )
            
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
        # Individual stocks need to be divided by 100
        if epic.startswith(('UA.D.', 'UB.D.', 'UC.D.', 'UD.D.', 'UE.D.', 'UF.D.', 'UG.D.', 'UH.D.', 'UI.D.', 'UJ.D.', 'SH.D.', 'SA.D.', 'SB.D.', 'SC.D.', 'SD.D.', 'SE.D.', 'SF.D.', 'SG.D.', 'SI.D')) and epic.endswith('.DAILY.IP'):
            return price / 100
        return price
    
    async def get_price(self, ticker: str) -> Optional[PriceData]:
        """Get price for ticker - database-first approach"""
        
        if not self.authenticated:
            if not await self.authenticate():
                return None
        
        ticker = ticker.upper()
        
        # Step 1: Look up symbol in database
        symbol_data = self._lookup_symbol_in_db(ticker)
        
        # Step 2: If not found, discover and save
        if not symbol_data:
            symbol_data = await self._discover_and_enhance_symbol(ticker)
            if not symbol_data:
                logger.warning(f"Could not find or discover {ticker}")
                return None
        
        epic = symbol_data['epic']
        if not epic:
            logger.warning(f"No EPIC available for {ticker}")
            return None
        
        try:
            # Get market data
            market_data = await asyncio.to_thread(
                self.ig_service.fetch_market_by_epic, epic
            )
            
            if not market_data or 'snapshot' not in market_data:
                logger.warning(f"No data for {ticker} ({epic})")
                return None
            
            snapshot = market_data['snapshot']
            
            # Get price (try bid first, then offer)
            raw_price = float(snapshot.get('bid', 0) or snapshot.get('offer', 0))
            if raw_price == 0:
                logger.warning(f"Zero price for {ticker}")
                return None
            
            # Normalize price
            price = self._normalize_price(raw_price, epic)
            
            # Get change data
            change_percent = float(snapshot.get('percentageChange', 0))
            change_absolute = float(snapshot.get('netChange', 0))
            if epic.startswith(('UA.D.', 'UB.D.', 'UC.D.', 'UD.D.', 'UE.D.', 'UF.D.', 'UG.D.', 'UH.D.', 'UI.D.', 'UJ.D.', 'SH.D.', 'SA.D.', 'SB.D.', 'SC.D.', 'SD.D.', 'SE.D.', 'SF.D.', 'SG.D.')):
                change_absolute = change_absolute / 100
            
            return PriceData(
                symbol=ticker,
                asset_type=AssetType.EQUITY,
                price=price,
                change_percent=change_percent,
                change_absolute=change_absolute,
                volume=None,
                timestamp=datetime.utcnow(),
                source="ig_index"
            )
            
        except Exception as e:
            logger.error(f"IG API error for {ticker}: {e}")
            return None
    
    async def get_bulk_prices(self, tickers: List[str]) -> List[Optional[PriceData]]:
        """Get prices for multiple tickers with proper rate limiting"""
        results = []
        for ticker in tickers:
            result = await self.get_price(ticker)  # Uses existing rate limiting
            results.append(result)
        return results
    
    def can_handle_symbol(self, ticker: str) -> bool:
        """Check if we can handle this ticker"""
        # We can handle any ticker that looks like a stock symbol
        ticker = ticker.upper()
        return (len(ticker) <= 6 and 
                ticker.replace('.', '').isalpha() and 
                not ticker.startswith('^') and
                not ticker.endswith('=X') and
                not ticker.endswith('=F'))
    
    async def health_check(self) -> bool:
        """Check if IG API and database are working"""
        try:
            # Check database connection
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.close()
            
            # Check IG authentication
            if not self.authenticated:
                return await self.authenticate()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def close_connections(self):
        """Close database connections"""
        if self.db_connection and not self.db_connection.closed:
            self.db_connection.close()
            logger.debug("Database connection closed")