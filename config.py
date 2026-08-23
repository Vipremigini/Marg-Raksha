# ---------------------------------------------------------------
#  MargRaksha - config.py
#  Central configuration for all modules
#
#  NOTE: Sensitive keys, passwords, and phone numbers have been 
#        removed/obfuscated for security reasons.
# ---------------------------------------------------------------

# -- LAMP IDENTITY --------------------------------------------
LAMP_ID            = "LAMP_001"
LAMP_LOCATION      = "SRM University, Chennai"

# -- NETWORK --------------------------------------------------
WIFI_SSID          = "Bhargave"
WIFI_PASSWORD      = "YOUR_WIFI_PASSWORD"

# -- CAMERA ---------------------------------------------------
# Primary camera: USB webcam (mic built-in, used for audio too)
# Secondary camera: ESP32-CAM (number plate angle / backup)
USE_USB_WEBCAM    = True          # FIXED: webcam is primary
WEBCAM_INDEX      = 0             # /dev/video0 - change if wrong
WEBCAM_WIDTH      = 1280
WEBCAM_HEIGHT     = 720
WEBCAM_FPS        = 30

ESP32_CAM_IP      = "10.42.0.200"
ESP32_CAM_STREAM  = "http://10.42.0.200:81/stream"
ESP32_CAM_CAPTURE = "http://10.42.0.200/capture"

# -- UART (ESP32 sensor node) ---------------------------------
UART_PORT         = "/dev/ttyUSB0"
UART_BAUD         = 115200
UART_TIMEOUT_SECONDS = 10

# -- FIREBASE -------------------------------------------------
FIREBASE_URL      = "https://your-firebase-project-id-default-rtdb.asia-southeast1.firebasedatabase.app"
FIREBASE_KEY_PATH = "/home/arduino/margrakksha/serviceAccountKey.json"

# -- TWILIO ---------------------------------------------------
TWILIO_SID        = "YOUR_TWILIO_SID"
TWILIO_TOKEN      = "YOUR_TWILIO_TOKEN"
TWILIO_FROM       = "YOUR_TWILIO_PHONE_NUMBER"
POLICE_PHONE      = "+91XXXXXXXXXX"
HOSPITAL_PHONE    = "+91XXXXXXXXXX"

# -- PLATE RECOGNITION ----------------------------------------
PLATE_API_KEY     = "YOUR_PLATE_API_KEY"
PLATE_API_URL     = "https://api.platerecognizer.com/v1/plate-reader/"
TEST_PLATE        = "TN01AB1234"

# -- DETECTION THRESHOLDS -------------------------------------
SPEED_LIMIT_KMPH          = 60
ACCIDENT_CONFIDENCE       = 0.55
ACCIDENT_MODERATE         = 0.45
AQI_CRITICAL              = 200
TEMP_HEAT_ADVISORY        = 42
HUMIDITY_FOG_THRESHOLD    = 85
AUDIO_RMS_THRESHOLD       = 1500

# Drunk driving detection
DRUNK_SWERVE_THRESHOLD_PX = 40    # pixels of lateral deviation per frame
DRUNK_SWERVE_WINDOW       = 30    # frames to analyse (1 second at 30fps)
DRUNK_SWERVE_COUNT        = 5     # how many swerves in window = drunk flag

# Speed estimation
SPEED_PIXELS_PER_METER    = 12.0  # tune after mounting camera
SPEED_TRAP_FRAMES         = 15    # frames between speed measurements

# Crime / night watch
CRIME_HOURS_START         = 22
CRIME_HOURS_END           = 5

# Ultrasonic pothole
ULTRASONIC_POTHOLE_CM     = 30

# -- AUDIO ----------------------------------------------------
AUDIO_SAMPLE_RATE         = 16000
AUDIO_CHANNELS            = 1
AUDIO_CHUNK_SIZE          = 1024

# -- MAX98357A SPEAKER ----------------------------------------
SPEAKER_ENABLED           = True
SPEAKER_VOLUME            = 80   # percent

# -- PATHS ----------------------------------------------------
BASE_DIR      = "/home/arduino/margrakksha"
LOG_DIR       = "/home/arduino/margrakksha/logs"
EVIDENCE_DIR  = "/home/arduino/margrakksha/evidence"
MODEL_DIR     = "/home/arduino/margrakksha/models"
EVENT_LOG     = "/home/arduino/margrakksha/logs/events.log"

# -- DASHBOARD ------------------------------------------------
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8080

# -- ALERT BITMASK --------------------------------------------
ALR_SPEEDING      = 0x01
ALR_ACCIDENT      = 0x02
ALR_CRIME         = 0x04
ALR_SOS           = 0x08
ALR_POTHOLE       = 0x10
ALR_AQI_CRITICAL  = 0x20
ALR_DRUNK_DRIVING = 0x40
ALR_HELMET        = 0x80

# -- LAPTOP/NETWORK BRIDGING ----------------------------------
LAPTOP_CAM_IP      = "10.98.166.140"
LAPTOP_CAM_CAPTURE = "http://10.98.166.140:9000/capture"
LAPTOP_CAM_STREAM  = "http://10.98.166.140:9000/stream"

ESP32_SENSOR_URL  = "http://10.98.166.140:9001/sensor"
ESP32_COMMAND_URL = "http://10.98.166.140:9001/command"
