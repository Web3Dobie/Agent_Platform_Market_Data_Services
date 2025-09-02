# services/data_providers/fred_service.py

import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from config.settings import settings
from services.cache_service import CacheService

class FredService:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str = settings.fred_api_key):
        if not api_key:
            raise ValueError("FRED_API_KEY is not configured.")
        self.api_key = api_key
        # The cache now connects automatically when created
        self.cache = CacheService()

    # This is now a regular synchronous method
    def get_series_data(self, series_id: str, series_name: str) -> Optional[Dict[str, Any]]:
        cache_key = f"fred:{series_id}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            print(f"Cache HIT for FRED series: {series_id}")
            return cached_data

        print(f"Cache MISS for FRED series: {series_id}. Fetching from API.")
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # --- START OF FINAL FIX ---

        is_pmi = (series_id == 'PMI')
        
        # Default parameters for all normal, well-behaved series
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 25,
            "realtime_start": today_str,
            "realtime_end": today_str,
        }

        # Special handling for the problematic PMI series
        if is_pmi:
            # For PMI, we cannot use 'sort_order' or 'realtime' dates.
            # We must fetch a range in ascending order and take the last value.
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                # Fetch the last 2 years of data to ensure we get the latest
                "observation_start": (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
            }

        # --- END OF FINAL FIX ---

        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get("observations"): return None

            observations = [obs for obs in data["observations"] if obs["value"] != "."]
            if len(observations) < 2: return None

            # If it was PMI, the latest is the LAST item; otherwise, it's the first
            if is_pmi:
                latest = observations[-1]
                previous = observations[-2]
                year_ago = observations[-13] if len(observations) > 12 else None
            else: # Standard logic for all other series
                latest = observations[0]
                previous = observations[1]
                year_ago = observations[12] if len(observations) > 12 else None

            latest_value = float(latest["value"])
            previous_value = float(previous["value"])
            
            formatted_data = {
                "name": series_name, "series_id": series_id, "latest_value": latest_value,
                "latest_date": latest["date"], "change_from_previous": round(latest_value - previous_value, 2),
                "percent_change_from_previous": round(((latest_value - previous_value) / previous_value) * 100, 2) if previous_value != 0 else 0,
                "history": [{"date": obs["date"], "value": float(obs["value"])} for obs in observations[-3:]] # Always take last 3
            }

            if year_ago:
                year_ago_value = float(year_ago["value"])
                if year_ago_value != 0:
                    formatted_data["percent_change_year_ago"] = round(((latest_value - year_ago_value) / year_ago_value) * 100, 2)

            self.cache.set(cache_key, formatted_data, ttl=settings.macro_cache_ttl)
            return formatted_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from FRED for {series_id}: {e}")
            return None