import cv2
import time
import threading
import urllib.request
import numpy as np
from datetime import datetime
from config import LAPTOP_CAM_STREAM, ESP32_CAM_CAPTURE, EVIDENCE_DIR
from event_logger import log_event

_laptop_frame  = None
_espcam_frame  = None
_laptop_lock   = threading.Lock()
_espcam_lock   = threading.Lock()
_laptop_online = False
_espcam_online = False
_laptop_last_seen = 0
_espcam_last_seen = 0
STALE_SECONDS = 3

def is_laptop_online(): return _laptop_online
def is_espcam_online(): return _espcam_online
def is_camera_online(): return _laptop_online or _espcam_online

def get_active_source():
    if _laptop_online: return "laptop"
    if _espcam_online: return "espcam"
    return "none"

def get_laptop_frame():
    with _laptop_lock:
        return _laptop_frame.copy() if _laptop_frame is not None else None

def get_espcam_frame():
    with _espcam_lock:
        return _espcam_frame.copy() if _espcam_frame is not None else None

def get_latest_frame():
    if _laptop_online:
        return get_laptop_frame()
    elif _espcam_online:
        return get_espcam_frame()
    return None

def save_evidence(frame, label="event"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"{EVIDENCE_DIR}/{label}_{timestamp}.jpg"
    cv2.imwrite(filename, frame)
    log_event("CAMERA", f"Evidence saved: {filename}")
    return filename

def _laptop_cam_thread():
    global _laptop_frame, _laptop_online, _laptop_last_seen
    log_event("CAMERA", f"Connecting to laptop stream: {LAPTOP_CAM_STREAM}")
    while True:
        cap = cv2.VideoCapture(LAPTOP_CAM_STREAM)
        if not cap.isOpened():
            log_event("CAMERA", "Laptop stream not reachable - retrying in 3s", "WARNING")
            _laptop_online = False
            time.sleep(3)
            continue

        log_event("CAMERA", "Laptop stream connected")
        while True:
            ret, frame = cap.read()
            if not ret:
                log_event("CAMERA", "Laptop stream dropped - reconnecting", "WARNING")
                _laptop_online = False
                break
            with _laptop_lock:
                _laptop_frame = frame
            _laptop_online = True
            _laptop_last_seen = time.time()
        cap.release()
        time.sleep(1)

def _grab_frame_from(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            img_array = np.asarray(bytearray(resp.read()), dtype=np.uint8)
            return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception:
        return None

def _esp32cam_thread():
    global _espcam_frame, _espcam_online, _espcam_last_seen
    while True:
        frame = _grab_frame_from(ESP32_CAM_CAPTURE)
        if frame is not None:
            with _espcam_lock:
                _espcam_frame = frame
            _espcam_online = True
            _espcam_last_seen = time.time()
        elif time.time() - _espcam_last_seen > STALE_SECONDS:
            _espcam_online = False
        time.sleep(0.1)

def start_camera():
    t1 = threading.Thread(target=_laptop_cam_thread, daemon=True)
    t2 = threading.Thread(target=_esp32cam_thread, daemon=True)
    t1.start()
    t2.start()
    log_event("CAMERA", "Camera threads started (laptop primary, ESP32-CAM standby)")
    return t1, t2
