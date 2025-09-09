import os
import io
import qrcode
import base64
from datetime import datetime
from bson import ObjectId
from flask import Flask, request, redirect, url_for, flash, render_template_string, session
from pymongo import MongoClient
from dotenv import load_dotenv

# ##############################################################################
# ## 1. HTML TEMPLATES AS PYTHON STRINGS
# ##############################################################################

# === ADMIN FACING TEMPLATES ===

# Base layout for all ADMIN pages (includes navbar)
ADMIN_LAYOUT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - QR Medical System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #212529; color: #dee2e6; }
        .card, .accordion-item { background-color: #343a40; border-color: #495057; }
        .table { --bs-table-bg: #343a40; --bs-table-striped-bg: #3e444a; --bs-table-color: #dee2e6; border-color: #495057;}
        .accordion-button { background-color: #3e444a; color: #fff; }
        .accordion-button:not(.collapsed) { background-color: #0d6efd; }
        .accordion-button:focus { box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.5); }
        .form-control { background-color: #495057; border-color: #6c757d; color: #fff; }
        .form-control:focus { background-color: #495057; border-color: #0d6efd; color: #fff; }
        .form-select { background-color: #495057; border-color: #6c757d; color: #fff; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-4">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('admin_dashboard') if session.get('logged_in') else url_for('login') }}">QR MedReg Admin</a>
            {% if session.get('logged_in') %}
            <a href="{{ url_for('logout') }}" class="btn btn-danger">Logout</a>
            {% endif %}
        </div>
    </nav>
    <main class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {{ content | safe }}
    </main>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# Admin Login Page Template
LOGIN_TEMPLATE = """
<div class="row justify-content-center">
    <div class="col-md-5">
        <div class="card">
            <div class="card-header text-center">
                <h4>Admin Login</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="username" class="form-label">Username</label>
                        <input type="text" class="form-control" id="username" name="username" required>
                    </div>
                    <div class="mb-3">
                        <label for="password" class="form-label">Password</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Login</button>
                </form>
            </div>
        </div>
    </div>
</div>
"""

# Admin dashboard template
ADMIN_TEMPLATE = """
<div class="row">
    <div class="col-lg-4 mb-4">
        <div class="card mb-4">
            <div class="card-header"><h4>Add New Center</h4></div>
            <div class="card-body">
                <form action="{{ url_for('add_center') }}" method="POST">
                    <div class="mb-3">
                        <label for="center-name" class="form-label">Center Name</label>
                        <input type="text" class="form-control" id="center-name" name="name" required>
                    </div>
                    <div class="mb-3">
                        <label for="center-address" class="form-label">Address</label>
                        <input type="text" class="form-control" id="center-address" name="address" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Add Center</button>
                </form>
            </div>
        </div>

        <div class="card">
            <div class="card-header"><h4>Add New Medical Staff</h4></div>
            <div class="card-body">
                <form action="{{ url_for('add_medical') }}" method="POST">
                    <div class="mb-3">
                        <label for="medical-name" class="form-label">Medical's Name</label>
                        <input type="text" class="form-control" id="medical-name" name="name" required>
                    </div>
                    <div class="mb-3">
                        <label for="center-select" class="form-label">Assign to Center</label>
                        <select class="form-select" id="center-select" name="center_id" required>
                            <option value="" disabled selected>Select a center...</option>
                            {% for center in centers %}
                            <option value="{{ center._id }}">{{ center.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <button type="submit" class="btn btn-success w-100">Add Medical & Generate QR</button>
                </form>
            </div>
        </div>
    </div>

    <div class="col-lg-8">
        <h2>System Overview</h2>
        <div class="accordion" id="centersAccordion">
            {% for center in centers_with_medicals %}
            <div class="accordion-item">
                <h2 class="accordion-header" id="heading-{{ center._id }}">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-{{ center._id }}">
                        <strong>{{ center.name }}</strong>&nbsp; ({{ center.address }})
                    </button>
                </h2>
                <div id="collapse-{{ center._id }}" class="accordion-collapse collapse" data-bs-parent="#centersAccordion">
                    <div class="accordion-body">
                        <h5>Medical Staff at this Center</h5>
                        {% if center.medicals %}
                            <table class="table table-hover">
                                <thead>
                                    <tr><th>Name</th><th>QR Code</th><th>Registrations</th></tr>
                                </thead>
                                <tbody>
                                {% for medical in center.medicals %}
                                <tr>
                                    <td>{{ medical.name }}</td>
                                    <td>
                                        {% if medical.qr_code %}
                                        <img src="data:image/png;base64,{{ medical.qr_code }}" alt="QR" width="100">
                                        {% endif %}
                                    </td>
                                    <td>
                                        <span class="badge bg-info rounded-pill">{{ medical.patients | length }}</span>
                                        {% if medical.patients %}
                                        <ul class="list-unstyled mt-2">
                                            {% for patient in medical.patients %}
                                            <li class="mb-2">
                                                {{ patient.name }} ({{ patient.phone }})
                                                <br>
                                                <small class="text-white-50">Ultrasound: {{ patient.ultrasound_name or 'N/A' }}</small>
                                            </li>
                                            {% endfor %}
                                        </ul>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                                </tbody>
                            </table>
                        {% else %}
                        <p class="text-muted">No medical staff assigned to this center yet.</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% else %}
            <p>No centers found. Please add a center to begin.</p>
            {% endfor %}
        </div>
    </div>
</div>
"""

# === PATIENT FACING TEMPLATES (No Navbar) ===

# Patient registration form template (Full page, no layout)
REGISTER_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Patient Registration</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #212529; color: #dee2e6; padding-top: 2rem; }
        .card { background-color: #343a40; border-color: #495057; }
        .form-control { background-color: #495057; border-color: #6c757d; color: #fff; }
        .form-control:focus { background-color: #495057; border-color: #0d6efd; color: #fff; }
    </style>
</head>
<body>
<main class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="row justify-content-center">
                <div class="col-md-6">
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            </div>
        {% endif %}
    {% endwith %}
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header text-center">
                    <h3>Patient Registration</h3>
                </div>
                <div class="card-body">
                    <p class="text-center">You are registering with <strong>{{ medical.name }}</strong> at <strong>{{ center.name }}</strong>.</p>
                    <form method="POST" class="needs-validation" novalidate>
                        <div class="mb-3">
                            <label for="name" class="form-label">Full Name</label>
                            <input type="text" class="form-control" id="name" name="name" required>
                            <div class="invalid-feedback">Please enter your name.</div>
                        </div>
                        <div class="mb-3">
                            <label for="phone" class="form-label">Phone Number</label>
                            <input type="tel" class="form-control" id="phone" name="phone" required minlength="10" maxlength="12" pattern="[0-9]{10,12}">
                            <div class="invalid-feedback">Please enter a valid 10 to 12 digit phone number.</div>
                        </div>
                        <div class="mb-3">
                            <label for="ultrasound_name" class="form-label">Ultrasound Name</label>
                            <input type="text" class="form-control" id="ultrasound_name" name="ultrasound_name" required>
                            <div class="invalid-feedback">Please enter the ultrasound name.</div>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Submit Registration</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
</main>
<script>
    (() => {
        'use strict'
        const forms = document.querySelectorAll('.needs-validation')
        Array.from(forms).forEach(form => {
            form.addEventListener('submit', event => {
                if (!form.checkValidity()) {
                    event.preventDefault()
                    event.stopPropagation()
                }
                form.classList.add('was-validated')
            }, false)
        })
    })()
</script>
</body>
</html>
"""

# Success message template (Full page, no layout)
SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Success</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #212529; color: #dee2e6; display: flex; align-items: center; justify-content: center; height: 100vh; }
    </style>
</head>
<body>
    <div class="text-center py-5">
        <h1 class="display-4 text-success">Registration Successful!</h1>
        <p class="lead">Thank you. Your information has been submitted.</p>
    </div>
</body>
</html>
"""

# ##############################################################################
# ## 2. APPLICATION SETUP AND CONFIGURATION
# ##############################################################################

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_KEY")

MONGO_URI = os.getenv("MONGO_URI")
HOST_URL = os.getenv("HOST_URL")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

client = MongoClient(MONGO_URI)
db = client.get_database()
centers_collection = db.centers
medicals_collection = db.medicals
patients_collection = db.patients

# ##############################################################################
# ## 3. HELPER FUNCTIONS
# ##############################################################################

def generate_qr_code_base64(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def render_admin_page(title, content_template, **context):
    """Renders an ADMIN page by injecting content into the admin layout."""
    content = render_template_string(content_template, **context)
    return render_template_string(ADMIN_LAYOUT_TEMPLATE, title=title, content=content)

# ##############################################################################
# ## 4. FLASK ROUTES
# ##############################################################################

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

# --- AUTHENTICATION ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
    return render_admin_page("Admin Login", LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out.', 'info')
    return redirect(url_for('login'))

# --- ADMIN ROUTES ---

@app.route('/admin')
def admin_dashboard():
    if 'logged_in' not in session: return redirect(url_for('login'))
    all_centers = list(centers_collection.find({}, sort=[('name', 1)]))
    pipeline = [
        {"$sort": {"name": 1}},
        {"$lookup": {"from": "medicals", "localField": "_id", "foreignField": "center_id", "as": "medicals"}},
        {"$unwind": {"path": "$medicals", "preserveNullAndEmptyArrays": True}},
        {"$lookup": {"from": "patients", "localField": "medicals._id", "foreignField": "medical_id", "as": "medicals.patients"}},
        {"$unwind": {"path": "$medicals.patients", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"medicals.patients.timestamp": -1}},
        {"$group": {
            "_id": "$medicals._id", "center_id": {"$first": "$_id"}, "center_name": {"$first": "$name"},
            "center_address": {"$first": "$address"}, "medical_name": {"$first": "$medicals.name"},
            "qr_code": {"$first": "$medicals.qr_code"}, "patients": {"$push": "$medicals.patients"}
        }},
        {"$group": {
            "_id": "$center_id", "name": {"$first": "$center_name"}, "address": {"$first": "$center_address"},
            "medicals": {"$push": {
                "_id": "$_id", "name": "$medical_name", "qr_code": "$qr_code",
                "patients": {"$filter": {"input": "$patients", "as": "p", "cond": {"$ne": ["$$p", {}]}}}
            }}
        }},
        {"$project": {
            "name": 1, "address": 1,
            "medicals": {"$filter": {"input": "$medicals", "as": "m", "cond": {"$ne": ["$$m._id", None]}}}
        }},
        {"$sort": {"name": 1}}
    ]
    centers_with_data = list(centers_collection.aggregate(pipeline))
    return render_admin_page("Admin Dashboard", ADMIN_TEMPLATE, centers=all_centers, centers_with_medicals=centers_with_data)

@app.route('/add-center', methods=['POST'])
def add_center():
    if 'logged_in' not in session: return redirect(url_for('login'))
    name = request.form.get('name')
    address = request.form.get('address')
    if name and address:
        centers_collection.insert_one({'name': name, 'address': address})
        flash(f"Center '{name}' added successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/add-medical', methods=['POST'])
def add_medical():
    if 'logged_in' not in session: return redirect(url_for('login'))
    name = request.form.get('name')
    center_id_str = request.form.get('center_id')
    if name and center_id_str:
        center_id = ObjectId(center_id_str)
        new_medical = medicals_collection.insert_one({'name': name, 'center_id': center_id, 'qr_code': ''})
        registration_url = f"{HOST_URL}/register/{new_medical.inserted_id}"
        qr_code_b64 = generate_qr_code_base64(registration_url)
        medicals_collection.update_one({'_id': new_medical.inserted_id}, {'$set': {'qr_code': qr_code_b64}})
        flash(f"Medical '{name}' added and QR code generated.", "success")
    return redirect(url_for('admin_dashboard'))

# --- PATIENT REGISTRATION ROUTES ---

@app.route('/register/<medical_id>', methods=['GET', 'POST'])
def register_patient(medical_id):
    try:
        medical_obj_id = ObjectId(medical_id)
        medical = medicals_collection.find_one({'_id': medical_obj_id})
        if not medical:
            return "<h2>Invalid registration link. Medical not found.</h2>", 404
        center = centers_collection.find_one({'_id': medical['center_id']})

        if request.method == 'POST':
            patient_name = request.form.get('name')
            patient_phone = request.form.get('phone')
            ultrasound_name = request.form.get('ultrasound_name')

            # --- Server-Side Validation ---
            error = None
            if not patient_name or not patient_phone or not ultrasound_name:
                error = "All fields are required."
            elif not patient_phone.isdigit() or not (10 <= len(patient_phone) <= 12):
                error = "Phone number must be 10 to 12 digits."
            
            if error:
                flash(error, "danger")
                return redirect(url_for('register_patient', medical_id=medical_id))

            patients_collection.insert_one({
                'name': patient_name, 'phone': patient_phone, 'ultrasound_name': ultrasound_name,
                'medical_id': medical_obj_id, 'center_id': medical['center_id'],
                'timestamp': datetime.utcnow()
            })
            return redirect(url_for('registration_success'))
            
        return render_template_string(REGISTER_TEMPLATE, medical=medical, center=center)
    except Exception:
        return "<h2>Invalid registration link format.</h2>", 400

@app.route('/success')
def registration_success():
    return render_template_string(SUCCESS_TEMPLATE)

# ##############################################################################
# ## 5. RUN THE APPLICATION
# ##############################################################################

if __name__ == '__main__':
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 5000)),
        debug=True
    )