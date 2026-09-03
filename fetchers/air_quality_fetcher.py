import httpx
import logging
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_air_quality_modeled():
    """Fetches modeled air quality data from Open-Meteo."""
    try:
        params = {
            "latitude": config.CITY_LATITUDE,
            "longitude": config.CITY_LONGITUDE,
            "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,dust,uv_index,european_aqi",
            "timezone": config.CITY_TIMEZONE
        }
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(config.OPENMETEO_AIR_QUALITY_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            current = data.get("current", {})
            if current:
                timestamp = current.get("time")
                aq_data = {
                    "timestamp": timestamp,
                    "pm25": current.get("pm2_5"),
                    "pm10": current.get("pm10"),
                    "co": current.get("carbon_monoxide"),
                    "no2": current.get("nitrogen_dioxide"),
                    "so2": current.get("sulphur_dioxide"),
                    "o3": current.get("ozone"),
                    "dust": current.get("dust"),
                    "uv_index": current.get("uv_index"),
                    "aqi_europe": current.get("european_aqi")
                }
                
                database.upsert_dict("air_quality_modeled", aq_data, ["timestamp"])
                database.log_fetch("air_quality_modeled", "success", rows_inserted=1)
                
    except Exception as e:
        logger.error(f"Error fetching modeled air quality: {e}")
        database.log_fetch("air_quality_modeled", "error", error_message=str(e))

async def fetch_aqi_history():
    """Fetches past 30 days of hourly historical air quality from Open-Meteo and averages it daily."""
    try:
        from datetime import timedelta
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)
        
        params = {
            "latitude": config.CITY_LATITUDE,
            "longitude": config.CITY_LONGITUDE,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,dust,uv_index,european_aqi",
            "timezone": config.CITY_TIMEZONE
        }
        
        url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            
            if not times:
                return
                
            daily_aggs = {}
            for i in range(len(times)):
                day_str = times[i].split("T")[0]
                if day_str not in daily_aggs:
                    daily_aggs[day_str] = {"pm25": [], "pm10": [], "aqi": [], "co": [], "no2": [], "so2": [], "o3": [], "dust": [], "uv": []}
                    
                def append_val(key, api_key):
                    val = hourly.get(api_key, [])[i] if i < len(hourly.get(api_key, [])) else None
                    if val is not None: daily_aggs[day_str][key].append(val)
                
                append_val("pm25", "pm2_5")
                append_val("pm10", "pm10")
                append_val("aqi", "european_aqi")
                append_val("co", "carbon_monoxide")
                append_val("no2", "nitrogen_dioxide")
                append_val("so2", "sulphur_dioxide")
                append_val("o3", "ozone")
                append_val("dust", "dust")
                append_val("uv", "uv_index")
            
            rows_inserted = 0
            for day, vals in daily_aggs.items():
                def get_avg(key):
                    return sum(vals[key])/len(vals[key]) if vals[key] else None
                    
                record = {
                    "timestamp": f"{day}T00:00:00",
                    "pm25": get_avg("pm25"),
                    "pm10": get_avg("pm10"),
                    "aqi_europe": get_avg("aqi"),
                    "co": get_avg("co"), 
                    "no2": get_avg("no2"), 
                    "so2": get_avg("so2"), 
                    "o3": get_avg("o3"), 
                    "dust": get_avg("dust"), 
                    "uv_index": get_avg("uv")
                }
                
                database.upsert_dict("air_quality_modeled", record, ["timestamp"])
                rows_inserted += 1
                
            database.log_fetch("air_quality_history", "success", rows_inserted=rows_inserted)
            
    except Exception as e:
        logger.error(f"Error fetching historical AQI data: {e}")
        database.log_fetch("air_quality_history", "error", error_message=str(e))

async def fetch_air_quality_stations():
    """Fetches real-time station AQI data from WAQI."""
    if not config.WAQI_API_KEY:
        logger.warning("WAQI API key not found. Skipping station AQI fetch.")
        return
        
    try:
        url = f"{config.WAQI_FEED_URL}/{config.CITY_NAME.lower()}/"
        params = {"token": config.WAQI_API_KEY}
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "ok":
                station_data = data.get("data", {})
                iaqi = station_data.get("iaqi", {})
                time_info = station_data.get("time", {})
                
                # Extract pollutant values safely
                get_val = lambda key: iaqi.get(key, {}).get("v") if key in iaqi else None
                
                record = {
                    "timestamp": time_info.get("iso", datetime.utcnow().isoformat()),
                    "station_name": station_data.get("city", {}).get("name", config.CITY_NAME),
                    "aqi": station_data.get("aqi"),
                    "pm25": get_val("pm25"),
                    "pm10": get_val("pm10"),
                    "o3": get_val("o3"),
                    "no2": get_val("no2"),
                    "so2": get_val("so2"),
                    "co": get_val("co"),
                    "dominant_pollutant": station_data.get("dominentpol")
                }
                
                database.upsert_dict("air_quality_stations", record, ["timestamp", "station_name"])
                database.log_fetch("air_quality_stations", "success", rows_inserted=1)
                
    except Exception as e:
        logger.error(f"Error fetching station air quality: {e}")
        database.log_fetch("air_quality_stations", "error", error_message=str(e))
