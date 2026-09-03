import httpx
import logging
import asyncio
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_economic_indicators():
    """Fetches economic indicators for the country from World Bank API."""
    try:
        rows_inserted = 0
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            for code, name in config.WORLD_BANK_INDICATORS.items():
                url = f"{config.WORLD_BANK_URL.replace('IND', 'IND')}/{code}" # Assumes IND for India
                params = {"format": "json", "per_page": 20} # Get last 20 years
                
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, list) and len(data) > 1:
                    records = data[1]
                    for record in records:
                        if record.get("value") is not None:
                            db_record = {
                                "indicator_code": code,
                                "year": record.get("date"),
                                "indicator_name": name,
                                "value": record.get("value"),
                                "country_code": record.get("countryiso3code")
                            }
                            database.upsert_dict("economic_indicators", db_record, ["indicator_code", "year"])
                            rows_inserted += 1
                
                # Small delay to respect API limits (though WB is generous)
                await asyncio.sleep(0.5)
                
        database.log_fetch("economic_indicators", "success", rows_inserted=rows_inserted)
                
    except Exception as e:
        logger.error(f"Error fetching economic indicators: {e}")
        database.log_fetch("economic_indicators", "error", error_message=str(e))
