#include <Arduino.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <BH1750.h>
#include <MPU6050.h>
#include <math.h>

// ── PIN DEFINITIONS (Classic ESP32) ─────
#define PIN_DHT        4
#define PIN_RAIN       5
#define PIN_MQ135      34   // input-only, ADC1
#define PIN_VIBRATION  35   // input-only
#define PIN_BUTTON     25   // MUST wire to GND when pressed (INPUT_PULLUP).
                            // NEVER connect this pin to any external voltage
                            // rail (5V/12V) - GPIO max safe input is ~3.6V.
                            // This is what killed the previous two boards.
#define PIN_LED_RED    26
#define PIN_LED_BLUE   27
#define PIN_LED_AMBER  14
#define PIN_GPS_RX     16
#define PIN_GPS_TX     17
#define PIN_LED_WHITE  13
#define PIN_I2C_SCL    22
#define PIN_I2C_SDA    21
#define PIN_BUZZER     19

// ── CONSTANTS ───────────────────────────
#define LAMP_ID         "LAMP_001"
#define BAUD_RATE       115200
#define LUX_DAYLIGHT    500
#define LUX_DUSK        100
#define LUX_NIGHT       10
#define TEMP_HOT        35.0
#define TEMP_COLD       20.0
#define HUM_FOG         85
#define ACC_THRESHOLD   15.0
#define SEND_INTERVAL   1000

// ── OBJECTS ─────────────────────────────
DHT         dht(PIN_DHT, DHT22);
TinyGPSPlus gps;
HardwareSerial gpsSerial(1);
BH1750      lightMeter;
MPU6050     mpu;

// ── SENSOR STATE ────────────────────────
float temp      = 25.0, hum = 50.0;
float lat       = 13.0827, lon = 80.2707;
int   gps_fix   = 0;
int   rain      = 0;
int   aqi       = 0;
float lux       = 0;
int   vib       = 0;
float acc_total = 9.8;
int   count_in  = 0, count_out = 0;
float speed_kmh = 0;
int   sos       = 0;
int   alr       = 0;

// ── LED STATE ────────────────────────────
int  led_white = 0, led_red = 0;
int  led_blue  = 0, led_amber = 0;
bool emergency_mode  = false;
String current_color = "off";

// ── TIMING ──────────────────────────────
unsigned long last_send = 0;
unsigned long last_dht  = 0;
unsigned long last_mpu  = 0;
unsigned long last_lux  = 0;
unsigned long last_led  = 0;

// ── LED FUNCTIONS ────────────────────────
void apply_leds() {
  analogWrite(PIN_LED_WHITE, led_white);
  analogWrite(PIN_LED_RED,   led_red);
  analogWrite(PIN_LED_BLUE,  led_blue);
  analogWrite(PIN_LED_AMBER, led_amber);
}

void leds_off() {
  led_white = 0; led_red   = 0;
  led_blue  = 0; led_amber = 0;
  apply_leds();
  current_color = "off";
}

void update_leds_smart() {
  if (emergency_mode) return;

  if (lux > LUX_DAYLIGHT) { leds_off(); return; }

  int base = map((int)lux, 0, LUX_DAYLIGHT, 255, 30);
  base = constrain(base, 30, 255);

  if (alr & 0x0A) {
    led_white = 0; led_blue = 0; led_amber = 0; led_red = 255;
    apply_leds(); current_color = "red"; return;
  }
  if (rain) {
    led_red = 0; led_white = base * 0.6; led_blue = base * 0.5; led_amber = 0;
    apply_leds(); current_color = "blue_white"; return;
  }
  if (hum > HUM_FOG && lux < LUX_DUSK) {
    led_red = 0; led_blue = 0; led_white = base * 0.7; led_amber = base * 0.6;
    apply_leds(); current_color = "amber_white"; return;
  }
  if (lux > LUX_NIGHT && lux < LUX_DUSK) {
    led_red = 0; led_blue = 0; led_white = base * 0.4; led_amber = base * 0.3;
    apply_leds(); current_color = "dusk_warm"; return;
  }
  if (temp > TEMP_HOT) {
    led_red = 0; led_amber = 0; led_white = base; led_blue = base * 0.15;
    current_color = "cool_white";
  } else if (temp < TEMP_COLD) {
    led_red = 0; led_blue = 0; led_white = base; led_amber = base * 0.2;
    current_color = "warm_white";
  } else {
    led_red = 0; led_blue = 0; led_amber = 0; led_white = base;
    current_color = "white";
  }
  apply_leds();
}

void set_led_command(String color, int brightness) {
  if (color == "red") {
    emergency_mode = true;
    led_white = 0; led_blue = 0; led_amber = 0; led_red = brightness;
  } else if (color == "blue") {
    emergency_mode = false;
    led_red = 0; led_amber = 0;
    led_white = brightness * 0.6; led_blue = brightness * 0.5;
  } else if (color == "amber") {
    emergency_mode = false;
    led_red = 0; led_blue = 0;
    led_white = brightness * 0.7; led_amber = brightness * 0.6;
  } else if (color == "white") {
    emergency_mode = false;
    led_red = 0; led_blue = 0; led_amber = 0; led_white = brightness;
  } else if (color == "off") {
    emergency_mode = false;
    leds_off();
  }
  current_color = color;
  apply_leds();
}

// ── BUZZER (piezo, non-blocking) ────────
unsigned long buzzer_start  = 0;
bool          buzzer_active = false;

void buzzer_sos_start() {
  buzzer_active = true;
  buzzer_start  = millis();
  digitalWrite(PIN_BUZZER, HIGH);
}

void buzzer_alert_start() {
  buzzer_active = true;
  buzzer_start  = millis();
  digitalWrite(PIN_BUZZER, HIGH);
}

void buzzer_update() {
  if (!buzzer_active) return;
  unsigned long elapsed = millis() - buzzer_start;
  if (elapsed < 200)       digitalWrite(PIN_BUZZER, HIGH);
  else if (elapsed < 500)  digitalWrite(PIN_BUZZER, LOW);
  else if (elapsed < 700)  digitalWrite(PIN_BUZZER, HIGH);
  else if (elapsed < 1000) digitalWrite(PIN_BUZZER, LOW);
  else if (elapsed < 1200) digitalWrite(PIN_BUZZER, HIGH);
  else if (elapsed < 1500) digitalWrite(PIN_BUZZER, LOW);
  else { buzzer_active = false; digitalWrite(PIN_BUZZER, LOW); }
}

// ── COMMAND PARSER (from UNO Q over Serial) ──
void parse_command(String cmd_str) {
  StaticJsonDocument<256> doc;
  if (deserializeJson(doc, cmd_str)) return;
  String cmd = doc["cmd"].as<String>();

  if (cmd == "led") {
    set_led_command(doc["color"].as<String>(), doc["brightness"] | 200);
  } else if (cmd == "buzzer") {
    String pat = doc["pattern"].as<String>();
    if (pat == "sos")   buzzer_sos_start();
    if (pat == "alert") buzzer_alert_start();
  } else if (cmd == "reset_count") {
    count_in = 0; count_out = 0;
  } else if (cmd == "emergency_off") {
    emergency_mode = false;
    alr &= ~0x0A;
  }
}

// ── SEND JSON TO UNO Q ──────────────────
void send_json() {
  StaticJsonDocument<512> doc;
  doc["lamp"] = LAMP_ID;
  doc["t"]    = millis();

  JsonObject g = doc.createNestedObject("gps");
  g["lat"] = lat; g["lon"] = lon; g["fix"] = gps_fix;

  JsonObject e = doc.createNestedObject("env");
  e["temp"] = temp; e["hum"] = hum; e["rain"] = rain;
  e["aqi"]  = aqi;
  e["ldr"]  = (int)lux;

  JsonObject m = doc.createNestedObject("motion");
  m["vib"] = vib; m["acc"] = acc_total; m["pir"] = 1;

  JsonObject t = doc.createNestedObject("traffic");
  t["count_in"] = count_in; t["count_out"] = count_out;
  t["speed"] = speed_kmh;   t["obstacle"] = 0;

  JsonObject a = doc.createNestedObject("audio");
  a["rms"] = 0; a["event"] = 0;

  doc["sos"] = sos;
  doc["alr"] = alr;

  JsonObject l = doc.createNestedObject("led");
  l["white"] = led_white; l["red"] = led_red;
  l["blue"]  = led_blue;  l["amber"] = led_amber;
  l["color"] = current_color;

  String out;
  serializeJson(doc, out);
  Serial.println(out);
}

// ── SETUP ───────────────────────────────
void setup() {
  Serial.begin(BAUD_RATE);
  delay(2000);
  Serial.println("MargRaksha ESP32 Booting...");

  gpsSerial.begin(9600, SERIAL_8N1, PIN_GPS_RX, PIN_GPS_TX);
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setTimeOut(1000);

  dht.begin();

  if (lightMeter.begin()) Serial.println("BH1750 OK");
  else Serial.println("BH1750 not found - using default lux");

  mpu.initialize();
  if (mpu.testConnection()) Serial.println("MPU6050 OK");
  else Serial.println("MPU6050 not found");

  pinMode(PIN_RAIN,      INPUT);
  pinMode(PIN_VIBRATION, INPUT);
  pinMode(PIN_BUTTON,    INPUT_PULLUP);
  pinMode(PIN_LED_WHITE, OUTPUT);
  pinMode(PIN_LED_RED,   OUTPUT);
  pinMode(PIN_LED_BLUE,  OUTPUT);
  pinMode(PIN_LED_AMBER, OUTPUT);
  pinMode(PIN_BUZZER,    OUTPUT);

  leds_off();
  Serial.println("MargRaksha ESP32 Ready!");
}

// ── LOOP ────────────────────────────────
void loop() {
  unsigned long now = millis();

  buzzer_update();

  if (now - last_dht > 2000) {
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) temp = t;
    if (!isnan(h)) hum  = h;
    last_dht = now;
  }

  if (now - last_lux > 500) {
    float reading = lightMeter.readLightLevel();
    if (reading >= 0) {
      lux = reading;
    } else {
      Serial.println("[BH1750] Device is not configured! Attempting reinit...");
      if (lightMeter.begin()) {
        Serial.println("[BH1750] Reinit successful");
      }
    }
    last_lux = now;
  }

  if (now - last_mpu > 100) {
    int16_t ax, ay, az, gx, gy, gz;
    mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
    float axf = ax / 16384.0 * 9.8;
    float ayf = ay / 16384.0 * 9.8;
    float azf = az / 16384.0 * 9.8;
    acc_total = sqrt(axf*axf + ayf*ayf + azf*azf);
    if (acc_total > ACC_THRESHOLD) {
      alr |= 0x02;
      emergency_mode = true;
      set_led_command("red", 255);
      buzzer_sos_start();
    }
    last_mpu = now;
  }

  rain = digitalRead(PIN_RAIN) == LOW ? 1 : 0;
  aqi  = analogRead(PIN_MQ135);
  vib  = digitalRead(PIN_VIBRATION);

  static bool last_button_state = HIGH;
  bool button_state = digitalRead(PIN_BUTTON);
  if (button_state == LOW && last_button_state == HIGH) {
    sos = 1; alr |= 0x08;
    emergency_mode = true;
    set_led_command("red", 255);
    buzzer_sos_start();
  }
  last_button_state = button_state;
  if (button_state == HIGH) sos = 0;

  if (now - last_led > 1000) {
    update_leds_smart();
    last_led = now;
  }

  while (gpsSerial.available()) gps.encode(gpsSerial.read());
  if (gps.location.isValid()) {
    lat = gps.location.lat();
    lon = gps.location.lng();
    gps_fix = 1;
  }

  static unsigned long last_gps_debug = 0;
  if (now - last_gps_debug > 5000) {
    last_gps_debug = now;
    Serial.print("[GPS DEBUG] chars=");
    Serial.print(gps.charsProcessed());
    Serial.print(" sentencesWithFix=");
    Serial.print(gps.sentencesWithFix());
    Serial.print(" satellites=");
    Serial.println(gps.satellites.isValid() ? gps.satellites.value() : -1);
    if (gps.charsProcessed() < 10) {
      Serial.println("[GPS DEBUG] No data received - check wiring/TX-RX swap/power.");
    }
  }

  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    if (cmd.length() > 0) parse_command(cmd);
  }

  if (now - last_send >= SEND_INTERVAL) {
    send_json();
    last_send = now;
  }
}
