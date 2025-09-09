from flask import Blueprint, request, jsonify, render_template
from models.referral import referral_document
from bson import ObjectId

public_bp = Blueprint("public", __name__)

@public_bp.route("/referral/<code>")
def referral_form(code):
    medical = public_bp.db.medicals.find_one({"referralCode": code})
    if not medical:
        return "Invalid referral code", 404
    center = public_bp.db.centers.find_one({"_id": ObjectId(medical["assignedCenter"])})
    return render_template("referral.html", medical=medical, center=center)

@public_bp.route("/referrals", methods=["POST"])
def submit_referral():
    data = request.json
    code = data.get("referralCode")
    medical = public_bp.db.medicals.find_one({"referralCode": code})
    if not medical:
        return jsonify({"error": "invalid code"}), 400
    center_id = medical["assignedCenter"]
    doc = referral_document(medical["_id"], center_id, code, data["patient"])
    res = public_bp.db.referrals.insert_one(doc)
    return jsonify({"_id": str(res.inserted_id), "status": "saved"})
