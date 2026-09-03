"""
SQLite database layer for the Thane Digital Twin.
Handles schema creation and provides helper functions for inserting and querying data.
"""

import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import config

logger = logging.getLogger(__name__)

def get_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database schema."""
    logger.info(f"Initializing database at {config.DB_PATH}")
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Weather Data (Forecast/Current)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_data (
                timestamp TEXT PRIMARY KEY,
                temperature REAL,
                humidity REAL,
                wind_speed REAL,
                wind_direction REAL,
                precipitation REAL,
                pressure REAL,
                cloud_cover REAL,
                weather_code INTEGER
            )
        """)
        
        # 2. Weather History (Archive)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_history (
                timestamp TEXT PRIMARY KEY,
                temperature REAL,
                humidity REAL,
                wind_speed REAL,
                precipitation REAL,
                pressure REAL
            )
        """)
        
        # 3. Air Quality (Modeled from Open-Meteo)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS air_quality_modeled (
                timestamp TEXT PRIMARY KEY,
                pm25 REAL,
                pm10 REAL,
                co REAL,
                no2 REAL,
                so2 REAL,
                o3 REAL,
                dust REAL,
                uv_index REAL,
                aqi_europe REAL
            )
        """)
        
        # 4. Air Quality (Physical Stations from WAQI)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS air_quality_stations (
                timestamp TEXT,
                station_name TEXT,
                aqi REAL,
                pm25 REAL,
                pm10 REAL,
                o3 REAL,
                no2 REAL,
                so2 REAL,
                co REAL,
                dominant_pollutant TEXT,
                PRIMARY KEY (timestamp, station_name)
            )
        """)
        
        # 5. Marine Data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS marine_data (
                timestamp TEXT PRIMARY KEY,
                wave_height REAL,
                wave_direction REAL,
                wave_period REAL,
                sea_surface_temp REAL,
                ocean_current_velocity REAL
            )
        """)
        
        # 6. Flood Risk Data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flood_data (
                timestamp TEXT PRIMARY KEY,
                river_discharge REAL,
                river_discharge_mean REAL,
                river_discharge_max REAL
            )
        """)
        
        # 7. News Data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_data (
                url TEXT PRIMARY KEY,
                timestamp TEXT,
                title TEXT,
                description TEXT,
                source_name TEXT,
                image_url TEXT,
                published_at TEXT
            )
        """)
        
        # 8. Demographics Data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS demographics_data (
                fetched_at TEXT PRIMARY KEY,
                population INTEGER,
                area_km2 REAL,
                capital TEXT,
                region TEXT,
                subregion TEXT,
                languages_json TEXT,
                currencies_json TEXT,
                timezones_json TEXT,
                borders_json TEXT
            )
        """)
        
        # 9. Economic Indicators (World Bank)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS economic_indicators (
                indicator_code TEXT,
                year INTEGER,
                indicator_name TEXT,
                value REAL,
                country_code TEXT,
                PRIMARY KEY (indicator_code, year)
            )
        """)
        
        # 10. Points of Interest (Overpass/Nominatim)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS poi_data (
                osm_id INTEGER PRIMARY KEY,
                name TEXT,
                category TEXT,
                subcategory TEXT,
                latitude REAL,
                longitude REAL,
                address TEXT,
                tags_json TEXT
            )
        """)
        
        # 11. Solar & Daylight
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS solar_data (
                date TEXT PRIMARY KEY,
                sunrise TEXT,
                sunset TEXT,
                dawn TEXT,
                dusk TEXT,
                day_length TEXT,
                solar_noon TEXT,
                timezone TEXT
            )
        """)
        
        # 12. Seismic Activity (USGS)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS earthquake_data (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT,
                magnitude REAL,
                depth_km REAL,
                latitude REAL,
                longitude REAL,
                place TEXT,
                distance_from_city_km REAL
            )
        """)
        
        # 13. Currency Exchange Rates (Frankfurter)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rates (
                date TEXT,
                base_currency TEXT,
                target_currency TEXT,
                rate REAL,
                PRIMARY KEY (date, target_currency)
            )
        """)
        
        # 14. ML Predictions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                model_version TEXT,
                prediction_type TEXT,
                input_features_json TEXT,
                predicted_values_json TEXT,
                confidence REAL
            )
        """)
        
        # 15. LLM Insights
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                insight_type TEXT,
                prompt_summary TEXT,
                response_text TEXT,
                tokens_used INTEGER
            )
        """)
        
        # 16. Fetch Log (System Health)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fetch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                source TEXT,
                status TEXT,
                rows_inserted INTEGER,
                error_message TEXT,
                duration_ms INTEGER
            )
        """)
        
        # 17. System Config
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
        
        conn.commit()
    logger.info("Database initialization complete.")

def log_fetch(source: str, status: str, rows_inserted: int = 0, error_message: str = "", duration_ms: int = 0):
    """Log an API fetch operation."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO fetch_log (timestamp, source, status, rows_inserted, error_message, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), source, status, rows_inserted, error_message, duration_ms))
        conn.commit()

# --- Example Helper for generic inserts ---
def upsert_dict(table_name: str, data: Dict[str, Any], conflict_cols: List[str]):
    """
    Helper to do an INSERT OR REPLACE INTO (sqlite upsert) using a dictionary.
    """
    if not data:
        return
        
    cols = list(data.keys())
    vals = list(data.values())
    placeholders = ",".join(["?"] * len(cols))
    col_names = ",".join(cols)
    
    # Simple replace for sqlite
    query = f"INSERT OR REPLACE INTO {table_name} ({col_names}) VALUES ({placeholders})"
    
    with get_connection() as conn:
        conn.execute(query, vals)
        conn.commit()

if __name__ == "__main__":
    # Configure basic logging if run directly
    logging.basicConfig(level=logging.INFO)
    init_db()
