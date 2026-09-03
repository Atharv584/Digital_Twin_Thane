import httpx
import logging
import json
import asyncio
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_poi():
    """Fetches Points of Interest from Overpass API (OSM)."""
    try:
        # Format bbox for Overpass QL: (south, west, north, east)
        bbox = f"({config.CITY_BBOX[0]},{config.CITY_BBOX[1]},{config.CITY_BBOX[2]},{config.CITY_BBOX[3]})"
        
        # Build the Overpass query for multiple categories
        query_parts = []
        for cat_name, cat_data in config.POI_CATEGORIES.items():
            query_parts.append(f'node["{cat_data["tag"]}"="{cat_data["value"]}"]{bbox};')
            
        overpass_query = f"""
        [out:json][timeout:60];
        (
          {' '.join(query_parts)}
        );
        out center;
        """
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                config.OVERPASS_URL, 
                data={"data": overpass_query},
                headers={"User-Agent": config.USER_AGENT}
            )
            response.raise_for_status()
            data = response.json()
            
            elements = data.get("elements", [])
            rows_inserted = 0
            
            for el in elements:
                tags = el.get("tags", {})
                
                # Determine category based on tags
                category = "unknown"
                for cat_name, cat_data in config.POI_CATEGORIES.items():
                    if tags.get(cat_data["tag"]) == cat_data["value"]:
                        category = cat_name
                        break
                        
                record = {
                    "osm_id": el.get("id"),
                    "name": tags.get("name", "Unknown"),
                    "category": category,
                    "subcategory": tags.get("amenity") or tags.get("leisure") or tags.get("public_transport") or "",
                    "latitude": el.get("lat") or el.get("center", {}).get("lat"),
                    "longitude": el.get("lon") or el.get("center", {}).get("lon"),
                    "address": f"{tags.get('addr:street', '')} {tags.get('addr:city', '')}".strip(),
                    "tags_json": json.dumps(tags)
                }
                
                if record["latitude"] and record["longitude"]:
                    database.upsert_dict("poi_data", record, ["osm_id"])
                    rows_inserted += 1
                
        database.log_fetch("poi", "success", rows_inserted=rows_inserted)
                
    except Exception as e:
        logger.error(f"Error fetching POI data: {e}")
        database.log_fetch("poi", "error", error_message=str(e))
