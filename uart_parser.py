import json
import threading
import time
import urllib.request
import urllib.error
from config import ESP32_SENSOR_URL, ESP32_COMMAND_URL, UART_TIMEOUT_SECONDS
from event_logger import log_event

latest_data   = {}
data_lock     = threading.Lock()
last_received = time.time()

def get_latest():
    with data_lock:
        return dict(latest_data)

def is_sensor_alive():
    return (time.time() - last_received) < UART_TIMEOUT_SECONDS

def send_command(cmd_dict):
    """Send a JSON command to the ESP32, relayed through the laptop bridge."""
    try:
        data = json.dumps(cmd_dict).encode("utf-8")
        req = urllib.request.Request(
            ESP32_COMMAND_URL, data=data,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        log_event("UART", f"Send command failed: {e}", "ERROR")

def set_led(color="white", brightness=200):
    send_command({"cmd": "led", "color": color, "brightness": brightness})

def trigger_buzzer(pattern="sos"):
    send_command({"cmd": "buzzer", "pattern": pattern})

def reset_vehicle_count():
    send_command({"cmd": "reset_count"})

def emergency_off():
    send_command({"cmd": "emergency_off"})

def _poll_thread():
    global last_received
    log_event("UART", f"Polling ESP32 sensor data via laptop bridge: {ESP32_SENSOR_URL}")
    backoff = 3
    while True:
        try:
            with urllib.request.urlopen(ESP32_SENSOR_URL, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("_alive", True):
                with data_lock:
                    latest_data.update(data)
                last_received = time.time()
            backoff = 3
        except urllib.error.URLError as e:
            log_event("UART", f"Bridge unreachable: {e} - retry in {backoff}s", "WARNING")
            backoff = min(backoff * 2, 15)
        except Exception as e:
            log_event("UART", f"Unexpected error: {e}", "ERROR")
        time.sleep(1)

def start_uart():
    t = threading.Thread(target=_poll_thread, daemon=True)
    t.start()
    log_event("UART", "Sensor polling thread started (via laptop bridge)")
    return t
