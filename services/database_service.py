# services/database_service.py
import psycopg2
import psycopg2.extras
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseService:
    """Database service for Market Data Service - handles symbol metadata queries"""
    
    def __init__(self, db_config: dict):
        """
        Initialize database service with connection config
        
        Args:
            db_config: Dictionary with host, port, database, user, password
        """
        self.db_config = db_config
        self._connection = None
        logger.info("Database service initialized")
    
    def get_connection(self):
        """Get or create database connection"""
        if self._connection is None or self._connection.closed:
            try:
                self._connection = psycopg2.connect(**self.db_config)
                self._connection.autocommit = False
                logger.info("Connected to PostgreSQL")
            except Exception as e:
                logger.error(f"Database connection failed: {e}")
                raise
        return self._connection
    
    def close_connection(self):
        """Close database connection"""
        if self._connection and not self._connection.closed:
            self._connection.close()
            logger.info("Database connection closed")
    
    def get_symbols_by_asset_type(
        self, 
        asset_type: str, 
        limit: int = 100, 
        offset: int = 0,
        active_only: bool = True
    ) -> Dict:
        """
        Get symbols filtered by asset type with pagination
        
        Args:
            asset_type: Filter by asset type (index, forex, commodity, crypto, stock)
            limit: Maximum number of results
            offset: Number of results to skip
            active_only: Only return active symbols
            
        Returns:
            Dictionary with symbols list and pagination info
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Build base query
            base_query = """
                SELECT symbol, display_name, epic, asset_type, active, discovered_at, last_updated
                FROM hedgefund_agent.stock_universe
                WHERE 1=1
            """
            
            count_query = """
                SELECT COUNT(*) 
                FROM hedgefund_agent.stock_universe
                WHERE 1=1
            """
            
            params = []
            
            # Add active filter
            if active_only:
                base_query += " AND active = %s"
                count_query += " AND active = %s"
                params.append(True)
            
            # Add asset type filter
            if asset_type:
                base_query += " AND asset_type = %s"
                count_query += " AND asset_type = %s"
                params.append(asset_type)
            
            # Add ordering and pagination to base query
            base_query += " ORDER BY symbol LIMIT %s OFFSET %s"
            query_params = params + [limit, offset]
            
            # Execute queries
            cursor.execute(base_query, query_params)
            symbols = cursor.fetchall()
            
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]
            
            # Format response
            symbol_list = []
            for row in symbols:
                symbol_list.append({
                    "symbol": row['symbol'],
                    "display_name": row['display_name'],
                    "epic": row['epic'],
                    "asset_type": row['asset_type'],
                    "active": row['active'],
                    "discovered_at": row['discovered_at'],
                    "last_updated": row['last_updated']
                })
            
            response = {
                "symbols": symbol_list,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total_count": total_count,
                    "returned_count": len(symbol_list)
                },
                "filters": {
                    "asset_type": asset_type,
                    "active_only": active_only
                }
            }
            
            logger.info(f"Retrieved {len(symbol_list)} symbols (asset_type={asset_type})")
            return response
            
        except Exception as e:
            logger.error(f"Failed to get symbols by asset type: {e}")
            raise
        finally:
            cursor.close()
    
    def get_all_symbols(
        self, 
        limit: int = 200, 
        offset: int = 0,
        active_only: bool = True
    ) -> Dict:
        """
        Get all symbols with pagination
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            active_only: Only return active symbols
            
        Returns:
            Dictionary with symbols list and pagination info
        """
        return self.get_symbols_by_asset_type(
            asset_type=None, 
            limit=limit, 
            offset=offset, 
            active_only=active_only
        )
    
    def get_symbols_by_patterns(
        self, 
        asset_type: str, 
        patterns: List[str], 
        active_only: bool = True
    ) -> List[Dict]:
        """
        Get symbols matching specific patterns within an asset type
        
        Args:
            asset_type: Asset type to filter by
            patterns: List of patterns to match in symbol names
            active_only: Only return active symbols
            
        Returns:
            List of matching symbols
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Build pattern matching conditions
            pattern_conditions = []
            params = []
            
            for pattern in patterns:
                pattern_conditions.append("symbol ILIKE %s")
                params.append(f"%{pattern}%")
            
            query = f"""
                SELECT symbol, display_name, epic, asset_type, active, discovered_at, last_updated
                FROM hedgefund_agent.stock_universe
                WHERE asset_type = %s
                AND ({' OR '.join(pattern_conditions)})
            """
            
            params = [asset_type] + params
            
            if active_only:
                query += " AND active = %s"
                params.append(True)
            
            query += " ORDER BY symbol"
            
            cursor.execute(query, params)
            symbols = cursor.fetchall()
            
            symbol_list = []
            for row in symbols:
                symbol_list.append({
                    "symbol": row['symbol'],
                    "display_name": row['display_name'],
                    "epic": row['epic'],
                    "asset_type": row['asset_type'],
                    "active": row['active'],
                    "discovered_at": row['discovered_at'],
                    "last_updated": row['last_updated']
                })
            
            logger.info(f"Found {len(symbol_list)} symbols matching patterns {patterns}")
            return symbol_list
            
        except Exception as e:
            logger.error(f"Failed to get symbols by patterns: {e}")
            raise
        finally:
            cursor.close()
    
    def get_symbol_by_epic(self, epic: str) -> Optional[Dict]:
        """
        Get symbol details by IG epic code
        
        Args:
            epic: IG Index epic code
            
        Returns:
            Symbol dictionary or None if not found
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute("""
                SELECT symbol, display_name, epic, asset_type, active, discovered_at, last_updated
                FROM hedgefund_agent.stock_universe
                WHERE epic = %s
            """, (epic,))
            
            row = cursor.fetchone()
            
            if row:
                return {
                    "symbol": row['symbol'],
                    "display_name": row['display_name'],
                    "epic": row['epic'],
                    "asset_type": row['asset_type'],
                    "active": row['active'],
                    "discovered_at": row['discovered_at'],
                    "last_updated": row['last_updated']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get symbol by epic {epic}: {e}")
            raise
        finally:
            cursor.close()
    
    def get_symbol_by_name(self, symbol: str) -> Optional[Dict]:
        """
        Get symbol details by symbol name
        
        Args:
            symbol: Symbol name (e.g., 'AAPL', 'BTC')
            
        Returns:
            Symbol dictionary or None if not found
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute("""
                SELECT symbol, display_name, epic, asset_type, active, discovered_at, last_updated
                FROM hedgefund_agent.stock_universe
                WHERE symbol = %s
            """, (symbol.upper(),))
            
            row = cursor.fetchone()
            
            if row:
                return {
                    "symbol": row['symbol'],
                    "display_name": row['display_name'],
                    "epic": row['epic'],
                    "asset_type": row['asset_type'],
                    "active": row['active'],
                    "discovered_at": row['discovered_at'],
                    "last_updated": row['last_updated']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get symbol by name {symbol}: {e}")
            raise
        finally:
            cursor.close()
    
    def get_asset_type_summary(self) -> Dict[str, int]:
        """
        Get count of symbols by asset type
        
        Returns:
            Dictionary mapping asset types to counts
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT asset_type, COUNT(*) 
                FROM hedgefund_agent.stock_universe 
                WHERE active = TRUE
                GROUP BY asset_type
                ORDER BY COUNT(*) DESC
            """)
            
            results = cursor.fetchall()
            
            summary = {}
            total = 0
            for asset_type, count in results:
                summary[asset_type] = count
                total += count
            
            summary['total'] = total
            
            logger.info(f"Asset type summary: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get asset type summary: {e}")
            raise
        finally:
            cursor.close()
    
    def save_discovered_symbol(
        self, 
        symbol: str, 
        epic: str, 
        display_name: str, 
        asset_type: str
    ) -> bool:
        """
        Save a newly discovered symbol to the database
        
        Args:
            symbol: Symbol name
            epic: IG Index epic code
            display_name: Human readable name
            asset_type: Type of asset
            
        Returns:
            True if successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO hedgefund_agent.stock_universe 
                (symbol, epic, display_name, asset_type, active, discovered_at, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) 
                DO UPDATE SET 
                    epic = EXCLUDED.epic,
                    display_name = EXCLUDED.display_name,
                    asset_type = EXCLUDED.asset_type,
                    last_updated = EXCLUDED.last_updated
            """, (
                symbol.upper(),
                epic,
                display_name,
                asset_type,
                True,
                datetime.now(),
                datetime.now()
            ))
            
            conn.commit()
            logger.info(f"Saved symbol: {symbol} -> {epic}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save symbol {symbol}: {e}")
            return False
        finally:
            cursor.close()
    
    def health_check(self) -> Dict:
        """
        Database health check
        
        Returns:
            Dictionary with health status and basic stats
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Test connection and get basic stats
            cursor.execute("SELECT COUNT(*) FROM hedgefund_agent.stock_universe WHERE active = TRUE")
            active_symbols = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT asset_type) FROM hedgefund_agent.stock_universe WHERE active = TRUE")
            asset_types = cursor.fetchone()[0]
            
            cursor.close()
            
            return {
                "status": "healthy",
                "active_symbols": active_symbols,
                "asset_types": asset_types,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Dependency injection function for FastAPI
_db_service_instance = None

def get_database_service() -> DatabaseService:
    """Get database service instance (singleton)"""
    global _db_service_instance
    
    if _db_service_instance is None:
        # Import here to avoid circular imports
        from config.settings import DATABASE_CONFIG
        _db_service_instance = DatabaseService(DATABASE_CONFIG)
    
    return _db_service_instance