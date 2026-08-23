import firebase_admin
from firebase_admin import db
from config import TEST_PLATE, LAMP_ID
from event_logger import log_event

def get_vehicle_data(plate):
    """
    Fetch medical + owner data for a vehicle plate from Firebase.
    Returns dict or None if not found.
    """
    try:
        ref  = db.reference(f"arogya_vault/{plate}")
        data = ref.get()
        if data:
            log_event("AROGYA", f"Data found for plate: {plate}")
            return data
        else:
            log_event("AROGYA", f"No data for plate: {plate}", "WARNING")
            return None
    except Exception as e:
        log_event("AROGYA", f"Firebase fetch error: {e}", "ERROR")
        return None

def push_test_data():
    """Populate Firebase with dummy data for test plate TN01AB1234."""
    try:
        ref = db.reference(f"arogya_vault/{TEST_PLATE}")
        ref.set({
            "owner": {
                "name":       "Ravi Kumar",
                "age":        42,
                "blood_group": "O+",
                "allergies":  ["Penicillin"],
                "conditions": ["Hypertension", "Diabetes"],
                "medications": ["Metformin", "Amlodipine"],
                "emergency_contacts": [
                    {"name": "Priya Kumar",
                     "relation": "Wife",
                     "phone": "+919876543210"}
                ],
                "doctor": {
                    "name":  "Dr. Mehta",
                    "phone": "+919123456789"
                },
                "hospital_preference": "Apollo Chennai",
                "insurance": {
                    "provider": "Star Health",
                    "policy":   "SH-2024-XXXX"
                }
            },
            "family": [
                {
                    "name":        "Priya Kumar",
                    "relation":    "Wife",
                    "blood_group": "A+",
                    "allergies":   [],
                    "conditions":  [],
                    "medications": []
                }
            ]
        })
        log_event("AROGYA", f"Test data pushed for {TEST_PLATE}")
    except Exception as e:
        log_event("AROGYA", f"Test data push failed: {e}", "ERROR")

def format_for_sms(data):
    """Format Arogya Vault data into a short SMS string for hospital."""
    if not data:
        return "No medical data available."
    owner = data.get("owner", {})
    return (
        f"ACCIDENT VICTIM | {owner.get('name','Unknown')} "
        f"Age:{owner.get('age','?')} "
        f"Blood:{owner.get('blood_group','?')} "
        f"Conditions:{','.join(owner.get('conditions',[]))} "
        f"Allergies:{','.join(owner.get('allergies',[]))} "
        f"Emergency:{owner.get('emergency_contacts',[{}])[0].get('phone','?')}"
    )
