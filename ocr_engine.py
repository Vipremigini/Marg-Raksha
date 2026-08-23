import requests
import base64
import cv2
from config import PLATE_API_KEY, PLATE_API_URL, LAMP_ID
from event_logger import log_event

def read_plate(frame):
    """
    Send frame to PlateRecognizer API and return plate number.
    Returns plate string or None if not found.
    """
    try:
        _, img_encoded = cv2.imencode(".jpg", frame)
        img_bytes = img_encoded.tobytes()
        response = requests.post(
            PLATE_API_URL,
            headers={"Authorization": f"Token {PLATE_API_KEY}"},
            files={"upload": ("frame.jpg", img_bytes, "image/jpeg")},
            data={"regions": ["in"]},
            timeout=5
        )
        data = response.json()
        results = data.get("results", [])
        if results:
            plate = results[0]["plate"].upper().replace(" ", "")
            conf  = results[0].get("score", 0)
            log_event("OCR", f"Plate detected: {plate} conf:{conf:.2f}")
            return plate
        else:
            log_event("OCR", "No plate found in frame", "WARNING")
            return None
    except Exception as e:
        log_event("OCR", f"Plate API error: {e}", "ERROR")
        return None

def read_plate_from_file(filepath):
    """Read plate from saved evidence photo file."""
    frame = cv2.imread(filepath)
    if frame is None:
        log_event("OCR", f"Could not read file: {filepath}", "ERROR")
        return None
    return read_plate(frame)
