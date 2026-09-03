import httpx
import logging
from datetime import datetime
import config
import database

logger = logging.getLogger(__name__)

async def fetch_weather():
    """Fetches current and 7-day hourly forecast from Open-Meteo."""
    try:
        params = {
            "latitude": config.CITY_LATITUDE,
            "longitude": config.CITY_LONGITUDE,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,surface_pressure,cloud_cover,weather_code",
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
            "timezone": config.CITY_TIMEZONE
        }
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(config.OPENMETEO_FORECAST_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Extract current data
            current = data.get("current", {})
            if current:
                timestamp = current.get("time")
                weather_data = {
                    "timestamp": timestamp,
                    "temperature": current.get("temperature_2m"),
                    "humidity": current.get("relative_humidity_2m"),
                    "wind_speed": current.get("wind_speed_10m"),
                    "wind_direction": current.get("wind_direction_10m"),
                    "precipitation": current.get("precipitation"),
                    "pressure": current.get("surface_pressure"),
                    "cloud_cover": current.get("cloud_cover"),
                    "weather_code": current.get("weather_code")
                }
                
                database.upsert_dict("weather_data", weather_data, ["timestamp"])
                database.log_fetch("weather_forecast", "success", rows_inserted=1)
                
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        database.log_fetch("weather_forecast", "error", error_message=str(e))

async def fetch_weather_history():
    """Fetches past 30 days of daily historical weather from Open-Meteo."""
    try:
        from datetime import timedelta
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)
        
        params = {
            "latitude": config.CITY_LATITUDE,
            "longitude": config.CITY_LONGITUDE,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
            "hourly": "relative_humidity_2m,surface_pressure",
            "timezone": config.CITY_TIMEZONE
        }
        
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            response = await client.get(config.OPENMETEO_HISTORICAL_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            daily = data.get("daily", {})
            times = daily.get("time", [])
            
            hourly = data.get("hourly", {})
            hourly_hum = hourly.get("relative_humidity_2m", [])
            hourly_pres = hourly.get("surface_pressure", [])
            
            rows_inserted = 0
            for i in range(len(times)):
                # Average hourly data to get daily values
                start_idx = i * 24
                end_idx = start_idx + 24
                hum_slice = [h for h in hourly_hum[start_idx:end_idx] if h is not None] if hourly_hum else []
                pres_slice = [p for p in hourly_pres[start_idx:end_idx] if p is not None] if hourly_pres else []
                
                avg_hum = sum(hum_slice) / len(hum_slice) if hum_slice else None
                avg_pres = sum(pres_slice) / len(pres_slice) if pres_slice else None
                
                record = {
                    "timestamp": f"{times[i]}T00:00:00",
                    "temperature": daily.get("temperature_2m_mean", [])[i],
                    "humidity": avg_hum,
                    "wind_speed": daily.get("wind_speed_10m_max", [])[i],
                    "precipitation": daily.get("precipitation_sum", [])[i],
                    "pressure": avg_pres
                }
                if record["temperature"] is not None:
                    database.upsert_dict("weather_history", record, ["timestamp"])
                    rows_inserted += 1
                    
            database.log_fetch("weather_history", "success", rows_inserted=rows_inserted)
            
    except Exception as e:
        logger.error(f"Error fetching historical weather data: {e}")
        database.log_fetch("weather_history", "error", error_message=str(e))
