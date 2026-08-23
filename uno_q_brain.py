# MargRaksha V2 - uno_q_brain.py
import time, threading, os, subprocess, firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
from config import (FIREBASE_URL, FIREBASE_KEY_PATH, LAMP_ID,
    SPEAKER_ENABLED, SPEAKER_VOLUME, DRUNK_SWERVE_THRESHOLD_PX,
    DRUNK_SWERVE_WINDOW, DRUNK_SWERVE_COUNT, SPEED_LIMIT_KMPH)
from event_logger import log_event, set_firebase
from uart_parser import start_uart, get_latest, is_sensor_alive, set_led, trigger_buzzer
from camera_engine import start_camera, get_latest_frame, save_evidence
from yolo_engine import start_yolo, get_detection
from ocr_engine import read_plate
from arogya_vault import get_vehicle_data, push_test_data
from alert_engine import (init_twilio, trigger_accident, trigger_sos,
    trigger_crime, trigger_helmet_violation, trigger_drunk_driving, trigger_speed_violation)
from environment_monitor import start as start_env
from traffic_monitor import start as start_traffic
from crime_detector import start as start_crime
from health_monitor import start as start_health
from dashboard_server import start as start_dashboard
import yolo_engine

def speak(text):
    if not SPEAKER_ENABLED: return
    threading.Thread(target=lambda: subprocess.Popen(
        ["espeak","-v","en","-s","130","-a",str(SPEAKER_VOLUME*2),text],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL),daemon=True).start()

def init_firebase():
    try:
        if os.path.exists(FIREBASE_KEY_PATH):
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred,{"databaseURL":FIREBASE_URL})
            log_event("BRAIN","Firebase connected")
            return db.reference()
        log_event("BRAIN","No key file","WARNING")
        return None
    except Exception as e:
        log_event("BRAIN","Firebase failed:"+str(e),"ERROR")
        return None

def on_accident(confidence,evidence_path,plate_frame):
    log_event("BRAIN","ACCIDENT conf:"+str(round(confidence,2)))
    gps=get_latest().get("gps",{})
    plate=read_plate(plate_frame) if plate_frame is not None else None
    medical=get_vehicle_data(plate) if plate else None
    set_led(color="red",brightness=255)
    trigger_buzzer(pattern="sos")
    speak("Emergency detected. Alerting control room.")
    trigger_accident(confidence,evidence_path,gps,plate,medical)

def on_helmet(frame):
    log_event("BRAIN","HELMET VIOLATION")
    gps=get_latest().get("gps",{})
    plate=read_plate(frame)
    if plate:
        trigger_helmet_violation(plate,save_evidence(frame,"helmet"),gps)
        speak("Helmet violation detected.")

def on_drunk_driving(vehicle_type,track_id,confidence):
    log_event("BRAIN","DRUNK DRIVING:"+vehicle_type)
    gps=get_latest().get("gps",{})
    frame=get_latest_frame()
    evidence=save_evidence(frame,"drunk") if frame is not None else None
    set_led(color="red",brightness=255)
    trigger_buzzer(pattern="sos")
    speak("Erratic driving detected. Alerting police.")
    trigger_drunk_driving(vehicle_type,evidence,gps,confidence)

def on_speed_violation(speed_kmh,plate_frame):
    log_event("BRAIN","SPEED:"+str(round(speed_kmh,1)))
    gps=get_latest().get("gps",{})
    plate=read_plate(plate_frame) if plate_frame is not None else None
    frame=get_latest_frame()
    evidence=save_evidence(frame,"speed") if frame is not None else None
    speak("Speed violation. Alert sent.")
    trigger_speed_violation(speed_kmh,plate,evidence,gps)

def sos_monitor():
    last=0
    while True:
        try:
            data=get_latest()
            if data.get("sos",0) and time.time()-last>60:
                last=time.time()
                gps=data.get("gps",{})
                log_event("BRAIN","SOS PRESSED")
                set_led(color="red",brightness=255)
                trigger_buzzer(pattern="sos")
                speak("SOS activated. Help is on the way. Stay calm.")
                trigger_sos(gps)
        except Exception as e:
            log_event("BRAIN","SOS error:"+str(e),"ERROR")
        time.sleep(0.5)

def adaptive_led():
    while True:
        try:
            data=get_latest()
            det=get_detection()
            env=data.get("env",{})
            alr=data.get("alr",0)
            lux=env.get("ldr",500)
            hum=env.get("hum",0)
            rain=env.get("rain",0)
            hour=datetime.now().hour
            if alr&0x0A or alr&0x08: set_led(color="red",brightness=255)
            elif det.get("accident"): set_led(color="red",brightness=255)
            elif rain: set_led(color="blue",brightness=200)
            elif hum>85 and lux<100: set_led(color="amber",brightness=255)
            elif 1<=hour<4 and not data.get("motion",{}).get("pir",0): set_led(color="white",brightness=30)
            elif lux>500: set_led(color="off",brightness=0)
            else:
                b=max(60,min(255,int(255-(lux/500.0)*195)))
                set_led(color="white",brightness=b)
        except Exception as e:
            log_event("BRAIN","LED error:"+str(e),"ERROR")
        time.sleep(3)

def drunk_driving_monitor():
    history,last_alert={},{}
    while True:
        try:
            tracks=get_detection().get("tracks",[])
            for t in tracks:
                tid=t.get("id")
                xc=t.get("x",0)+t.get("w",0)/2
                vc=t.get("class","car")
                if tid not in history: history[tid]=[]
                history[tid].append(xc)
                if len(history[tid])>DRUNK_SWERVE_WINDOW: history[tid].pop(0)
                if len(history[tid])<DRUNK_SWERVE_WINDOW: continue
                sc=sum(1 for i in range(2,len(history[tid]))
                    if (history[tid][i-1]-history[tid][i-2])*(history[tid][i]-history[tid][i-1])<0
                    and abs(history[tid][i]-history[tid][i-1])>DRUNK_SWERVE_THRESHOLD_PX)
                if sc>=DRUNK_SWERVE_COUNT and time.time()-last_alert.get(tid,0)>120:
                    last_alert[tid]=time.time()
                    on_drunk_driving(vc,tid,min(1.0,sc/DRUNK_SWERVE_WINDOW))
            active={t.get("id") for t in tracks}
            for tid in list(history):
                if tid not in active: del history[tid]
        except Exception as e:
            log_event("BRAIN","Drunk monitor error:"+str(e),"ERROR")
        time.sleep(0.1)

def speed_violation_monitor():
    last=0
    while True:
        try:
            from traffic_monitor import get_traffic
            spd=get_traffic().get("speed",0)
            if spd>SPEED_LIMIT_KMPH and time.time()-last>30:
                last=time.time()
                log_event("BRAIN","SPEED VIOLATION:"+str(round(spd,1)))
                on_speed_violation(spd,get_latest_frame())
        except Exception as e:
            log_event("BRAIN","Speed monitor error:"+str(e),"ERROR")
        time.sleep(2)

def vibration_monitor():
    last=0
    while True:
        try:
            alr=get_latest().get("alr",0)
            if alr&0x02 and time.time()-last>60:
                det=get_detection()
                if det.get("accident") or det.get("confidence",0)>0.4:
                    last=time.time()
                    frame=get_latest_frame()
                    evidence=save_evidence(frame,"vibration") if frame is not None else None
                    on_accident(det.get("confidence",0.6),evidence,frame)
        except Exception as e:
            log_event("BRAIN","Vibration error:"+str(e),"ERROR")
        time.sleep(1)

def main():
    log_event("BRAIN","MargRaksha V2 Starting")
    firebase_db=init_firebase()
    if firebase_db:
        set_firebase(firebase_db)
        try: push_test_data()
        except: pass
    init_twilio()
    start_uart()
    start_camera()
    yolo_engine.on_accident_detected=on_accident
    yolo_engine.on_helmet_violation=on_helmet
    start_yolo()
    start_env(firebase_db)
    start_traffic(firebase_db)
    start_crime(firebase_db)
    start_health(firebase_db)
    start_dashboard()
    for name,target in [
        ("SOS Monitor",sos_monitor),
        ("Adaptive LED",adaptive_led),
        ("Drunk Driving",drunk_driving_monitor),
        ("Speed Monitor",speed_violation_monitor),
        ("Vibration",vibration_monitor)]:
        threading.Thread(target=target,daemon=True,name=name).start()
        log_event("BRAIN","Thread started:"+name)
    speak("MargRaksha online. All systems operational.")
    log_event("BRAIN","Dashboard at http://10.42.0.1:8080")
    while True:
        time.sleep(10)
        log_event("BRAIN","Heartbeat|"+datetime.now().strftime("%H:%M:%S")+"|Sensor:"+( "OK" if is_sensor_alive() else "OFFLINE"))

if __name__=="__main__":
    main()
