import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import sqlite3
import pandas as pd

import config
import database
from scheduler import start_scheduler, run_all_fetchers
from ml.predictor import predict_aqi
from llm.analyzer import generate_daily_report, answer_question

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Ensure DB is initialized
database.init_db()

# Keep track of scheduler
app_scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the scheduler
    global app_scheduler
    logger.info("Starting Thane Digital Twin Application...")
    app_scheduler = start_scheduler()
    
    # Optionally, we could trigger an initial background fetch if DB is empty
    # For now, let's just let the scheduler do its job or allow manual trigger via API
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    if app_scheduler:
        app_scheduler.shutdown()

app = FastAPI(title="Thane Digital Twin API", lifespan=lifespan)

# Mount static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(config.STATIC_DIR))

def query_db(query: str, args=(), one=False):
    """Helper to query the DB and return dicts."""
    with database.get_connection() as conn:
        cur = conn.execute(query, args)
        rv = [dict((cur.description[i][0], value) \
               for i, value in enumerate(row)) for row in cur.fetchall()]
        return (rv[0] if rv else None) if one else rv

# ── Frontend Route ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serves the main dashboard UI."""
    return templates.TemplateResponse("index.html", {"request": request, "city": config.CITY_NAME})

# ── REST API Endpoints ────────────────────────────────────────────────────────

@app.get("/api/weather/current")
async def get_current_weather():
    row = query_db("SELECT * FROM weather_data ORDER BY timestamp DESC LIMIT 1", one=True)
    return row or {"status": "no data yet"}

@app.get("/api/weather/history")
async def get_weather_history(days: int = 7):
    rows = query_db("SELECT * FROM weather_history ORDER BY timestamp DESC LIMIT ?", (days,))
    return rows

@app.get("/api/dashboard")
async def get_dashboard():
    """Unified dashboard endpoint — all current city telemetry in one shot."""
    weather    = query_db("SELECT * FROM weather_data ORDER BY timestamp DESC LIMIT 1", one=True)
    aqi_model  = query_db("SELECT * FROM air_quality_modeled ORDER BY timestamp DESC LIMIT 1", one=True)
    aqi_sta    = query_db("SELECT * FROM air_quality_stations ORDER BY timestamp DESC LIMIT 1", one=True)
    marine     = query_db("SELECT * FROM marine_data ORDER BY timestamp DESC LIMIT 1", one=True)
    flood      = query_db("SELECT * FROM flood_data ORDER BY timestamp DESC LIMIT 1", one=True)
    solar      = query_db("SELECT * FROM solar_data ORDER BY date DESC LIMIT 1", one=True)
    demo       = query_db("SELECT * FROM demographics_data ORDER BY fetched_at DESC LIMIT 1", one=True)
    gdp        = query_db(
        "SELECT value, year FROM economic_indicators WHERE indicator_code='NY.GDP.MKTP.CD' ORDER BY year DESC LIMIT 1",
        one=True
    )
    usd_inr    = query_db(
        "SELECT rate FROM exchange_rates WHERE target_currency='INR' ORDER BY date DESC LIMIT 1",
        one=True
    )

    # Best available AQI — prefer station, fallback to modeled
    aqi_value = None
    dominant  = None
    pm25      = None
    pm10      = None
    if aqi_sta:
        aqi_value = aqi_sta.get("aqi")
        dominant  = aqi_sta.get("dominant_pollutant")
        pm25      = aqi_sta.get("pm25")
        pm10      = aqi_sta.get("pm10")
    elif aqi_model:
        aqi_value = aqi_model.get("aqi_europe")
        pm25      = aqi_model.get("pm25")
        pm10      = aqi_model.get("pm10")

    return {
        "weather": weather,
        "aqi": {
            "value":     aqi_value,
            "dominant":  dominant,
            "pm25":      pm25,
            "pm10":      pm10,
            "no2":       (aqi_sta or aqi_model or {}).get("no2"),
            "o3":        (aqi_sta or aqi_model or {}).get("o3"),
            "so2":       (aqi_sta or aqi_model or {}).get("so2"),
            "uv_index":  (aqi_model or {}).get("uv_index"),
        },
        "marine":    marine,
        "flood":     flood,
        "solar":     solar,
        "demographics": {
            "population": (demo or {}).get("population"),
            "area_km2":   (demo or {}).get("area_km2"),
            "capital":    (demo or {}).get("capital"),
            "region":     (demo or {}).get("region"),
        },
        "economic": {
            "gdp_usd": (gdp or {}).get("value"),
            "gdp_year": (gdp or {}).get("year"),
        },
        "exchange": {
            "usd_inr": (usd_inr or {}).get("rate"),
        },
    }


@app.get("/api/historical-table")
async def get_historical_table(days: int = 30):
    """Joins weather_history and air_quality_modeled for a tabular view."""
    query = """
    SELECT 
        date(w.timestamp) as date,
        ROUND(w.temperature, 1) as avg_temp,
        w.humidity,
        w.wind_speed,
        w.precipitation,
        w.pressure,
        ROUND(a.aqi_europe, 1) as aqi,
        ROUND(a.pm25, 1) as pm25,
        ROUND(a.pm10, 1) as pm10,
        ROUND(a.co, 1) as co,
        ROUND(a.no2, 1) as no2,
        ROUND(a.so2, 1) as so2,
        ROUND(a.o3, 1) as o3,
        ROUND(a.dust, 1) as dust,
        ROUND(a.uv_index, 1) as uv_index
    FROM weather_history w
    LEFT JOIN air_quality_modeled a 
        ON date(w.timestamp) = date(a.timestamp)
    ORDER BY w.timestamp DESC
    LIMIT ?
    """
    rows = query_db(query, (days,))
    return rows

@app.get("/api/air-quality/current")
async def get_current_aqi():
    # Return both modeled and station data
    modeled = query_db("SELECT * FROM air_quality_modeled ORDER BY timestamp DESC LIMIT 1", one=True)
    stations = query_db("SELECT * FROM air_quality_stations ORDER BY timestamp DESC LIMIT 5")
    return {"modeled": modeled, "stations": stations}

@app.get("/api/marine/current")
async def get_marine_current():
    row = query_db("SELECT * FROM marine_data ORDER BY timestamp DESC LIMIT 1", one=True)
    return row or {"status": "no data yet"}
    
@app.get("/api/flood/current")
async def get_flood_current():
    row = query_db("SELECT * FROM flood_data ORDER BY timestamp DESC LIMIT 1", one=True)
    return row or {"status": "no data yet"}

@app.get("/api/news/latest")
async def get_latest_news():
    rows = query_db("SELECT * FROM news_data ORDER BY published_at DESC LIMIT 10")
    return rows

@app.get("/api/demographics")
async def get_demographics():
    row = query_db("SELECT * FROM demographics_data ORDER BY fetched_at DESC LIMIT 1", one=True)
    return row or {"status": "no data yet"}
    
@app.get("/api/economic")
async def get_economic(indicator: str = "NY.GDP.MKTP.CD"):
    rows = query_db("SELECT * FROM economic_indicators WHERE indicator_code = ? ORDER BY year DESC LIMIT 10", (indicator,))
    return rows

@app.get("/api/poi")
async def get_poi(category: str = None):
    if category:
        rows = query_db("SELECT * FROM poi_data WHERE category = ? LIMIT 100", (category,))
    else:
        rows = query_db("SELECT * FROM poi_data LIMIT 500")
    return rows
    
@app.get("/api/solar/today")
async def get_solar():
    row = query_db("SELECT * FROM solar_data ORDER BY date DESC LIMIT 1", one=True)
    return row or {"status": "no data yet"}
    
@app.get("/api/earthquakes")
async def get_earthquakes(days: int = 30):
    rows = query_db("SELECT * FROM earthquake_data ORDER BY timestamp DESC LIMIT 50")
    return rows
    
@app.get("/api/exchange-rates")
async def get_exchange_rates():
    rows = query_db("SELECT * FROM exchange_rates ORDER BY date DESC LIMIT 10")
    return rows

@app.get("/api/predict")
async def get_prediction(temp: float = 30.0, hum: float = 70.0, wind: float = 15.0):
    """Predicts AQI based on provided weather conditions."""
    aqi = predict_aqi(temp, hum, wind)
    if aqi is None:
        return {"status": "model not ready or error", "predicted_aqi": None}
    return {"predicted_aqi": aqi, "inputs": {"temp": temp, "humidity": hum, "wind_speed": wind}}

@app.post("/api/analyze")
async def analyze_data(query: str = None):
    """Generates LLM insights or answers a question."""
    if query:
        result = answer_question(query)
    else:
        result = generate_daily_report()
    return {"result": result}

@app.get("/api/status")
async def get_status():
    """Returns system health, DB row counts, and recent fetch logs."""
    stats = {}
    with database.get_connection() as conn:
        tables = ["weather_data", "air_quality_modeled", "air_quality_stations", "marine_data", "flood_data", 
                  "news_data", "poi_data", "earthquake_data", "solar_data"]
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count
            
    recent_logs = query_db("SELECT * FROM fetch_log ORDER BY timestamp DESC LIMIT 10")
    
    return {
        "status": "online",
        "city": config.CITY_NAME,
        "database_stats": stats,
        "recent_fetches": recent_logs
    }

@app.post("/api/fetch/trigger")
async def trigger_fetch(background_tasks: BackgroundTasks):
    """Manually trigger all fetchers to run in the background."""
    background_tasks.add_task(run_all_fetchers)
    return {"status": "fetch_started", "message": "All fetchers triggered in background."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
