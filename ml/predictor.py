import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import joblib
import logging
from datetime import datetime
import json
import sqlite3
import os

import config
import database

logger = logging.getLogger(__name__)

def get_training_data():
    """Extracts and merges data from sqlite for training."""
    try:
        with database.get_connection() as conn:
            # We use pandas to read directly from sqlite
            weather_df = pd.read_sql_query("SELECT timestamp, temperature, humidity, wind_speed FROM weather_data", conn)
            aq_df = pd.read_sql_query("SELECT timestamp, aqi, pm25 FROM air_quality_stations", conn)
            
            if weather_df.empty or aq_df.empty:
                logger.warning("Not enough data to train model.")
                return None
                
            # Convert timestamps
            weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp'])
            aq_df['timestamp'] = pd.to_datetime(aq_df['timestamp'])
            
            # Merge on closest timestamp (or exact if rounded)
            # For simplicity, we round to nearest hour and merge
            weather_df['hour'] = weather_df['timestamp'].dt.floor('h')
            aq_df['hour'] = aq_df['timestamp'].dt.floor('h')
            
            # Aggregate to hourly to resolve duplicates
            weather_hourly = weather_df.groupby('hour').mean(numeric_only=True).reset_index()
            aq_hourly = aq_df.groupby('hour').mean(numeric_only=True).reset_index()
            
            merged_df = pd.merge(weather_hourly, aq_hourly, on='hour', how='inner')
            
            # Feature engineering
            merged_df['hour_of_day'] = merged_df['hour'].dt.hour
            merged_df['day_of_week'] = merged_df['hour'].dt.dayofweek
            merged_df['month'] = merged_df['hour'].dt.month
            
            # Drop NaNs
            merged_df = merged_df.dropna()
            return merged_df
            
    except Exception as e:
        logger.error(f"Error getting training data: {e}")
        return None

def train_model():
    """Trains a Random Forest model to predict AQI from weather data."""
    df = get_training_data()
    
    if df is None or len(df) < config.MIN_ROWS_FOR_TRAINING:
        logger.info(f"Skipping training, need at least {config.MIN_ROWS_FOR_TRAINING} rows of merged data.")
        return False
        
    try:
        # Features: temp, humidity, wind_speed, hour, day, month
        X = df[['temperature', 'humidity', 'wind_speed', 'hour_of_day', 'day_of_week', 'month']]
        # Target: AQI
        y = df['aqi']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        
        score = model.score(X_test, y_test)
        logger.info(f"Model trained successfully. R^2 Score: {score:.2f}")
        
        # Save model
        joblib.dump(model, config.MODEL_FILE)
        return True
        
    except Exception as e:
        logger.error(f"Error training model: {e}")
        return False

def predict_aqi(temperature, humidity, wind_speed, timestamp=None):
    """Predicts AQI given weather conditions."""
    if not os.path.exists(config.MODEL_FILE):
        logger.warning("Model file not found. Cannot predict.")
        return None
        
    try:
        model = joblib.load(config.MODEL_FILE)
        
        if timestamp is None:
            dt = datetime.now()
        else:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp)
            else:
                dt = timestamp
                
        hour_of_day = dt.hour
        day_of_week = dt.weekday()
        month = dt.month
        
        # Create input array matching training features
        features = np.array([[temperature, humidity, wind_speed, hour_of_day, day_of_week, month]])
        
        prediction = model.predict(features)[0]
        
        # Log prediction
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "model_version": "rf_v1",
            "prediction_type": "aqi",
            "input_features_json": json.dumps({"temp": temperature, "hum": humidity, "wind": wind_speed}),
            "predicted_values_json": json.dumps({"aqi": float(prediction)}),
            "confidence": None # Could be estimated from tree variance
        }
        database.upsert_dict("predictions", record, ["id"]) # Needs auto-increment handling or unique id
        # Better to just insert for predictions table since it has auto-increment PK
        with database.get_connection() as conn:
            conn.execute("""
                INSERT INTO predictions (timestamp, model_version, prediction_type, input_features_json, predicted_values_json)
                VALUES (?, ?, ?, ?, ?)
            """, (record["timestamp"], record["model_version"], record["prediction_type"], record["input_features_json"], record["predicted_values_json"]))
            conn.commit()
            
        return float(prediction)
        
    except Exception as e:
        logger.error(f"Error making prediction: {e}")
        return None

def retrain_model():
    """Job to periodically retrain the model."""
    logger.info("Starting scheduled model retraining...")
    train_model()
