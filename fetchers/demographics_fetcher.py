import httpx
import logging
import json
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_demographics():
    """Fetches demographics data for the country from REST Countries API."""
    try:
        url = f"{config.REST_COUNTRIES_URL}/{config.CITY_COUNTRY.lower()}"
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                country_data = data[0]
                
                record = {
                    "fetched_at": datetime.utcnow().isoformat(),
                    "population": country_data.get("population"),
                    "area_km2": country_data.get("area"),
                    "capital": country_data.get("capital", [""])[0],
                    "region": country_data.get("region"),
                    "subregion": country_data.get("subregion"),
                    "languages_json": json.dumps(country_data.get("languages", {})),
                    "currencies_json": json.dumps(country_data.get("currencies", {})),
                    "timezones_json": json.dumps(country_data.get("timezones", [])),
                    "borders_json": json.dumps(country_data.get("borders", []))
                }
                
                database.upsert_dict("demographics_data", record, ["fetched_at"])
                database.log_fetch("demographics", "success", rows_inserted=1)
                
    except Exception as e:
        logger.error(f"Error fetching demographics: {e}")
        database.log_fetch("demographics", "error", error_message=str(e))
