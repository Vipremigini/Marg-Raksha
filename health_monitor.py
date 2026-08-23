import time
import threading
import psutil
from datetime import datetime
from config import LAMP_ID, UART_TIMEOUT_SECONDS
from event_logger import log_event
from uart_parser import is_sensor_alive
from camera_engine import is_camera_online

_firebase_db = None

def init(firebase_db):
    global _firebase_db
    _firebase_db = firebase_db

def get_system_health():
    return {
        "cpu_percent":  psutil.cpu_percent(interval=1),
        "ram_percent":  psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "cpu_temp":     _get_cpu_temp(),
        "sensor_alive": is_sensor_alive(),
        "camera_online": is_camera_online(),
        "time":         datetime.now().isoformat()
    }

def _get_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    return entries[0].current
    except Exception:
        pass
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read()) / 1000.0
    except Exception:
        return 0.0

def _push_health(health):
    if not _firebase_db:
        return
    try:
        _firebase_db.child("system").child(LAMP_ID).child("health").set(health)
    except Exception as e:
        log_event("HEALTH", f"Firebase push failed: {e}", "ERROR")

def monitor_loop():
    while True:
        try:
            health = get_system_health()
            log_event("HEALTH",
                f"CPU:{health['cpu_percent']}% "
                f"RAM:{health['ram_percent']}% "
                f"DISK:{health['disk_percent']}% "
                f"TEMP:{health['cpu_temp']}C "
                f"SENSOR:{health['sensor_alive']} "
                f"CAM:{health['camera_online']}")
            _push_health(health)
            if not health["sensor_alive"]:
                log_event("HEALTH", "ESP32-S3 UART silent - sensor node offline!", "ERROR")
            if not health["camera_online"]:
                log_event("HEALTH", "Camera offline!", "WARNING")
        except Exception as e:
            log_event("HEALTH", f"Monitor error: {e}", "ERROR")
        time.sleep(60)

def start(firebase_db):
    init(firebase_db)
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    log_event("HEALTH", "Health monitor started")
    return t
