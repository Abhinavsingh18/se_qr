from datetime import datetime

def referral_document(medical_id, center_id, referral_code, patient):
    return {
        "medicalId": medical_id,
        "centerId": center_id,
        "referralCode": referral_code,
        "patientName": patient.get("name"),
        "patientPhone": patient.get("phone"),
        "patientAge": patient.get("age"),
        "patientNotes": patient.get("notes"),
        "createdAt": datetime.utcnow()
    }
