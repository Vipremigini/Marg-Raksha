import cv2
import time
import threading
import os
from datetime import datetime
from ultralytics import YOLO
import torch
torch.set_num_threads(3)
from config import ACCIDENT_CONFIDENCE, ACCIDENT_MODERATE, MODEL_DIR, EVIDENCE_DIR
from event_logger import log_event
from camera_engine import get_latest_frame, save_evidence

latest_detection = {
    "accident": False,
    "confidence": 0.0,
    "helmet_violation": False,
    "pothole": False,
    "plate_frame": None,
    "person_count": 0,
    "vehicle_count": 0,
    "last_updated": None
}
detection_lock = threading.Lock()

on_accident_detected = None
on_helmet_violation = None
on_pothole_detected = None

HELMET_MODEL_PATH = os.path.join(MODEL_DIR, "helmet_ppe.pt")
ACCIDENT_MODEL_PATH = os.path.join(MODEL_DIR, "accident.pt")
ACCIDENT_CHECK_INTERVAL_SECONDS = 8
ACCIDENT_TRIGGER_CLASSES = ["detected-injury", "fire", "high", "medium", "low"]

INFER_WIDTH = 480


def get_detection():
    with detection_lock:
        return dict(latest_detection)


def _get_model_path(model_name="yolov8n.pt"):
    model_path = os.path.join(MODEL_DIR, model_name)
    if not os.path.exists(model_path):
        log_event("YOLO", f"Downloading {model_name}")
        m = YOLO(model_name)
        if os.path.exists(model_name):
            os.rename(model_name, model_path)
    return model_path


def _resize_for_inference(frame):
    h, w = frame.shape[:2]
    if w <= INFER_WIDTH:
        return frame
    scale = INFER_WIDTH / w
    return cv2.resize(frame, (INFER_WIDTH, int(h * scale)))


def _detect_pothole(frame, results, model):
    for box in results.boxes:
        label = model.names[int(box.cls[0])].lower()
        if "pothole" in label or "hole" in label or "crack" in label:
            log_event("YOLO", "Pothole detected via YOLO class")
            return True

    height, width = frame.shape[:2]
    road_region = frame[height // 2:, :]
    gray = cv2.cvtColor(road_region, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    _, thresh = cv2.threshold(blurred, 40, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 2000 < area < 30000:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / float(h)
            if 0.3 < aspect_ratio < 3.0:
                log_event("YOLO", f"Pothole detected via vision - area:{area} ratio:{aspect_ratio:.2f}")
                return True
    return False


def _crop_with_padding(frame, x1, y1, x2, y2, pad_ratio=0.6):
    h, w = frame.shape[:2]
    box_w = x2 - x1
    box_h = y2 - y1
    pad_x = int(box_w * pad_ratio)
    pad_y = int(box_h * pad_ratio)
    cx1 = max(0, x1 - pad_x)
    cy1 = max(0, y1 - pad_y)
    cx2 = min(w, x2 + pad_x)
    cy2 = min(h, y2 + pad_y)
    if cx2 <= cx1 or cy2 <= cy1:
        return None
    return frame[cy1:cy2, cx1:cx2]


def _check_helmet(frame, helmet_model):
    try:
        results = helmet_model(frame, verbose=False)[0]
        seen = []
        for box in results.boxes:
            label = helmet_model.names[int(box.cls[0])].lower()
            conf = float(box.conf[0])
            seen.append(f"{label}:{conf:.2f}")
            if "no_helmet" in label and conf > 0.35:
                log_event("YOLO", f"Helmet CHECK saw: {seen} -> VIOLATION")
                return True
        log_event("YOLO", f"Helmet CHECK saw: {seen if seen else 'nothing'} -> no violation")
    except Exception as e:
        log_event("YOLO", f"Helmet model error: {e}", "ERROR")
    return False


def _fast_detection_loop(model_path):
    global latest_detection
    log_event("YOLO", f"Loading general model: {model_path}")
    model = YOLO(model_path)

    helmet_model = None
    if os.path.exists(HELMET_MODEL_PATH):
        log_event("YOLO", "Loading helmet detection model")
        helmet_model = YOLO(HELMET_MODEL_PATH)
    else:
        log_event("YOLO", "Helmet model not found - helmet detection disabled", "WARNING")

    log_event("YOLO", "Fast detection loop running (person/vehicle/helmet/pothole)")
    last_debug_log = 0

    while True:
        frame = get_latest_frame()
        if frame is None:
            time.sleep(0.3)
            continue
        try:
            small = _resize_for_inference(frame)
            results = model(small, verbose=False)[0]
            person_count = 0
            vehicle_count = 0
            motorcycle_present = False
            motorcycle_box = None
            detected_labels = []

            for box in results.boxes:
                label = model.names[int(box.cls[0])].lower()
                conf = float(box.conf[0])
                detected_labels.append(f"{label}:{conf:.2f}")
                if label == "person":
                    person_count += 1
                if label in ["car", "truck", "bus", "motorcycle"]:
                    vehicle_count += 1
                if label == "motorcycle":
                    motorcycle_present = True
                    xyxy = box.xyxy[0].tolist()
                    motorcycle_box = [int(v) for v in xyxy]

            now = time.time()
            if now - last_debug_log > 2:
                log_event("YOLO", f"Seen: {detected_labels if detected_labels else 'nothing'}")
                last_debug_log = now

            pothole = _detect_pothole(small, results, model)

            helmet_violation = False
            if helmet_model is not None and motorcycle_present and motorcycle_box is not None:
                x1, y1, x2, y2 = motorcycle_box
                cropped = _crop_with_padding(small, x1, y1, x2, y2, pad_ratio=0.6)
                if cropped is not None and cropped.shape[0] > 10 and cropped.shape[1] > 10:
                    helmet_violation = _check_helmet(cropped, helmet_model)
                    if helmet_violation and on_helmet_violation:
                        on_helmet_violation(frame.copy())

            with detection_lock:
                latest_detection["helmet_violation"] = helmet_violation
                latest_detection["pothole"] = pothole
                latest_detection["plate_frame"] = None
                latest_detection["person_count"] = person_count
                latest_detection["vehicle_count"] = vehicle_count
                latest_detection["last_updated"] = datetime.now().isoformat()
        except Exception as e:
            log_event("YOLO", f"Fast loop error: {e}", "ERROR")
        time.sleep(0.6)


def _accident_detection_loop():
    global latest_detection
    if not os.path.exists(ACCIDENT_MODEL_PATH):
        log_event("YOLO", "Accident model not found - accident detection disabled", "WARNING")
        return

    log_event("YOLO", "Loading accident detection model (separate thread)")
    accident_model = YOLO(ACCIDENT_MODEL_PATH)
    log_event("YOLO", "Accident detection loop running independently")

    while True:
        start = time.time()
        frame = get_latest_frame()
        if frame is None:
            time.sleep(1)
            continue
        try:
            small = _resize_for_inference(frame)
            results = accident_model(small, verbose=False)[0]
            detected = False
            best_conf = 0.0
            seen = []
            for box in results.boxes:
                label = accident_model.names[int(box.cls[0])].lower()
                conf = float(box.conf[0])
                seen.append(f"{label}:{conf:.2f}")
                if any(cls in label for cls in ACCIDENT_TRIGGER_CLASSES):
                    detected = True
                    best_conf = max(best_conf, conf)

            log_event("YOLO", f"Accident model saw: {seen if seen else 'nothing'}")

            with detection_lock:
                latest_detection["accident"] = detected
                latest_detection["confidence"] = best_conf

            if detected:
                evidence_path = save_evidence(frame.copy(), "accident")
                log_event("YOLO", f"Accident conf:{best_conf:.2f} saved:{evidence_path}")
                if best_conf >= ACCIDENT_CONFIDENCE and on_accident_detected:
                    on_accident_detected(best_conf, evidence_path, None)

            elapsed = time.time() - start
            log_event("YOLO", f"Accident check took {elapsed:.1f}s")
        except Exception as e:
            log_event("YOLO", f"Accident loop error: {e}", "ERROR")

        time.sleep(max(0.5, ACCIDENT_CHECK_INTERVAL_SECONDS - (time.time() - start)))


def start_yolo(model_name="yolov8n.pt"):
    model_path = _get_model_path(model_name)
    t1 = threading.Thread(target=_fast_detection_loop, args=(model_path,), daemon=True)
    t2 = threading.Thread(target=_accident_detection_loop, daemon=True)
    t1.start()
    t2.start()
    log_event("YOLO", "YOLO threads started (fast + accident, independent)")
    return t1, t2
