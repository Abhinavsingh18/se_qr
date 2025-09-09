from datetime import datetime

def medical_document(name, center_id, referral_code):
    return {
        "name": name,
        "address": "",
        "phone": "",
        "assignedCenter": center_id,
        "referralCode": referral_code,
        "createdAt": datetime.utcnow()
    }
