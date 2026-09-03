import httpx
import logging
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_marine_data():
    """Fetches marine data (waves, sea temp) from Open-Meteo."""
    try:
        params = {
            "latitude": config.CITY_LATITUDE,
            "longitude": config.CITY_LONGITUDE,
            "current": "wave_height,wave_direction,wave_period,ocean_current_velocity",
            "timezone": config.CITY_TIMEZONE
        }
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(config.OPENMETEO_MARINE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            current = data.get("current", {})
            if current:
                timestamp = current.get("time")
                marine_data = {
                    "timestamp": timestamp,
                    "wave_height": current.get("wave_height"),
                    "wave_direction": current.get("wave_direction"),
                    "wave_period": current.get("wave_period"),
                    "sea_surface_temp": current.get("ocean_temperature"), # Sometimes available depending on precise lat/lon
                    "ocean_current_velocity": current.get("ocean_current_velocity")
                }
                
                database.upsert_dict("marine_data", marine_data, ["timestamp"])
                database.log_fetch("marine_data", "success", rows_inserted=1)
                
    except Exception as e:
        logger.error(f"Error fetching marine data: {e}")
        database.log_fetch("marine_data", "error", error_message=str(e))
