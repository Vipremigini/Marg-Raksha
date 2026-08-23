# MargRaksha V2 - alert_engine.py
from twilio.rest import Client
import firebase_admin
from firebase_admin import db
from datetime import datetime
from config import (TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM,
                    POLICE_PHONE, HOSPITAL_PHONE, LAMP_ID)
from event_logger import log_event
from arogya_vault import format_for_sms

_twilio_client = None

def init_twilio():
    global _twilio_client
    try:
        _twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
        log_event("ALERT", "Twilio initialized")
    except Exception as e:
        log_event("ALERT", "Twilio init failed: " + str(e), "ERROR")

def send_sms(to, message):
    if not _twilio_client:
        log_event("ALERT", "Twilio not initialized", "WARNING")
        return
    try:
        _twilio_client.messages.create(body=message, from_=TWILIO_FROM, to=to)
        log_event("ALERT", "SMS sent to " + to)
    except Exception as e:
        log_event("ALERT", "SMS failed: " + str(e), "ERROR")

def push_firebase(path, data):
    try:
        db.reference(path).set(data)
        log_event("ALERT", "Firebase pushed: " + path)
    except Exception as e:
        log_event("ALERT", "Firebase push failed: " + str(e), "ERROR")

def trigger_accident(confidence, evidence_path, gps, plate, medical_data):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_event("ALERT", "ACCIDENT ALERT - plate:" + str(plate))
    push_firebase("accidents/" + LAMP_ID + "/" + timestamp, {
        "confidence": confidence,
        "gps": gps,
        "plate": plate,
        "evidence": evidence_path,
        "time": datetime.now().isoformat()
    })
    medical_str = format_for_sms(medical_data)
    send_sms(POLICE_PHONE, "ACCIDENT at " + str(gps) + " | Plate:" + str(plate) + " | Conf:" + str(round(confidence*100)) + "% | " + LAMP_ID)
    send_sms(HOSPITAL_PHONE, "INCOMING PATIENT | " + medical_str + " | Location:" + str(gps))

def trigger_sos(gps):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_event("ALERT", "SOS EMERGENCY at " + str(gps))
    push_firebase("sos/" + LAMP_ID + "/" + timestamp, {
        "gps": gps,
        "time": datetime.now().isoformat()
    })
    send_sms(POLICE_PHONE, "SOS EMERGENCY | Location:" + str(gps) + " | LampID:" + LAMP_ID)

def trigger_crime(gps, evidence_path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_event("ALERT", "CRIME SUSPECTED at " + str(gps))
    push_firebase("crime/" + LAMP_ID + "/" + timestamp, {
        "gps": gps,
        "evidence": evidence_path,
        "time": datetime.now().isoformat()
    })
    send_sms(POLICE_PHONE, "CRIME ALERT | Location:" + str(gps) + " | LampID:" + LAMP_ID)

def trigger_helmet_violation(plate, evidence_path, gps):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_event("ALERT", "HELMET VIOLATION - plate:" + str(plate))
    push_firebase("violations/helmet/" + timestamp, {
        "plate": plate,
        "evidence": evidence_path,
        "gps": gps,
        "lamp_id": LAMP_ID,
        "time": datetime.now().isoformat()
    })
    send_sms(POLICE_PHONE, "HELMET VIOLATION | Plate:" + str(plate) + " | Location:" + str(gps) + " | " + LAMP_ID)

def trigger_drunk_driving(vehicle_type, evidence_path, gps, confidence):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_event("ALERT", "DRUNK DRIVING - type:" + str(vehicle_type))
    push_firebase("violations/drunk/" + timestamp, {
        "vehicle_type": vehicle_type,
        "confidence": confidence,
        "evidence": evidence_path,
        "gps": gps,
        "lamp_id": LAMP_ID,
        "time": datetime.now().isoformat()
    })
    send_sms(POLICE_PHONE, "DRUNK DRIVING | Vehicle:" + str(vehicle_type) + " | Conf:" + str(round(confidence*100)) + "% | Location:" + str(gps) + " | " + LAMP_ID)

def trigger_speed_violation(speed_kmh, plate, evidence_path, gps):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_event("ALERT", "SPEED VIOLATION - " + str(round(speed_kmh,1)) + " kmh")
    push_firebase("violations/speed/" + timestamp, {
        "speed_kmh": speed_kmh,
        "plate": plate,
        "evidence": evidence_path,
        "gps": gps,
        "lamp_id": LAMP_ID,
        "time": datetime.now().isoformat()
    })
    send_sms(POLICE_PHONE, "SPEED VIOLATION | " + str(round(speed_kmh,1)) + " kmh | Plate:" + str(plate) + " | Location:" + str(gps) + " | " + LAMP_ID)

def trigger_aqi(aqi_value, gps):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_event("ALERT", "AQI CRITICAL: " + str(aqi_value))
    push_firebase("alerts/aqi/" + LAMP_ID + "/" + timestamp, {
        "aqi": aqi_value,
        "gps": gps,
        "time": datetime.now().isoformat()
    })
