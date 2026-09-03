"""
Central configuration for the Thane Digital Twin.
All API endpoints, coordinates, schedule intervals, and paths are defined here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Project Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
STATIC_DIR = BASE_DIR / "static"

DATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "city_twin.db"

# ── Thane Coordinates ─────────────────────────────────────────────────────────
CITY_NAME = "Thane"
CITY_COUNTRY = "India"
CITY_LATITUDE = 19.1970
CITY_LONGITUDE = 72.9635
CITY_TIMEZONE = "Asia/Kolkata"

# Bounding box for POI queries (south, west, north, east)
CITY_BBOX = (19.12, 72.90, 19.30, 73.05)

# ── API Keys ───────────────────────────────────────────────────────────────────
WAQI_API_KEY = os.getenv("WAQI_API_KEY", "")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ── API Endpoints ──────────────────────────────────────────────────────────────
# 1. Open-Meteo Weather Forecast (no key)
OPENMETEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# 2. Open-Meteo Historical Weather (no key)
OPENMETEO_HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"

# 3. Open-Meteo Air Quality (no key)
OPENMETEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# 4. WAQI / AQICN (free key)
WAQI_FEED_URL = "https://api.waqi.info/feed"
WAQI_GEO_URL = "https://api.waqi.info/map/bounds"

# 5. Open-Meteo Marine (no key)
OPENMETEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

# 6. Open-Meteo Flood (no key)
OPENMETEO_FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"

# 7. GNews (free key)
GNEWS_URL = "https://gnews.io/api/v4/search"

# 8. REST Countries (no key)
REST_COUNTRIES_URL = "https://restcountries.com/v3.1/name"

# 9. World Bank (no key)
WORLD_BANK_URL = "https://api.worldbank.org/v2/country/IND/indicator"

# 10. Nominatim / OSM (no key, 1 req/sec)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# 11. Overpass API / OSM (no key)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# 12. Sunrise-Sunset (no key)
SUNRISE_SUNSET_URL = "https://api.sunrisesunset.io/json"

# 13. USGS Earthquake (no key)
USGS_EARTHQUAKE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# 14. Frankfurter Exchange Rates (no key)
FRANKFURTER_URL = "https://api.frankfurter.dev"

# 15. Nager.Date Public Holidays (no key)
NAGER_DATE_URL = "https://date.nager.at/api/v3/PublicHolidays"

# 16. Hipo Universities (no key)
HIPO_UNIV_URL = "http://universities.hipolabs.com/search"

# ── Scheduler Intervals ───────────────────────────────────────────────────────
# Format: (hours, minutes) — or "cron" dict for complex schedules
SCHEDULE = {
    "weather_forecast":     {"hours": 6},
    "air_quality_modeled":  {"hours": 3},
    "air_quality_stations": {"hours": 3},
    "marine":               {"hours": 6},
    "flood":                {"hours": 12},
    "news":                 {"hours": 12},
    "solar":                {"hours": 24},
    "earthquakes":          {"hours": 6},
    "exchange_rates":       {"hours": 24},
    "demographics":         {"days": 7},
    "economic":             {"days": 7},
    "poi":                  {"days": 7},
    "holidays":             {"days": 7},
    "universities":         {"days": 30},
    "ml_retrain":           {"hours": 24},
    "llm_report":           {"hours": 24},
}

# ── ML Configuration ──────────────────────────────────────────────────────────
HISTORICAL_BACKFILL_DAYS = 30
MIN_ROWS_FOR_TRAINING = 50
MODEL_FILE = MODELS_DIR / "city_twin_model.joblib"

# ── LLM Configuration ─────────────────────────────────────────────────────────
GROQ_MODEL = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
GROQ_MAX_TOKENS = 1024
GROQ_TEMPERATURE = 0.3

# ── World Bank Indicators ─────────────────────────────────────────────────────
WORLD_BANK_INDICATORS = {
    "SP.POP.TOTL": "Total Population",
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "SP.URB.TOTL.IN.ZS": "Urban Population (%)",
    "EN.ATM.CO2E.PC": "CO2 Emissions (metric tons per capita)",
    "SP.DYN.LE00.IN": "Life Expectancy at Birth",
    "SE.ADT.LITR.ZS": "Literacy Rate (%)",
}

# ── Overpass POI Categories ────────────────────────────────────────────────────
POI_CATEGORIES = {
    "hospital": {"tag": "amenity", "value": "hospital"},
    "school": {"tag": "amenity", "value": "school"},
    "park": {"tag": "leisure", "value": "park"},
    "transit_station": {"tag": "public_transport", "value": "station"},
    "fire_station": {"tag": "amenity", "value": "fire_station"},
    "police": {"tag": "amenity", "value": "police"},
    "university": {"tag": "amenity", "value": "university"},
    "place_of_worship": {"tag": "amenity", "value": "place_of_worship"},
}

# ── HTTP Client Config ─────────────────────────────────────────────────────────
HTTP_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
USER_AGENT = "ThaneDigitalTwin/1.0 (prototype; contact@example.com)"
