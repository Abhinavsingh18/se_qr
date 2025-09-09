import os, secrets
from flask import Blueprint, request, jsonify
from models.center import center_document
from models.medical import medical_document
import qrcode

admin_bp = Blueprint("admin", __name__)

def generate_referral_code():
    return secrets.token_urlsafe(4)[:8]

@admin_bp.route("/centers", methods=["POST"])
def create_center():
    data = request.json
    name = data.get("name")
    if not name:
        return jsonify({"error": "name required"}), 400
    doc = center_document(name, data.get("address",""), data.get("phone",""))
    res = admin_bp.db.centers.insert_one(doc)
    return jsonify({"_id": str(res.inserted_id), **doc})

@admin_bp.route("/medicals", methods=["POST"])
def create_medical():
    data = request.json
    name, center_id = data.get("name"), data.get("centerId")
    if not name or not center_id:
        return jsonify({"error": "name & centerId required"}), 400
    code = generate_referral_code()
    doc = medical_document(name, center_id, code)
    res = admin_bp.db.medicals.insert_one(doc)

    # Generate QR
    host = os.environ.get("HOST_URL","http://localhost:5000")
    qr_url = f"{host}/referral/{code}"
    qr = qrcode.make(qr_url)
    path = f"static/qrcodes/{code}.png"
    qr.save(path)

    return jsonify({"_id": str(res.inserted_id), **doc, "qrPath": path})
