import cv2
import time
import socket
from flask import Flask, Response

app = Flask(__name__)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 20)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # always grab the newest frame, don't queue old ones


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _mjpeg_generator():
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue
        ret2, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if not ret2:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg.tobytes()
            + b"\r\n"
        )


@app.route("/stream")
def stream():
    return Response(_mjpeg_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/capture")
def capture():
    """Kept for compatibility / single-shot use (e.g. plate OCR snapshots)."""
    ret, frame = cap.read()
    if not ret:
        return "Camera error", 500
    ret2, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return Response(jpeg.tobytes(), mimetype="image/jpeg")


@app.route("/status")
def status():
    return {"status": "online", "device": "laptop_webcam"}


if __name__ == "__main__":
    ip = get_ip()
    print("Laptop camera server running.")
    print(f"Stream URL:  http://{ip}:9000/stream   <- use this one, it's the fast one")
    print(f"Capture URL: http://{ip}:9000/capture   <- single-shot, for OCR only")
    print("Keep this window open during the demo.")
    app.run(host="0.0.0.0", port=9000, threaded=True)
