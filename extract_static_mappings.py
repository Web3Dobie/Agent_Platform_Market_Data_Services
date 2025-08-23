# ==============================================================================
# EXTRACT STATIC MAPPINGS TO JSON
# Run this script to create the initial ig_epic_mappings.json
# ==============================================================================

import json
import os
from datetime import datetime
from typing import Dict, Any

def extract_static_mappings() -> Dict[str, Any]:
    """Extract all static mappings from your ig_index.py epic_map"""
    
    # Your current static mappings from ig_index.py
    static_mappings = {
        # US EQUITY (all working)
        "^GSPC": "IX.D.SPTRD.DAILY.IP",      # S&P 500
        "SPY": "IX.D.SPTRD.DAILY.IP",        # S&P 500 ETF (alias)
        "^IXIC": "IX.D.NASDAQ.CASH.IP",      # NASDAQ Composite
        "QQQ": "IX.D.NASDAQ.CASH.IP",        # NASDAQ ETF (alias)
        "^DJI": "IX.D.DOW.DAILY.IP",         # Dow Jones
        "^RUT": "IX.D.RUSSELL.DAILY.IP",     # Russell 2000
        "IWM": "IX.D.RUSSELL.DAILY.IP",      # Russell 2000 ETF (alias)
        
        # INDIVIDUAL STOCKS - CONFIRMED WORKING
        "AAPL": "UA.D.AAPL.DAILY.IP",       # Apple Inc - CFD

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
        
        # VIX and Dollar Index (commonly requested)
        "^VIX": "IX.D.VIX.DAILY.IP",         # VIX (if available)
        "VIX": "IX.D.VIX.DAILY.IP",          # VIX alias
        "DXY": "IX.D.DOLLAR.DAILY.IP",       # Dollar Index (if available)
    }
    
    def detect_asset_type(symbol: str, epic: str) -> str:
        """Detect asset type from symbol and epic patterns"""
        symbol_upper = symbol.upper()
        
        # Individual stocks
        if epic.startswith(('UA.D.', 'UC.D.', 'SH.D.')) and epic.endswith('.DAILY.IP'):
            return "stock"
        
        # Indices
        elif epic.startswith('IX.D.') or symbol_upper.startswith('^') or symbol_upper in ['SPY', 'QQQ', 'IWM', 'VIX', 'DXY']:
            return "index"
        
        # Forex
        elif any(fx in symbol_upper for fx in ['USD=X', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD']) or epic.startswith('CS.D.') and epic.endswith('.TODAY.IP'):
            return "forex"
        
        # Commodities
        elif symbol_upper.endswith('=F') or symbol_upper in ['GOLD', 'SILVER', 'OIL', 'BRENT', 'NATGAS', 'COPPER'] or epic.startswith(('CC.D.', 'MT.D.', 'CS.D.USC')):
            return "commodity"
        
        # Default
        else:
            return "unknown"
    
    # Convert to JSON format with metadata
    json_mappings = {}
    current_date = datetime.now().isoformat()[:10]  # YYYY-MM-DD
    
    for symbol, epic in static_mappings.items():
        prefix = epic.split('.')[0] if '.' in epic else ""
        asset_type = detect_asset_type(symbol, epic)
        
        json_mappings[symbol] = {
            "epic": epic,
            "asset_type": asset_type,
            "prefix": prefix,
            "discovery_method": "migrated",
            "discovered_date": current_date,
            "last_verified": current_date,
            "status": "working",
            "notes": "Migrated from static mappings"
        }
    
    return json_mappings

def create_ig_epic_mappings_file():
    """Create the ig_epic_mappings.json file"""
    
    # Create config directory if it doesn't exist
    os.makedirs('config', exist_ok=True)
    
    # Extract mappings
    mappings = extract_static_mappings()
    
    # Create metadata for the file
    file_metadata = {
        "_metadata": {
            "version": "1.0",
            "created_date": datetime.now().isoformat(),
            "total_mappings": len(mappings),
            "description": "IG Index epic code mappings",
            "auto_discovery_enabled": True,
            "last_bulk_verification": None,
            "known_prefixes": sorted(list(set(
                data["prefix"] for data in mappings.values() if data["prefix"]
            )))
        }
    }
    
    # Combine metadata and mappings
    full_data = {**file_metadata, **mappings}
    
    # Write to JSON file
    output_file = 'config/ig_epic_mappings.json'
    with open(output_file, 'w') as f:
        json.dump(full_data, f, indent=2, sort_keys=True)
    
    print(f"✅ Created {output_file}")
    print(f"📊 Migrated {len(mappings)} symbols")
    
    # Print summary by asset type
    asset_type_counts = {}
    prefix_counts = {}
    
    for data in mappings.values():
        asset_type = data["asset_type"]
        prefix = data["prefix"]
        
        asset_type_counts[asset_type] = asset_type_counts.get(asset_type, 0) + 1
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    
    print("\n📋 Asset Type Distribution:")
    for asset_type, count in sorted(asset_type_counts.items()):
        print(f"   {asset_type:10}: {count:3} symbols")
    
    print("\n🏷️  Prefix Distribution:")
    for prefix, count in sorted(prefix_counts.items()):
        print(f"   {prefix:6}: {count:3} symbols")
    
    print(f"\n💾 File location: {os.path.abspath(output_file)}")
    
    # Create backup of original static mappings
    backup_file = 'config/static_mappings_backup.json'
    static_only = extract_static_mappings()
    
    # Remove metadata for backup (just the raw mappings)
    backup_data = {symbol: data["epic"] for symbol, data in static_only.items()}
    
    with open(backup_file, 'w') as f:
        json.dump(backup_data, f, indent=2, sort_keys=True)
    
    print(f"💾 Backup created: {os.path.abspath(backup_file)}")
    
    return output_file

if __name__ == "__main__":
    create_ig_epic_mappings_file()