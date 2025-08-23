# ==============================================================================
# IG INDEX PROVIDER - SIMPLIFIED FOR EPIC DISCOVERY
# services/data_providers/ig_index.py
# ==============================================================================

from trading_ig import IGService
from trading_ig.config import config
import asyncio
import json
import os
from typing import Optional, List, Dict
from datetime import datetime
from app.models import PriceData, AssetType
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class IGIndexProvider:
    """IG Index API with EPIC discovery and JSON storage"""
    
    def __init__(self):
        self.ig_service = None
        self.authenticated = False
        
        # JSON file for EPIC mappings
        self.json_file_path = 'config/ig_epic_mappings.json'
        self.epic_mappings = self._load_epic_mappings()
        
        # All known prefixes to try
        self.prefixes = [
            'UA', 'UB', 'UC', 'UD', 'UE', 'UF', 'UG', 'UH', 'UI', 'UJ',
            'SA', 'SB', 'SC', 'SD', 'SE', 'SF', 'SG', 'SH',
            'IX', 'CS', 'CC', 'MT', 'SI'
        ]
        
        logger.info(f"✅ IG Index provider initialized with {len(self.epic_mappings)} mappings")
    
    def _load_epic_mappings(self) -> Dict[str, str]:
        """Load ticker -> EPIC mappings from JSON"""
        try:
            with open(self.json_file_path, 'r') as f:
                data = json.load(f)
                # Extract just the ticker -> epic mappings
                mappings = {}
                for ticker, info in data.items():
                    if ticker != '_metadata' and isinstance(info, dict):
                        epic = info.get('epic', '')
                        if epic:
                            mappings[ticker.upper()] = epic
                    elif isinstance(info, str):
                        # Handle simple string mappings
                        mappings[ticker.upper()] = info
                
                logger.info(f"📂 Loaded {len(mappings)} EPIC mappings from JSON")
                return mappings
        except FileNotFoundError:
            logger.warning(f"❌ JSON file not found: {self.json_file_path}")
            return {}
        except Exception as e:
            logger.error(f"❌ Error loading JSON: {e}")
            return {}
    
    def _save_epic_mapping(self, ticker: str, epic: str):
        """Save new ticker -> EPIC mapping to JSON"""
        try:
            # Load existing data
            try:
                with open(self.json_file_path, 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {}
            
            # Add new mapping
            data[ticker.upper()] = {
                "epic": epic,
                "discovered_date": datetime.now().isoformat()[:10],
                "status": "working"
            }
            
            # Save back to file
            with open(self.json_file_path, 'w') as f:
                json.dump(data, f, indent=2, sort_keys=True)
            
            # Update in-memory cache
            self.epic_mappings[ticker.upper()] = epic
            
            logger.info(f"💾 Saved new mapping: {ticker} -> {epic}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save mapping for {ticker}: {e}")
    
    def _get_symbol_variations(self, ticker: str) -> List[str]:
        """Generate symbol variations to try"""
        variations = [
            ticker,                 # ABBV
            f"{ticker}US",         # ABBVUS  
        ]
        return variations
    
    async def _discover_epic(self, ticker: str) -> Optional[str]:
        """Try to discover EPIC for ticker using all prefix/suffix combinations"""
        
        original_ticker = ticker.upper()   # keep the one from index_constituents
        logger.info(f"🔍 Discovering EPIC for {original_ticker}")
        
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
                        logger.info(f"🎯 FOUND: {original_ticker} -> {epic}")
                        self._save_epic_mapping(original_ticker, epic)  # 👈 use original here
                        return epic
                        
                except Exception:
                    # Small delay to avoid rate limits
                    await asyncio.sleep(2)
                    continue
                    
        logger.warning(f"❌ No EPIC found for {original_ticker}")
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
            logger.info(f"✅ IG Index authenticated ({config.acc_type})")
            return True
            
        except Exception as e:
            logger.error(f"❌ IG authentication failed: {e}")
            self.authenticated = False
            return False
    
    def _normalize_price(self, price: float, epic: str) -> float:
        """Normalize IG prices to standard format"""
        # Individual stocks need to be divided by 100
        if epic.startswith(('UA.D.', 'UB.D.', 'UC.D.', 'UD.D.', 'UE.D.', 'UF.D.', 'UG.D.', 'UH.D.', 'UI.D.', 'UJ.D.', 'SH.D.', 'SA.D.', 'SB.D.', 'SC.D.', 'SD.D.', 'SE.D.', 'SF.D.', 'SG.D.', 'SI.D')) and epic.endswith('.DAILY.IP'):
            return price / 100
        return price
    
    async def get_price(self, ticker: str) -> Optional[PriceData]:
        """Get price for ticker - try JSON first, then discovery"""
        
        if not self.authenticated:
            if not await self.authenticate():
                return None
        
        ticker = ticker.upper()
        
        # Step 1: Check JSON mappings
        epic = self.epic_mappings.get(ticker)
        
        # Step 2: If not found, try discovery
        if not epic:
            epic = await self._discover_epic(ticker)
        
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
        """Get prices for multiple tickers"""
        tasks = [self.get_price(ticker) for ticker in tickers]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
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
        """Check if IG API is working"""
        try:
            if not self.authenticated:
                return await self.authenticate()
            return True
        except Exception as e:
            logger.error(f"IG health check failed: {e}")
            return False