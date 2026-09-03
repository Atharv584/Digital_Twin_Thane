import httpx
import logging
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_solar_data():
    """Fetches sunrise, sunset, and other solar data from Sunrise-Sunset.io."""
    try:
        params = {
            "lat": config.CITY_LATITUDE,
            "lng": config.CITY_LONGITUDE,
            "formatted": 0 # ISO 8601 format
        }
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(config.SUNRISE_SUNSET_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", {})
            if results:
                record = {
                    "date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "sunrise": results.get("sunrise"),
                    "sunset": results.get("sunset"),
                    "dawn": results.get("dawn"),
                    "dusk": results.get("dusk"),
                    "day_length": str(results.get("day_length")),
                    "solar_noon": results.get("solar_noon"),
                    "timezone": results.get("timezone")
                }
                
                database.upsert_dict("solar_data", record, ["date"])
                database.log_fetch("solar", "success", rows_inserted=1)
                
    except Exception as e:
        logger.error(f"Error fetching solar data: {e}")
        database.log_fetch("solar", "error", error_message=str(e))
