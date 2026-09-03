import httpx
import logging
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_news():
    """Fetches latest news about the city from GNews."""
    if not config.GNEWS_API_KEY:
        logger.warning("GNews API key not found. Skipping news fetch.")
        return
        
    try:
        params = {
            "q": config.CITY_NAME,
            "lang": "en",
            "max": 10,
            "apikey": config.GNEWS_API_KEY
        }
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(config.GNEWS_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            articles = data.get("articles", [])
            rows_inserted = 0
            
            for article in articles:
                record = {
                    "url": article.get("url"),
                    "timestamp": datetime.utcnow().isoformat(),
                    "title": article.get("title"),
                    "description": article.get("description"),
                    "source_name": article.get("source", {}).get("name"),
                    "image_url": article.get("image"),
                    "published_at": article.get("publishedAt")
                }
                
                database.upsert_dict("news_data", record, ["url"])
                rows_inserted += 1
                
            database.log_fetch("news", "success", rows_inserted=rows_inserted)
                
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        database.log_fetch("news", "error", error_message=str(e))
