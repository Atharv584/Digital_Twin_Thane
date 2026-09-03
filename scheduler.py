import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

import config
from fetchers.weather_fetcher import fetch_weather, fetch_weather_history
from fetchers.air_quality_fetcher import fetch_air_quality_modeled, fetch_air_quality_stations, fetch_aqi_history
from fetchers.marine_fetcher import fetch_marine_data
from fetchers.flood_fetcher import fetch_flood_data
from fetchers.news_fetcher import fetch_news
from fetchers.demographics_fetcher import fetch_demographics
from fetchers.economic_fetcher import fetch_economic_indicators
from fetchers.poi_fetcher import fetch_poi
from fetchers.solar_fetcher import fetch_solar_data
from fetchers.earthquake_fetcher import fetch_earthquakes
from fetchers.exchange_rate_fetcher import fetch_exchange_rates

# We will import ML and LLM later when they are implemented
# from ml.predictor import retrain_model
# from llm.analyzer import generate_daily_report

logger = logging.getLogger(__name__)

async def run_all_fetchers():
    """Runs all fetchers (useful for initial data population)."""
    logger.info("Running all fetchers for initial data population...")
    
    # Run in parallel where possible, but group to avoid overwhelming the system
    await asyncio.gather(
        fetch_weather(),
        fetch_weather_history(),
        fetch_air_quality_modeled(),
        fetch_aqi_history(),
        fetch_marine_data(),
        fetch_flood_data(),
        fetch_solar_data(),
        fetch_earthquakes(),
        fetch_exchange_rates()
    )
    
    # Run these sequentially or with delays if needed (e.g. rate limits)
    await fetch_air_quality_stations()
    await fetch_news()
    await fetch_demographics()
    await fetch_economic_indicators()
    await fetch_poi()
    
    logger.info("Completed initial data fetch.")

def start_scheduler():
    """Starts the APScheduler with all configured jobs."""
    scheduler = AsyncIOScheduler()
    
    # ── Interval Jobs (hours) ──
    scheduler.add_job(fetch_weather, IntervalTrigger(hours=config.SCHEDULE["weather_forecast"]["hours"]))
    scheduler.add_job(fetch_air_quality_modeled, IntervalTrigger(hours=config.SCHEDULE["air_quality_modeled"]["hours"]))
    scheduler.add_job(fetch_air_quality_stations, IntervalTrigger(hours=config.SCHEDULE["air_quality_stations"]["hours"]))
    scheduler.add_job(fetch_marine_data, IntervalTrigger(hours=config.SCHEDULE["marine"]["hours"]))
    scheduler.add_job(fetch_flood_data, IntervalTrigger(hours=config.SCHEDULE["flood"]["hours"]))
    scheduler.add_job(fetch_news, IntervalTrigger(hours=config.SCHEDULE["news"]["hours"]))
    scheduler.add_job(fetch_earthquakes, IntervalTrigger(hours=config.SCHEDULE["earthquakes"]["hours"]))
    
    # ── Daily Cron Jobs ──
    # Run solar data right after midnight
    scheduler.add_job(fetch_solar_data, CronTrigger(hour=0, minute=5))
    # Run exchange rates after market open
    scheduler.add_job(fetch_exchange_rates, CronTrigger(hour=9, minute=0))
    
    # ── Weekly Jobs ──
    # Run on Monday at 1 AM
    scheduler.add_job(fetch_demographics, CronTrigger(day_of_week='mon', hour=1))
    scheduler.add_job(fetch_economic_indicators, CronTrigger(day_of_week='mon', hour=1, minute=30))
    scheduler.add_job(fetch_poi, CronTrigger(day_of_week='mon', hour=2))
    
    # ── AI/ML Jobs (Placeholder for now) ──
    # scheduler.add_job(retrain_model, CronTrigger(hour=2, minute=0))
    # scheduler.add_job(generate_daily_report, CronTrigger(hour=8, minute=0))

    scheduler.start()
    logger.info("Scheduler started successfully.")
    return scheduler

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # For testing the fetchers manually
    asyncio.run(run_all_fetchers())
