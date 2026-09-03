import httpx
import logging
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_earthquakes():
    """Fetches recent earthquakes within 500km of the city from USGS."""
    try:
        params = {
            "format": "geojson",
            "latitude": config.CITY_LATITUDE,
            "longitude": config.CITY_LONGITUDE,
            "maxradiuskm": 500
        }
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(config.USGS_EARTHQUAKE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            features = data.get("features", [])
            rows_inserted = 0
            
            for feature in features:
                props = feature.get("properties", {})
                geom = feature.get("geometry", {})
                coords = geom.get("coordinates", [])
                
                if not coords or len(coords) < 3:
                    continue
                    
                # Time is in milliseconds
                timestamp_ms = props.get("time")
                timestamp = datetime.utcfromtimestamp(timestamp_ms / 1000.0).isoformat() if timestamp_ms else None
                
                record = {
                    "event_id": feature.get("id"),
                    "timestamp": timestamp,
                    "magnitude": props.get("mag"),
                    "depth_km": coords[2],
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "place": props.get("place"),
                    # Approximation for prototyping
                    "distance_from_city_km": None # Could calculate with haversine
                }
                
                database.upsert_dict("earthquake_data", record, ["event_id"])
                rows_inserted += 1
                
        database.log_fetch("earthquakes", "success", rows_inserted=rows_inserted)
                
    except Exception as e:
        logger.error(f"Error fetching earthquake data: {e}")
        database.log_fetch("earthquakes", "error", error_message=str(e))
