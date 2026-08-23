# MargRaksha V2 - traffic_monitor.py
import time
import threading
from datetime import datetime
from config import SPEED_LIMIT_KMPH, LAMP_ID
from event_logger import log_event
from uart_parser import get_latest, trigger_buzzer

_firebase_db   = None
_speed_history = []
_traffic_cache = {}

def init(firebase_db):
    global _firebase_db
    _firebase_db = firebase_db

def get_traffic():
    return _traffic_cache.copy()

def _classify_intensity(count_per_min):
    if count_per_min < 5:
        return "LOW"
    elif count_per_min < 15:
        return "MEDIUM"
    return "HIGH"

def _push_traffic(data):
    if not _firebase_db:
        return
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _firebase_db.child("traffic").child(LAMP_ID).child(timestamp).set(data)
    except Exception as e:
        log_event("TRAFFIC", "Firebase push failed: " + str(e), "ERROR")

def monitor_loop():
    global _traffic_cache
    while True:
        try:
            raw      = get_latest()
            traffic  = raw.get("traffic", {})
            if not traffic:
                time.sleep(1)
                continue
            speed    = traffic.get("speed",    0)
            count_in = traffic.get("count_in", 0)
            obstacle = traffic.get("obstacle", 0)
            intensity = _classify_intensity(count_in)

            _traffic_cache = {
                "speed":     speed,
                "count_in":  count_in,
                "intensity": intensity,
                "obstacle":  obstacle,
                "time":      datetime.now().isoformat()
            }

            if speed > SPEED_LIMIT_KMPH:
                log_event("TRAFFIC", "SPEEDING: " + str(speed) + " kmh limit:" + str(SPEED_LIMIT_KMPH))
                trigger_buzzer(pattern="alert")

            if obstacle:
                log_event("TRAFFIC", "Obstacle detected", "WARNING")
                from alert_engine import push_firebase
                gps = raw.get("gps", {})
                push_firebase("obstacles/" + LAMP_ID + "/" + datetime.now().strftime("%Y%m%d_%H%M%S"), {
                    "gps":  gps,
                    "time": datetime.now().isoformat()
                })

            _push_traffic(_traffic_cache)

        except Exception as e:
            log_event("TRAFFIC", "Monitor error: " + str(e), "ERROR")
        time.sleep(5)

def start(firebase_db):
    init(firebase_db)
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    log_event("TRAFFIC", "Traffic monitor started")
    return t
