from flask import Flask, render_template, request, redirect, url_for
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import qrcode
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
mongo = PyMongo(app)

# QR_FOLDER = "static/qr_codes"
# os.makedirs(QR_FOLDER, exist_ok=True)

HOST_URL = os.getenv("HOST_URL")

# ----------------- Home -----------------
@app.route("/")
def index():
    return render_template("index.html")

# ----------------- Centers -----------------
@app.route("/add-center", methods=["GET", "POST"])
def add_center():
    if request.method == "POST":
        name = request.form.get("name")
        address = request.form.get("address")
        mongo.db.centers.insert_one({"name": name, "address": address})
        return redirect(url_for("centers"))
    return render_template("add_center.html")

@app.route("/centers")
def centers():
    centers = list(mongo.db.centers.find())
    return render_template("centers.html", centers=centers)

# ----------------- Medicals -----------------
@app.route("/add-medical", methods=["GET", "POST"])
def add_medical():
    centers = list(mongo.db.centers.find())
    if request.method == "POST":
        name = request.form.get("name")
        center_id_str = request.form.get("center_id")
        center_id = ObjectId(center_id_str) if center_id_str else None
        
        medical_id = mongo.db.medicals.insert_one({
            "name": name,
            "center_id": center_id
        }).inserted_id
        
        qr_data = f"{HOST_URL}/register/{medical_id}"
        qr_img = qrcode.make(qr_data)
        qr_file = f"{QR_FOLDER}/{medical_id}.png"
        qr_img.save(qr_file)
        
        mongo.db.medicals.update_one({"_id": medical_id}, {"$set": {"qr_code": qr_file}})
        
        return redirect(url_for("medicals"))
    
    return render_template("add_medical.html", centers=centers)

@app.route("/medicals")
def medicals():
    medicals = list(mongo.db.medicals.find())
    for m in medicals:
        center_name = "Unknown"
        if "center_id" in m and m["center_id"]:
            center = mongo.db.centers.find_one({"_id": m["center_id"]})
            center_name = center["name"] if center else "Unknown"
        m["center_name"] = center_name
    return render_template("medicals.html", medicals=medicals)

# ----------------- Patient Registration -----------------
@app.route("/register/<medical_id>", methods=["GET", "POST"])
def register_patient(medical_id):
    medical = mongo.db.medicals.find_one({"_id": ObjectId(medical_id)})
    if not medical:
        return "Invalid QR code"
    
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        mongo.db.patients.insert_one({
            "name": name,
            "phone": phone,
            "medical_id": medical["_id"],
            "center_id": medical.get("center_id")
        })
        return "Registration Successful!"
    
    return render_template("patient_register.html", medical=medical)

# ----------------- Run -----------------
if __name__ == "__main__":
    app.run(host=os.getenv("FLASK_HOST"), port=int(os.getenv("FLASK_PORT")), debug=True)
