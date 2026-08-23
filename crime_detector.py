# MargRaksha V2 - crime_detector.py
import time
import threading
from datetime import datetime
from config import (AUDIO_RMS_THRESHOLD, CRIME_HOURS_START,
                    CRIME_HOURS_END, LAMP_ID)
from event_logger import log_event
from uart_parser import get_latest, set_led, trigger_buzzer
from camera_engine import get_latest_frame, save_evidence

_firebase_db = None

def init(firebase_db):
    global _firebase_db
    _firebase_db = firebase_db

def _is_crime_hours():
    hour = datetime.now().hour
    return hour >= CRIME_HOURS_START or hour < CRIME_HOURS_END

def _check_crime():
    data   = get_latest()
    audio  = data.get("audio",  {})
    motion = data.get("motion", {})
    rms      = audio.get("rms",  0)
    vib      = motion.get("vib", 0)
    is_night = _is_crime_hours()
    if rms > AUDIO_RMS_THRESHOLD and not vib and is_night:
        log_event("CRIME", "Crime suspected - RMS:" + str(rms) + " night:" + str(is_night), "WARNING")
        frame = get_latest_frame()
        evidence_path = save_evidence(frame, "crime") if frame is not None else None
        gps = data.get("gps", {})
        from alert_engine import trigger_crime
        trigger_crime(gps, evidence_path)
        set_led(color="red", brightness=255)
        trigger_buzzer(pattern="sos")
        return True
    return False

def monitor_loop():
    while True:
        try:
            _check_crime()
        except Exception as e:
            log_event("CRIME", "Monitor error: " + str(e), "ERROR")
        time.sleep(2)

def start(firebase_db):
    init(firebase_db)
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    log_event("CRIME", "Crime detector started")
    return t
