import httpx
import logging
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_exchange_rates():
    """Fetches current exchange rates from Frankfurter API."""
    try:
        params = {
            "from": "USD",
            "to": "INR,EUR,GBP"
        }
        
        url = f"{config.FRANKFURTER_URL}/latest"
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            rates = data.get("rates", {})
            date = data.get("date")
            base = data.get("base")
            rows_inserted = 0
            
            for currency, rate in rates.items():
                record = {
                    "date": date,
                    "base_currency": base,
                    "target_currency": currency,
                    "rate": rate
                }
                
                database.upsert_dict("exchange_rates", record, ["date", "target_currency"])
                rows_inserted += 1
                
        database.log_fetch("exchange_rates", "success", rows_inserted=rows_inserted)
                
    except Exception as e:
        logger.error(f"Error fetching exchange rates: {e}")
        database.log_fetch("exchange_rates", "error", error_message=str(e))
