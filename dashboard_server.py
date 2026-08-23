import threading
import time
import cv2
from datetime import datetime
from collections import deque
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import uvicorn

from config import DASHBOARD_HOST, DASHBOARD_PORT, LAMP_ID, EVIDENCE_DIR
from event_logger import log_event
from uart_parser import get_latest, is_sensor_alive
from yolo_engine import get_detection
from health_monitor import get_system_health
from environment_monitor import get_env, get_gps
from traffic_monitor import get_traffic
from camera_engine import (
    get_latest_frame,
    get_laptop_frame,
    get_espcam_frame,
    is_laptop_online,
    is_espcam_online,
    get_active_source,
)

app = FastAPI()
_events = deque(maxlen=50)

def push_event(event_type, message, severity="INFO"):
    _events.appendleft({
        "time":     datetime.now().strftime("%H:%M:%S"),
        "type":     event_type,
        "message":  message,
        "severity": severity
    })

def get_events():
    return list(_events)

def get_dashboard_data():
    sensor  = get_latest()
    detect  = get_detection()
    health  = get_system_health()
    env     = get_env()
    gps     = get_gps()
    traffic = get_traffic()

    return {
        "lamp_id":   LAMP_ID,
        "time":      datetime.now().isoformat(),
        "gps":       gps,
        "env":       env,
        "traffic":   traffic,
        "detection": detect,
        "health":    health,
        "led":       sensor.get("led",   {}),
        "sos":       sensor.get("sos",   0),
        "alr":       sensor.get("alr",   0),
        "audio":     sensor.get("audio", {}),
        "sensor_alive": is_sensor_alive(),
        "cam_status": {
            "webcam_online": is_laptop_online(),
            "espcam_online": is_espcam_online(),
            "active_source": get_active_source(),
        },
    }

def _mjpeg_generator():
    while True:
        frame = get_latest_frame()
        if frame is None:
            time.sleep(0.1)
            continue
        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ret:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        time.sleep(1 / 15)

def _mjpeg_generator_webcam():
    while True:
        frame = get_laptop_frame()
        if frame is None:
            time.sleep(0.2)
            continue
        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ret:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        time.sleep(1 / 15)

def _mjpeg_generator_espcam():
    while True:
        frame = get_espcam_frame()
        if frame is None:
            time.sleep(0.2)
            continue
        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ret:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        time.sleep(1 / 15)

@app.get("/", response_class=HTMLResponse)
def dashboard():
    try:
        with open("/home/arduino/margrakksha/dashboard.html", "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>dashboard.html not found</h1>"

@app.get("/api/data")
def api_data():
    return JSONResponse(get_dashboard_data())

@app.get("/api/health")
def api_health():
    return JSONResponse(get_system_health())

@app.get("/api/detection")
def api_detection():
    return JSONResponse(get_detection())

@app.get("/api/events")
def api_events():
    return JSONResponse(get_events())

@app.get("/api/stream")
def api_stream():
    return StreamingResponse(_mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/stream/webcam")
def api_stream_webcam():
    return StreamingResponse(_mjpeg_generator_webcam(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/stream/espcam")
def api_stream_espcam():
    return StreamingResponse(_mjpeg_generator_espcam(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/traffic")
def api_traffic():
    return JSONResponse(get_traffic())

@app.get("/api/env")
def api_env():
    return JSONResponse(get_env())

def start():
    t = threading.Thread(
        target=lambda: uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT, log_level="warning"),
        daemon=True
    )
    t.start()
    log_event("DASHBOARD", f"Server started on port {DASHBOARD_PORT}")
    return t
