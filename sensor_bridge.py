import json
import threading
import time
import socket
import serial
import serial.tools.list_ports
from flask import Flask, request, jsonify

app = Flask(__name__)

latest_data = {}
data_lock = threading.Lock()
last_received = 0

_ser = None
_ser_lock = threading.Lock()
ESP32_BAUD = 115200


def find_esp32_port():
    """Try to auto-detect the ESP32's COM port. Falls back to manual entry if not found."""
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        if "cp210" in desc or "ch340" in desc or "usb-serial" in desc or "silicon labs" in desc:
            return p.device
    if ports:
        print("Could not auto-detect ESP32 specifically. Available ports:")
        for i, p in enumerate(ports):
            print(f"  [{i}] {p.device} - {p.description}")
        choice = input("Enter the number of your ESP32's port: ")
        return ports[int(choice)].device
    return None


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


def _serial_reader_thread(port):
    global _ser, last_received
    backoff = 3
    while True:
        try:
            with _ser_lock:
                _ser = serial.Serial(port, ESP32_BAUD, timeout=1)
            print(f"Connected to ESP32 on {port}")
            backoff = 3

            while True:
                try:
                    raw = _ser.readline()
                    if raw:
                        print(f"RAW: {raw}")
                except Exception:
                    break
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line or line.startswith("["):
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                with data_lock:
                    latest_data.update(data)
                last_received = time.time()

        except serial.SerialException as e:
            print(f"Serial error: {e} - retry in {backoff}s")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            with _ser_lock:
                if _ser and _ser.is_open:
                    try:
                        _ser.close()
                    except Exception:
                        pass
                _ser = None
        time.sleep(backoff)
        backoff = min(backoff * 2, 30)


@app.route("/sensor")
def sensor():
    with data_lock:
        d = dict(latest_data)
    d["_alive"] = (time.time() - last_received) < 10
    return jsonify(d)


@app.route("/command", methods=["POST"])
def command():
    """UNO Q posts commands here (LED, buzzer, speak) - we relay to the ESP32."""
    cmd = request.get_json(force=True)
    with _ser_lock:
        if _ser is None or not _ser.is_open:
            return jsonify({"ok": False, "error": "ESP32 not connected"}), 503
        try:
            cmd_str = json.dumps(cmd) + "\n"
            _ser.write(cmd_str.encode("utf-8"))
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/status")
def status():
    return jsonify({"status": "online", "device": "esp32_bridge"})


if __name__ == "__main__":
    port = find_esp32_port()
    if not port:
        print("No serial ports found at all. Is the ESP32 plugged in?")
        exit(1)

    threading.Thread(target=_serial_reader_thread, args=(port,), daemon=True).start()

    ip = get_ip()
    print("ESP32 sensor bridge running.")
    print(f"Sensor data URL:  http://{ip}:9001/sensor")
    print(f"Command URL:      http://{ip}:9001/command")
    print("Keep this window open during the demo.")
    app.run(host="0.0.0.0", port=9001, threaded=True)
