# ---------------------------------------------------------------
# MargRaksha - event_logger.py
# Writes timestamped events to local log file
# Also pushes telemetry to Firebase
# ---------------------------------------------------------------

import os
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from config import LOG_DIR, EVENT_LOG

# -- Create logs directory if missing -------------------------
os.makedirs(LOG_DIR, exist_ok=True)

# -- Setup rotating logger ------------------------------------
# Rotates daily, keeps 7 days of logs
logger = logging.getLogger("MargRaksha")
logger.setLevel(logging.DEBUG)

handler = TimedRotatingFileHandler(
    EVENT_LOG,
    when="midnight",     # rotate at midnight
    interval=1,          # every 1 day
    backupCount=7        # keep 7 days
)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)

# Also print to console so App Lab terminal shows live logs
console = logging.StreamHandler()
console.setFormatter(formatter)

logger.addHandler(handler)
logger.addHandler(console)

# -- Firebase reference (set later by main) -------------------
_firebase_db = None

def set_firebase(db):
    """Called by uno_q_brain.py after Firebase initializes."""
    global _firebase_db
    _firebase_db = db

def log_event(module, message, level="INFO"):
    """
    Log an event locally and optionally to Firebase.
    module: which subsystem (e.g. "UART", "YOLO", "SOS")
    message: what happened
    level: INFO / WARNING / ERROR
    """
    full_msg = f"[{module}] {message}"

    if level == "ERROR":
        logger.error(full_msg)
    elif level == "WARNING":
        logger.warning(full_msg)
    else:
        logger.info(full_msg)

    # Push to Firebase if connected
    if _firebase_db:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            _firebase_db.child("logs").child(timestamp).set({
                "module":  module,
                "message": message,
                "level":   level,
                "time":    datetime.now().isoformat()
            })
        except Exception:
            pass  # never crash main system over a logging failure

def log_telemetry(db, lamp_id, env_data):
    """
    Push environmental telemetry to Firebase every 60 seconds.
    Called by environment_monitor.py
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db.child("telemetry").child(lamp_id).child(timestamp).set(env_data)
    except Exception as e:
        log_event("TELEMETRY", f"Firebase push failed: {e}", "ERROR")
