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
        # ... (rest of the API call and data processing logic is the same)
        today_str = datetime.now().strftime('%Y-%m-%d')
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 25,
            "realtime_start": today_str, # <-- Add this line
            "realtime_end": today_str,   # <-- Add this line
        }
        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if not data.get("observations"): return None
            # ... (full data processing)
            observations = [obs for obs in data["observations"] if obs["value"] != "."]
            if len(observations) < 2: return None
            latest = observations[0]
            previous = observations[1]
            year_ago = observations[12] if len(observations) > 12 else None
            latest_value = float(latest["value"])
            previous_value = float(previous["value"])
            formatted_data = {
                "name": series_name, "series_id": series_id, "latest_value": latest_value,
                "latest_date": latest["date"], "change_from_previous": round(latest_value - previous_value, 2),
                "percent_change_from_previous": round(((latest_value - previous_value) / previous_value) * 100, 2),
                "history": [{"date": obs["date"], "value": float(obs["value"])} for obs in observations[:3]]
            }
            if year_ago:
                year_ago_value = float(year_ago["value"])
                formatted_data["percent_change_year_ago"] = round(((latest_value - year_ago_value) / year_ago_value) * 100, 2)

            self.cache.set(cache_key, formatted_data, ttl=settings.macro_cache_ttl)
            return formatted_data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from FRED for {series_id}: {e}")
            return None