"""
SIH'26 Thermal Anomaly Risk API — FastAPI service that fronts the
DBSCAN/OSM-join pipeline's `processed_data` table with the ANN classifier
and deterministic risk engine in fire_engine.py, and serves it to the
PYRON frontend.
"""

import os
import json
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path

from pydantic import BaseModel
from datetime import datetime

import gdown
import zipfile

from datetime import datetime, timezone

import subprocess
import sys
from apscheduler.schedulers.background import BackgroundScheduler

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text

from fire_engine import FireAnalysisEngine

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ARTIFACTS_DIR = Path(__file__).resolve().parent
load_dotenv(ARTIFACTS_DIR / ".env", override=True)

DB_TABLE = os.getenv("DB_TABLE", "processed_data")

FIREBASE_LIVE_SENSOR_URL = os.getenv(
    "FIREBASE_LIVE_SENSOR_URL",
    "https://farmiq-c8afe-default-rtdb.asia-southeast1.firebasedatabase.app/Greenhouse/Live.json",
)

CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")]

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "sih26_db")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    _encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
    DATABASE_URL = f"postgresql://{DB_USER}:{_encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

db_engine = create_engine(DATABASE_URL)

fire_engine: FireAnalysisEngine | None = None
fire_engine_error: str | None = None

# YAHAN SE NAYA CODE START HAI
def trigger_automated_pipeline():
    print("\n[AUTOMATION] Triggering live NASA data pipeline...")
    pipeline_dir = ARTIFACTS_DIR.parent / "pipeline"
    try:
        result = subprocess.run(
            [sys.executable, "run_pipeline.py"],
            cwd=str(pipeline_dir),
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("[AUTOMATION] Pipeline completed & Database updated successfully!")
        else:
            print(f"[AUTOMATION] Pipeline Error:\n{result.stderr}")
    except Exception as e:
        print(f"[AUTOMATION] Failed to trigger pipeline: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global fire_engine, fire_engine_error
    
    # 🚀 PATH FIX: '..' ka matlab ek folder piche (root) check karo
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(base_dir, "data")
    zip_path = os.path.join(base_dir, "heavy_data.zip")
    worldcover_path = os.path.join(data_dir, "worldcover")
    
    if not os.path.exists(worldcover_path):
        print("Starting heavy data download from Google Drive...")
        os.makedirs(data_dir, exist_ok=True)
        
        file_id = "1oT6dTaHtQ099w1VZzGsTUcRBTcEnFfts" # Teri file ID
        gdown.download(id=file_id, output=zip_path, quiet=False)
        
        print("Extracting files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(base_dir) # Root mein extract karega
            
        if os.path.exists(zip_path):
            os.remove(zip_path)
        print("Data is ready for the ML pipeline!")
    else:
        print("✅ Heavy data found locally. Skipping download.")
        
    # 🚀 PURANA CODE YAHAN SE CONTINUE...
    try:
        fire_engine = FireAnalysisEngine(artifacts_dir=str(ARTIFACTS_DIR))
        print("AI models loaded successfully.")
    except Exception as e:
        fire_engine_error = str(e)
        print(f"Model load error: {fire_engine_error}")
        
    scheduler = BackgroundScheduler()
    # Abhi testing ke liye 2 minutes rakha hai, baad mein hours=3 kar dena
    scheduler.add_job(trigger_automated_pipeline, 'interval', hours=3)
    scheduler.start()
    print("Background automation scheduler started (Interval: 3 hours).")
    
    yield
    
    scheduler.shutdown()
    print("Scheduler shut down.")
# YAHAN NAYA CODE KHATAM HAI

app = FastAPI(title="SIH'26 Thermal Anomaly Risk API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def require_fire_engine() -> FireAnalysisEngine:
    if fire_engine is None:
        raise HTTPException(
            status_code=503,
            detail=f"AI models are not loaded: {fire_engine_error or 'unknown error'}",
        )
    return fire_engine

def load_clusters() -> pd.DataFrame:
    try:
        return pd.read_sql(text(f"SELECT * FROM {DB_TABLE}"), db_engine)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database query failed: {e}") from e

def analyze_clusters(df: pd.DataFrame, engine: FireAnalysisEngine) -> list[dict]:
    raw_rows = df.to_dict(orient="records")
    try:
        analyses = engine.analyze_batch(raw_rows)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Model inference failed: {e}") from e

    results = []
    for raw, analysis in zip(raw_rows, analyses):
        results.append(
            {
                "cluster_id": raw.get("cluster_id"),
                "centroid_lat": raw.get("centroid_lat"),
                "centroid_lon": raw.get("centroid_lon"),
                "ai_prediction": analysis["fire_type"],
                "confidence": analysis["probability"],
                "persistence_score": raw.get("persistence_score"),
                "nearby_industry_mw": raw.get("nearby_industrial_capacity_mw"),
                "risk_level": analysis["risk_level"],
                "risk_score": analysis["risk_score"],
                "risk_reason": analysis["risk_reason"],
                "max_frp": raw.get("max_frp"),
                "max_brightness": raw.get("max_brightness"),
                "nearest_industrial_distance_km": raw.get("nearest_industrial_distance_km"),
                "spatial_spread_km": raw.get("spatial_spread_km"),
                "detection_count": raw.get("detection_count"),
            }
        )
    return results

def cluster_to_feature(c: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(c["centroid_lon"]), float(c["centroid_lat"])],
        },
        "properties": {k: v for k, v in c.items() if k not in ("centroid_lat", "centroid_lon")},
    }

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# Updated ESP32 Sensor Data Model (Jisme saare parameters hain)
class SensorData(BaseModel):
    device_id: str
    lat: float
    lon: float
    temperature: float
    humidity: float
    wind_speed: float        # Simulated by Slide Potentiometer
    wind_direction: str      # Simulated/Hardcoded Array
    smoke_ppm: float         # Simulated by Rotary Potentiometer
    flame_detected: bool     # Simulated by Slide Switch
    pm25: float              # Code logic generated
    pm10: float              # Code logic generated
    pressure: float          # Baseline simulated (~1013 hPa)
    rainfall: float          # Logic/Random generated
    timestamp: str           # NTP Timestamp

LATEST_ESP_DATA = {}

@app.post("/api/esp-data")
async def receive_esp_data(data: dict): # Pydantic model hai toh wo use kar
    global latest_esp_data
    latest_esp_data = data  # Wokwi ka live payload save ho gaya
    print(f"[🔥 FULL ESP32 NODE] Alert from {data.get('device_id')} (Sambalpur)!")
    return {"status": "success", "message": "Data received"}

@app.post("/api/esp-data")
async def receive_esp_data(data: SensorData):
    print(f"\n[🔥 FULL ESP32 NODE] Alert from {data.device_id} (Sambalpur)!")
    print(f"🌡️ Temp: {data.temperature}°C | 💧 Hum: {data.humidity}% | 💨 Wind: {data.wind_speed} m/s ({data.wind_direction})")
    print(f"🚬 Smoke: {data.smoke_ppm} ppm | 🌫️ PM2.5: {data.pm25} | 🌫️ PM10: {data.pm10}")
    print(f"🔥 Flame: {data.flame_detected} | 🧭 Press: {data.pressure} hPa | 🌧️ Rain: {data.rainfall} mm")
    
    LATEST_ESP_DATA[data.device_id] = data.dict()
    return {"status": "success", "message": "Full ground data logged successfully"}

@app.get("/api/esp-data")
async def get_esp_data():
    return LATEST_ESP_DATA

@app.get("/")
def read_root():
    return {"message": "Welcome to SIH'26 Backend Engine!"}

@app.get("/health")
def health():
    db_ok = True
    db_error = None
    try:
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = str(e)

    return {
        "models_loaded": fire_engine is not None,
        "model_error": fire_engine_error,
        "database_reachable": db_ok,
        "database_error": db_error,
        "database": "Supabase PostgreSQL",  # Yahan DB_NAME hata kar safe string daal di
        "table": DB_TABLE,
    }

@app.get("/api/thermal-map")
def get_thermal_map():
    engine = require_fire_engine()
    df = load_clusters()
    
    features = []
    if not df.empty:
        clusters = analyze_clusters(df, engine)
        features = [cluster_to_feature(c) for c in clusters]

    # Wokwi ke live data ko standard esp32 keys me map karo
    esp_payload = latest_esp_data if latest_esp_data else {}
    
    # Smoke level ko low/medium/high mein convert karo (TypeScript ke hisaab se)
    pm25_val = esp_payload.get("pm25", 0.0)
    smoke_str = "low" if pm25_val < 30 else ("medium" if pm25_val < 70 else "high")

    # Current time filter bypass karne ke liye (Blue dot hamesha dikhega)
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Base mock data jo tumne manga hai (Fallback)
    base_esp_data = {
            "temperature": -40.0,
            "humidity": 77.5,
            "pm25": 0,
            "wind_speed": 0.0,
            "pressure": 1015,
            "flame_detected": False
    }
        
    # 2. Agar Wokwi se live data aaya hai, toh mock values update (override) ho jayengi
    esp_payload = base_esp_data.copy()
    if latest_esp_data:
        esp_payload.update(latest_esp_data)

    # 🔥 Wokwi ke fake time ko Real Server Time se overwrite karo (HH:MM:SS)
    esp_payload["timestamp"] = datetime.now().strftime("%H:%M:%S")
            
    pm25_val = esp_payload.get("pm25", 0)
    smoke_str = "low" if pm25_val < 30 else ("medium" if pm25_val < 70 else "high")

    dummy_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [83.9777, 21.4669]
        },
        "properties": {
            "cluster_id": "NODE_SMB_01",
            "risk_score": 82,
            "risk_level": "critical",
            "classification": "wildfire",
            "ai_prediction": "wildfire",
            "is_ground_node": True,
            "persistence_score": 92,
            "duration_hours": 24,
            "timestamp": current_time,
            "first_detected": current_time,
            "last_detected": current_time,
                
            # Default format
            "esp32": {
                "temperature_c": esp_payload.get("temperature"),
                "humidity_pct": esp_payload.get("humidity"),
                "smoke_level": smoke_str
            },
            # Detailed 6-tiles UI ke liye payload
            "esp_live_data": esp_payload
        }
    }
    
    features.append(dummy_feature)
    return {"type": "FeatureCollection", "features": features}

@app.get("/api/live-sensors")
def get_live_sensor_data():
    try:
        response = requests.get(FIREBASE_LIVE_SENSOR_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Firebase request failed: {e}") from e

    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Unexpected Firebase response shape")

    temp = data.get("temperature")
    co2 = data.get("co2Level")
    fire_alert = None
    if temp is not None or co2 is not None:
        fire_alert = "DANGER: HIGH PROBABILITY OF FIRE" if (
            (temp is not None and temp > 45.0) or (co2 is not None and co2 > 1500)
        ) else "SAFE"

    return {
        "status": "success",
        "source": "Wokwi ESP32 via Firebase",
        "sensor_readings": data,
        "on_ground_fire_alert": fire_alert,
    }

RISK_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
ALERT_SEVERITY_FLOOR = "high"

# File ke top par latest_esp_data global variable zaroor define kar lena
latest_esp_data = None

@app.post("/api/esp-data")
async def receive_esp_data(data: dict):
    global latest_esp_data
    latest_esp_data = data
    print(f"[🔥 FULL ESP32 NODE] Alert from {data.get('device_id')} (Sambalpur)!")
    return {"status": "success"}

@app.get("/api/alerts")
def get_alerts():
    engine = require_fire_engine()
    df = load_clusters()
    
    alerts = []
    
    # NASA FIRMS data processing (agar available hai)
    if not df.empty:
        clusters = analyze_clusters(df, engine)
        floor = RISK_ORDER[ALERT_SEVERITY_FLOOR]
        for c in clusters:
            level = c["risk_level"].lower()
            if RISK_ORDER.get(level, 0) < floor:
                continue

            reasons = c.get("risk_reason") or []
            cluster_id = c["cluster_id"]
            lat, lon = c["centroid_lat"], c["centroid_lon"]

            alerts.append(
                {
                    "alert_id": f"SOS-{cluster_id}",
                    "severity": level,
                    "location": f"{lat:.4f}, {lon:.4f}",
                    "timestamp": None,
                    "cluster_id": str(cluster_id),
                    "reason": "; ".join(reasons) if reasons else f"{c['ai_prediction']} anomaly, risk score {c['risk_score']}/100",
                    "status": "active",
                    "automated_assessment": (
                        f"Classified as {c['ai_prediction']} ({c['confidence']:.1f}% model confidence). "
                        f"Risk score {c['risk_score']}/100 ({c['risk_level']})."
                    ),
                    "recommended_actions": None,
                    "assigned_team": None,
                    "assigned_team_status": None,
                    "log_timeline": [],
                    "is_ground_node": False  # Flag for frontend map
                }
            )

    # ... (tera upar ka NASA FIRMS wala existing loop)

    # --- IS PURAY BLOCK KO REPLACE KAR DE ---
    dummy_cluster = {
        "alert_id": "SOS-NODE_SMB_01",
        "cluster_id": "NODE_SMB_01",
        "centroid": {
            "lat": 21.4669, 
            "lon": 83.9777
        },
        "risk_level": "critical",
        "classification": "fire",  # Frontend useMemo filter ko bypass karne ke liye
        "ai_prediction": "Ground Validation",
        "location": "21.4669, 83.9777",
        "reason": "Live ESP32 Ground Validation Node",
        "status": "active",
        "automated_assessment": "Real-time hardware telemetry streaming directly from Sambalpur Wokwi simulation.",
        "recommended_actions": None,
        "assigned_team": "Team DEXTERS",
        "assigned_team_status": "Monitoring",
        "log_timeline": [],
        "is_ground_node": True,
        "esp_live_data": latest_esp_data if latest_esp_data else {"status": "Waiting for connection"}
    }
    
    alerts.append(dummy_cluster)
    return alerts

@app.get("/api/alerts/notifications")
def get_alert_notifications():
    alerts = get_alerts()
    active = [a for a in alerts if a["status"] == "active"]
    return {"hasUnread": len(active) > 0, "unreadCount": len(active)}