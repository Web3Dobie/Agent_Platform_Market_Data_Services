# ==============================================================================
# DYNAMIC SYMBOL NORMALIZER - Pattern-Based IG Index Conversion
# services/symbol_normalizer.py
# Handles 1000s of symbols without static mappings
# ==============================================================================

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class NormalizedSymbol:
    """Result of symbol normalization"""
    original: str           # Original symbol from content ($WMT, WMT)
    clean_symbol: str       # Clean symbol (WMT)
    ig_epic: str           # IG Index epic (UA.D.WMT.DAILY.IP)
    asset_type: str        # Type: stock, index, forex, commodity
    confidence: float      # Confidence in classification (0.0-1.0)

class DynamicSymbolNormalizer:
    """
    Dynamic symbol normalizer that builds IG Index epic codes on-the-fly
    No static mappings needed - scales to 1000s of symbols
    """
    
    def __init__(self):
        # Known patterns for different asset types
        self.index_patterns = {
            r'^\^': 'index',           # ^GSPC, ^DJI, ^IXIC
            r'SPY|QQQ|IWM': 'etf',     # Major ETFs
        }
        
        self.forex_patterns = {
            r'[A-Z]{6}=X$': 'forex',   # EURUSD=X, GBPUSD=X
            r'[A-Z]{6}$': 'forex',     # EURUSD, GBPUSD (without =X)
        }
        
        self.commodity_patterns = {
            r'=F$': 'commodity',       # GC=F, CL=F, NG=F
            r'^(GOLD|SILVER|OIL|COPPER)$': 'commodity',  # Word-based commodities
        }
        
        # Known IG Index epic patterns
        self.epic_patterns = {
            'stock': 'UA.D.{symbol}.DAILY.IP',           # Individual stocks
            'index': 'IX.D.{epic}.DAILY.IP',             # Indices (need custom mapping)
            'forex': 'CS.D.{pair}.TODAY.IP',             # Forex pairs
            'commodity': 'CS.D.{commodity}.TODAY.IP',     # Commodities
            'etf': 'UA.D.{symbol}.DAILY.IP',             # ETFs (treated as stocks)
        }
    
    def normalize_symbol(self, raw_symbol: str) -> NormalizedSymbol:
        """
        Convert any symbol format to IG Index epic code
        
        Args:
            raw_symbol: Symbol from content ($WMT, WMT, Walmart, etc.)
            
        Returns:
            NormalizedSymbol with IG Index epic code
        """
        
        # Step 1: Clean the symbol
        clean_symbol = self._clean_symbol(raw_symbol)
        
        # Step 2: Classify asset type
        asset_type, confidence = self._classify_asset_type(clean_symbol)
        
        # Step 3: Build IG Index epic code
        ig_epic = self._build_ig_epic(clean_symbol, asset_type)
        
        return NormalizedSymbol(
            original=raw_symbol,
            clean_symbol=clean_symbol,
            ig_epic=ig_epic,
            asset_type=asset_type,
            confidence=confidence
        )
    
    def _clean_symbol(self, raw_symbol: str) -> str:
        """
        Clean and standardize symbol format
        
        Examples:
            $WMT -> WMT
            $NVDA -> NVDA
            wmt -> WMT
            Walmart -> WMT (if we have company name mapping)
        """
        
        # Remove $ prefix if present
        symbol = raw_symbol.strip().upper()
        if symbol.startswith('$'):
            symbol = symbol[1:]
        
        # Handle common variations
        symbol = symbol.strip()
        
        # Basic validation - must be 1-5 alphanumeric characters for stocks
        if re.match(r'^[A-Z0-9]{1,5}$', symbol):
            return symbol
        
        # Handle special cases like BRK.B
        if re.match(r'^[A-Z]{1,4}\.[A-Z]$', symbol):
            return symbol
        
        # If it doesn't match basic patterns, assume it's a company name
        # You could add company name -> ticker lookup here
        # For now, return as-is
        return symbol
    
    def _classify_asset_type(self, symbol: str) -> Tuple[str, float]:
        """
        Classify symbol into asset type with confidence score
        
        Returns:
            (asset_type, confidence_score)
        """
        
        # Check index patterns
        for pattern, asset_type in self.index_patterns.items():
            if re.search(pattern, symbol):
                return asset_type, 0.95
        
        # Check forex patterns
        for pattern, asset_type in self.forex_patterns.items():
            if re.search(pattern, symbol):
                return asset_type, 0.95
        
        # Check commodity patterns
        for pattern, asset_type in self.commodity_patterns.items():
            if re.search(pattern, symbol):
                return asset_type, 0.95
        
        # Default classification logic
        if len(symbol) <= 5 and symbol.isalpha():
            # Most likely a stock ticker
            return 'stock', 0.85
        elif '.' in symbol and len(symbol) <= 6:
            # Could be BRK.B style stock
            return 'stock', 0.80
        else:
            # Unknown, default to stock
            return 'stock', 0.50
    
    def _build_ig_epic(self, symbol: str, asset_type: str) -> str:
        """
        Build IG Index epic code dynamically
        
        Args:
            symbol: Clean symbol (WMT, NVDA, etc.)
            asset_type: Type of asset (stock, index, forex, etc.)
            
        Returns:
            IG Index epic code (UA.D.WMT.DAILY.IP)
        """
        
        if asset_type in ['stock', 'etf']:
            # Pattern: UA.D.{SYMBOL}.DAILY.IP
            return f"UA.D.{symbol}.DAILY.IP"
        
        elif asset_type == 'forex':
            # Convert EURUSD=X -> EURUSD, then to CS.D.EURUSD.TODAY.IP
            pair = symbol.replace('=X', '')
            return f"CS.D.{pair}.TODAY.IP"
        
        elif asset_type == 'commodity':
            # Handle different commodity formats
            if symbol.endswith('=F'):
                # GC=F -> Gold mapping
                commodity_map = {
                    'GC=F': 'USCGC',    # Gold
                    'SI=F': 'USCSI',    # Silver
                    'CL=F': 'CL',       # Oil WTI
                    'BZ=F': 'LCO',      # Oil Brent
                    'NG=F': 'NG',       # Natural Gas
                    'HG=F': 'HG',       # Copper
                }
                commodity_code = commodity_map.get(symbol, symbol.replace('=F', ''))
                return f"CC.D.{commodity_code}.USS.IP"
            else:
                # Word-based: GOLD -> USCGC
                word_map = {
                    'GOLD': 'USCGC',
                    'SILVER': 'USCSI',
                    'OIL': 'CL',
                    'COPPER': 'HG',
                }
                commodity_code = word_map.get(symbol, symbol)
                return f"CS.D.{commodity_code}.TODAY.IP"
        
        elif asset_type == 'index':
            # Indices need special mapping, but we can try a pattern
            index_map = {
                '^GSPC': 'SPTRD',
                '^DJI': 'DOW',
                '^IXIC': 'NASDAQ',
                '^RUT': 'RUSSELL',
                'SPY': 'SPTRD',     # S&P 500 ETF
                'QQQ': 'NASDAQ',    # Nasdaq ETF
                'IWM': 'RUSSELL',   # Russell 2000 ETF
            }
            index_code = index_map.get(symbol, symbol.replace('^', ''))
            return f"IX.D.{index_code}.DAILY.IP"
        
        else:
            # Default to stock format
            return f"UA.D.{symbol}.DAILY.IP"
    
    def extract_and_normalize_symbols(self, text: str) -> List[NormalizedSymbol]:
        """
        Extract all symbols from text and normalize them
        
        Args:
            text: Content text containing symbols like "$WMT gains 5%"
            
        Returns:
            List of normalized symbols ready for IG Index API
        """
        
        symbols = []
        
        # Pattern 1: Cashtags ($SYMBOL)
        cashtag_pattern = r'\$([A-Z]{1,5}(?:\.[A-Z])?)'
        cashtags = re.findall(cashtag_pattern, text, re.IGNORECASE)
        
        # Pattern 2: Standalone tickers (more careful matching)
        # Look for 1-5 letter combinations that are likely tickers
        standalone_pattern = r'\b([A-Z]{2,5})\b(?=\s+(?:stock|shares|gained|lost|up|down|jumped|fell))'
        standalone = re.findall(standalone_pattern, text)
        
        # Combine all found symbols
        all_symbols = list(set(cashtags + standalone))
        
        # Normalize each symbol
        for symbol in all_symbols:
            try:
                normalized = self.normalize_symbol(symbol)
                symbols.append(normalized)
                logger.debug(f"Normalized {symbol} -> {normalized.ig_epic}")
            except Exception as e:
                logger.warning(f"Failed to normalize symbol {symbol}: {e}")
        
        return symbols


# ==============================================================================
# USAGE EXAMPLES AND API INTEGRATION
# ==============================================================================

class MarketDataQueryBuilder:
    """
    Builds market data queries using the dynamic normalizer
    Integrates with your existing market data microservice
    """
    
    def __init__(self, microservice_url: str = "http://localhost:8001"):
        self.normalizer = DynamicSymbolNormalizer()
        self.microservice_url = microservice_url
    
    def build_query_for_content(self, content_text: str) -> Dict:
        """
        Extract symbols from content and build market data queries
        
        Args:
            content_text: Text like "Apple ($AAPL) and Walmart ($WMT) both gained today"
            
        Returns:
            Query dict ready for your microservice
        """
        
        # Extract and normalize symbols
        normalized_symbols = self.normalizer.extract_and_normalize_symbols(content_text)
        
        if not normalized_symbols:
            return {"symbols": [], "message": "No symbols found in content"}
        
        # Build query for microservice
        query = {
            "symbols": [sym.clean_symbol for sym in normalized_symbols],  # Use clean symbols for API
            "ig_epics": [sym.ig_epic for sym in normalized_symbols],      # IG epic codes for reference
            "original_mentions": [sym.original for sym in normalized_symbols],  # Original mentions
            "asset_types": [sym.asset_type for sym in normalized_symbols],
            "microservice_urls": [
                f"{self.microservice_url}/prices/{sym.clean_symbol}" 
                for sym in normalized_symbols
            ]
        }
        
        return query
    
    def single_symbol_query(self, symbol: str) -> str:
        """
        Convert single symbol to microservice URL
        
        Args:
            symbol: Any symbol format ($WMT, WMT, etc.)
            
        Returns:
            Microservice URL ready to call
        """
        
        normalized = self.normalizer.normalize_symbol(symbol)
        return f"{self.microservice_url}/prices/{normalized.clean_symbol}"


# ==============================================================================
# QUICK TEST FUNCTION
# ==============================================================================

def test_normalizer():
    """Quick test function"""
    normalizer = DynamicSymbolNormalizer()
    
    test_symbols = ["WMT", "$NVDA", "AAPL", "MSFT", "GOOGL"]
    
    for symbol in test_symbols:
        result = normalizer.normalize_symbol(symbol)
        print(f"{symbol:6} -> {result.ig_epic} (confidence: {result.confidence:.2f})")

if __name__ == "__main__":
    test_normalizer()