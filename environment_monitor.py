# MargRaksha V2 - environment_monitor.py
import time
import threading
from datetime import datetime
from config import (AQI_CRITICAL, TEMP_HEAT_ADVISORY,
                    HUMIDITY_FOG_THRESHOLD, LAMP_ID)
from event_logger import log_event, log_telemetry
from uart_parser import get_latest, set_led

_firebase_db = None

def init(firebase_db):
    global _firebase_db
    _firebase_db = firebase_db

def get_env():
    return get_latest().get("env", {})

def get_gps():
    return get_latest().get("gps", {})

def check_conditions():
    from alert_engine import trigger_aqi
    env = get_env()
    if not env:
        return
    temp = env.get("temp", 0)
    hum  = env.get("hum",  0)
    rain = env.get("rain", 0)
    aqi  = env.get("aqi",  0)
    ldr  = env.get("ldr",  2048)
    if rain:
        set_led(color="blue", brightness=200)
        log_event("ENV", "Rain detected - LED blue")
    elif hum > HUMIDITY_FOG_THRESHOLD and ldr < 100:
        set_led(color="amber", brightness=255)
        log_event("ENV", "Fog mode - hum:" + str(hum))
    if temp > TEMP_HEAT_ADVISORY:
        log_event("ENV", "Heat advisory - temp:" + str(temp), "WARNING")
    if aqi > AQI_CRITICAL:
        log_event("ENV", "AQI critical: " + str(aqi), "WARNING")
        trigger_aqi(aqi, get_gps())

def telemetry_loop():
    while True:
        try:
            env = get_env()
            if env and _firebase_db:
                log_telemetry(_firebase_db, LAMP_ID, {
                    **env,
                    "time": datetime.now().isoformat()
                })
        except Exception as e:
            log_event("ENV", "Telemetry error: " + str(e), "ERROR")
        time.sleep(60)

def start(firebase_db):
    init(firebase_db)
    t = threading.Thread(target=telemetry_loop, daemon=True)
    t.start()
    log_event("ENV", "Environment monitor started")
    return t
