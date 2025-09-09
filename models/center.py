from datetime import datetime

def center_document(name, address="", phone=""):
    return {
        "name": name,
        "address": address,
        "phone": phone,
        "createdAt": datetime.utcnow()
    }
