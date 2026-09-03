import os
import logging
from groq import Groq
import json
from datetime import datetime

import config
import database

logger = logging.getLogger(__name__)

def get_client():
    if not config.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY is not set. LLM features will be disabled.")
        return None
    return Groq(api_key=config.GROQ_API_KEY)

def get_latest_data_summary():
    """Aggregates latest data points from the DB into a prompt-friendly text."""
    summary = f"Current Data Summary for {config.CITY_NAME}, {config.CITY_COUNTRY}:\n"
    
    try:
        with database.get_connection() as conn:
            # Weather
            weather = conn.execute("SELECT * FROM weather_data ORDER BY timestamp DESC LIMIT 1").fetchone()
            if weather:
                summary += f"- Weather: Temp {weather['temperature']}°C, Humidity {weather['humidity']}%, Wind {weather['wind_speed']} km/h\n"
            
            # AQI
            aqi = conn.execute("SELECT * FROM air_quality_stations ORDER BY timestamp DESC LIMIT 1").fetchone()
            if aqi:
                summary += f"- Air Quality: AQI {aqi['aqi']} (Main pollutant: {aqi['dominant_pollutant']})\n"
                
            # Marine
            marine = conn.execute("SELECT * FROM marine_data ORDER BY timestamp DESC LIMIT 1").fetchone()
            if marine:
                summary += f"- Marine: Wave Height {marine['wave_height']}m\n"
                
            # Flood
            flood = conn.execute("SELECT * FROM flood_data ORDER BY timestamp DESC LIMIT 1").fetchone()
            if flood:
                summary += f"- River Discharge: {flood['river_discharge']} m³/s\n"
                
    except Exception as e:
        logger.error(f"Error fetching data for LLM summary: {e}")
        summary += "- Error fetching live data.\n"
        
    return summary

def generate_daily_report():
    """Uses Groq Llama to generate a daily insights report."""
    client = get_client()
    if not client:
        return "LLM integration disabled (no API key)."
        
    data_context = get_latest_data_summary()
    
    prompt = f"""
    You are an AI assistant for a digital twin of {config.CITY_NAME}. 
    Based on the following current telemetry, write a short, 2-3 paragraph executive summary 
    highlighting any risks (like bad air quality, high waves, or heat) and overall city conditions.
    
    {data_context}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful, data-driven smart city assistant."},
                {"role": "user", "content": prompt}
            ],
            model=config.GROQ_MODEL,
            temperature=config.GROQ_TEMPERATURE,
            max_tokens=config.GROQ_MAX_TOKENS,
        )
        
        response_text = chat_completion.choices[0].message.content
        
        # Log insight
        with database.get_connection() as conn:
            conn.execute("""
                INSERT INTO llm_insights (timestamp, insight_type, prompt_summary, response_text, tokens_used)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), "daily_report", "Generate daily report from current telemetry", response_text, chat_completion.usage.total_tokens if chat_completion.usage else 0))
            conn.commit()
            
        return response_text
        
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}")
        return f"Failed to generate report: {str(e)}"
        
def answer_question(question: str):
    """Answers a user question using RAG (injecting current state)."""
    client = get_client()
    if not client:
        return "LLM integration disabled (no API key)."
        
    data_context = get_latest_data_summary()
    
    prompt = f"""
    You are an AI assistant for the {config.CITY_NAME} digital twin.
    Use the following current data to answer the user's question. If the answer isn't in the data, just use your general knowledge but clarify it's not from the real-time sensors.
    
    {data_context}
    
    User Question: {question}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a concise, helpful smart city AI."},
                {"role": "user", "content": prompt}
            ],
            model=config.GROQ_MODEL,
            temperature=config.GROQ_TEMPERATURE,
            max_tokens=config.GROQ_MAX_TOKENS,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}")
        return f"Error processing question: {str(e)}"
