import httpx
import logging
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_flood_data():
    """Fetches flood risk (river discharge) data from Open-Meteo."""
    try:
        params = {
            "latitude": config.CITY_LATITUDE,
            "longitude": config.CITY_LONGITUDE,
            "daily": "river_discharge,river_discharge_mean,river_discharge_max",
            "timezone": config.CITY_TIMEZONE,
            "forecast_days": 1 # Just get today's forecast/current
        }
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(config.OPENMETEO_FLOOD_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            daily = data.get("daily", {})
            if daily and daily.get("time"):
                # Take the first entry (today)
                timestamp = daily.get("time")[0]
                
                flood_data = {
                    "timestamp": timestamp,
                    "river_discharge": daily.get("river_discharge")[0] if daily.get("river_discharge") else None,
                    "river_discharge_mean": daily.get("river_discharge_mean")[0] if daily.get("river_discharge_mean") else None,
                    "river_discharge_max": daily.get("river_discharge_max")[0] if daily.get("river_discharge_max") else None
                }
                
                database.upsert_dict("flood_data", flood_data, ["timestamp"])
                database.log_fetch("flood_data", "success", rows_inserted=1)
                
    except Exception as e:
        logger.error(f"Error fetching flood data: {e}")
        database.log_fetch("flood_data", "error", error_message=str(e))
