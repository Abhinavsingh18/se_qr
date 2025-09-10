import os
import io
import qrcode
import base64
from datetime import datetime, timedelta
from bson import ObjectId
from flask import Flask, request, redirect, url_for, flash, render_template_string, session
from pymongo import MongoClient
from dotenv import load_dotenv

# ##############################################################################
# ## 1. HTML TEMPLATES AS PYTHON STRINGS
# ##############################################################################

# === STYLES AND LAYOUTS ===

# This new CSS block defines the entire blue color scheme.
UI_STYLES = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
    :root {
        --primary-blue: #0d6efd;
        --dark-blue: #0a2e5c;
        --light-blue: #e6f2ff;
        --page-bg: #f8f9fa;
        --card-bg: #ffffff;
        --text-dark: #212529;
        --text-light: #f8f9fa;
        --border-color: #dee2e6;
    }
    body {
        background-color: var(--page-bg);
        font-family: 'Poppins', sans-serif;
        color: var(--text-dark);
    }
    .navbar-custom {
        background-color: var(--dark-blue);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .card {
        border: 1px solid var(--border-color);
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        border-radius: 0.5rem;
    }
    .card-header {
        background-color: var(--light-blue);
        border-bottom: 1px solid var(--border-color);
        font-weight: 600;
        color: var(--dark-blue);
    }
    .btn-primary {
        background-color: var(--primary-blue);
        border: none;
    }
    .btn-info {
        background-color: #0dcaf0;
        border: none;
    }
    .form-control, .form-select {
        border: 1px solid var(--border-color);
    }
    .form-control:focus, .form-select:focus {
        border-color: var(--primary-blue);
        box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
    }
    .nav-tabs .nav-link {
        color: var(--primary-blue);
    }
    .nav-tabs .nav-link.active {
        color: var(--dark-blue);
        background-color: var(--card-bg);
        border-color: var(--border-color) var(--border-color) var(--card-bg);
        font-weight: 600;
    }
    .list-group-item {
        background-color: var(--card-bg);
    }
    .patient-list li {
        padding: 0.5rem;
        border-bottom: 1px solid var(--light-blue);
    }
    .patient-list li:last-child {
        border-bottom: none;
    }
</style>
"""

# Base layout for all ADMIN pages
ADMIN_LAYOUT_TEMPLATE = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{{{ title }}}} - QR Medical System</title>
    {UI_STYLES}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark navbar-custom mb-4">
        <div class="container">
            <a class="navbar-brand" href="{{{{ url_for('admin_dashboard') if session.get('logged_in') else url_for('login') }}}}">
                <strong>QR MedReg</strong> Admin
            </a>
            {{% if session.get('logged_in') %}}
            <a href="{{{{ url_for('logout') }}}}" class="btn btn-outline-light">Logout</a>
            {{% endif %}}
        </div>
    </nav>
    <main class="container">
        {{% with messages = get_flashed_messages(with_categories=true) %}}
            {{% if messages %}}
                {{% for category, message in messages %}}
                    <div class="alert alert-{{{{ category }}}} alert-dismissible fade show" role="alert">
                        {{{{ message }}}}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {{% endfor %}}
            {{% endif %}}
        {{% endwith %}}
        {{{{ content | safe }}}}
    </main>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# === ADMIN PAGE TEMPLATES ===

LOGIN_TEMPLATE = """
<div class="row justify-content-center mt-5">
    <div class="col-md-5">
        <div class="card">
            <div class="card-header text-center">
                <h4>Admin Login</h4>
            </div>
            <div class="card-body p-4">
                <form method="POST">
                    <div class="mb-3">
                        <label for="username" class="form-label">Username</label>
                        <input type="text" class="form-control" id="username" name="username" required>
                    </div>
                    <div class="mb-3">
                        <label for="password" class="form-label">Password</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100 mt-3">Login</button>
                </form>
            </div>
        </div>
    </div>
</div>
"""

ADMIN_TEMPLATE = """
<div class="row g-4">
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header">
                <ul class="nav nav-tabs card-header-tabs" id="formTabs" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="add-center-tab" data-bs-toggle="tab" data-bs-target="#add-center" type="button" role="tab">Add Center</button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="add-medical-tab" data-bs-toggle="tab" data-bs-target="#add-medical" type="button" role="tab">Add Medical</button>
                    </li>
                </ul>
            </div>
            <div class="card-body tab-content" id="formTabsContent">
                <div class="tab-pane fade show active p-2" id="add-center" role="tabpanel">
                    <form action="{{ url_for('add_center') }}" method="POST">
                        <div class="mb-3"><label for="center-name" class="form-label">Center Name</label><input type="text" class="form-control" id="center-name" name="name" required></div>
                        <div class="mb-3"><label for="center-address" class="form-label">Address</label><input type="text" class="form-control" id="center-address" name="address" required></div>
                        <button type="submit" class="btn btn-primary w-100">Save Center</button>
                    </form>
                </div>
                <div class="tab-pane fade p-2" id="add-medical" role="tabpanel">
                    <form action="{{ url_for('add_medical') }}" method="POST">
                        <div class="mb-3"><label for="medical-name" class="form-label">Medical's Name</label><input type="text" class="form-control" id="medical-name" name="name" required></div>
                        <div class="mb-3"><label for="center-select" class="form-label">Assign to Center</label>
                            <select class="form-select" id="center-select" name="center_id" required>
                                <option value="" disabled selected>Select a center...</option>
                                {% for center in centers %}<option value="{{ center._id }}">{{ center.name }}</option>{% endfor %}
                            </select>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Save Medical & Gen QR</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <div class="col-lg-8">
        <h4>System Overview</h4>
        <div class="card mb-4">
            <div class="card-body">
                <form method="GET" action="{{ url_for('admin_dashboard') }}" class="d-flex flex-wrap align-items-end gap-2">
                    <div class="flex-grow-1"><label for="filter_date" class="form-label">Show Registrations For:</label><input type="date" name="filter_date" id="filter_date" class="form-control" value="{{ filter_date }}"></div>
                    <button type="submit" class="btn btn-info text-white">Apply Filter</button>
                    <a href="{{ url_for('admin_dashboard') }}" class="btn btn-secondary">Today</a>
                </form>
            </div>
        </div>

        {% for center in centers_with_medicals %}
        <div class="card mb-3">
            <div class="card-header">{{ center.name }} <small class="text-muted fw-normal">({{ center.address }})</small></div>
            <div class="list-group list-group-flush">
                {% if center.medicals %}
                    {% for medical in center.medicals %}
                    <div class="list-group-item">
                        <div class="d-flex w-100 justify-content-between align-items-center">
                            <div>
                                <h6 class="mb-1">{{ medical.name }}</h6>
                                <span class="badge bg-primary rounded-pill">{{ medical.patients | length }} Registrations on {{ filter_date }}</span>
                            </div>
                            <button type="button" class="btn btn-outline-primary btn-sm" data-bs-toggle="modal" data-bs-target="#qrModal-{{ medical._id }}">Show QR</button>
                        </div>
                        {% if medical.patients %}
                        <div class="mt-3 patient-list">
                            <ul class="list-unstyled">
                                {% for patient in medical.patients %}
                                <li><strong>{{ patient.name }}</strong> ({{ patient.phone }}) <br><small class="text-muted">Ultrasound: {{ patient.ultrasound_name or 'N/A' }}</small></li>
                                {% endfor %}
                            </ul>
                        </div>
                        {% endif %}
                    </div>
                    <div class="modal fade" id="qrModal-{{ medical._id }}" tabindex="-1">
                        <div class="modal-dialog modal-dialog-centered">
                            <div class="modal-content"><div class="modal-header"><h5 class="modal-title">QR Code for {{ medical.name }}</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                                <div class="modal-body text-center">
                                    <img src="data:image/png;base64,{{ medical.qr_code }}" alt="QR Code" class="img-fluid">
                                    <p class="mt-2 text-muted">Scan to register</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="list-group-item"><p class="text-muted mb-0">No medical staff assigned to this center.</p></div>
                {% endif %}
            </div>
        </div>
        {% else %}
            <p>No centers found. Please add a center to begin.</p>
        {% endfor %}
    </div>
</div>
"""

# === PATIENT FACING TEMPLATES ===

REGISTER_TEMPLATE = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Patient Registration</title>
    {UI_STYLES}
    <style>body {{ padding-top: 2rem; }}</style>
</head>
<body>
<main class="container">
    {{% with messages = get_flashed_messages(with_categories=true) %}}
        {{% if messages %}}
            <div class="row justify-content-center"><div class="col-md-6">
                {{% for category, message in messages %}}
                    <div class="alert alert-{{{{ category }}}}">{{{{ message }}}}</div>
                {{% endfor %}}
            </div></div>
        {{% endif %}}
    {{% endwith %}}
    <div class="row justify-content-center"><div class="col-md-6">
        <div class="card">
            <div class="card-header text-center"><h3>Patient Registration</h3></div>
            <div class="card-body p-4">
                <p class="text-center">You are registering with <strong>{{{{ medical.name }}}}</strong> at <strong>{{{{ center.name }}}}</strong>.</p>
                <form method="POST" class="needs-validation" novalidate>
                    <div class="mb-3"><label for="name" class="form-label">Full Name</label><input type="text" class="form-control" id="name" name="name" required>
                        <div class="invalid-feedback">Please enter your name.</div></div>
                    <div class="mb-3"><label for="phone" class="form-label">Phone Number</label><input type="tel" class="form-control" id="phone" name="phone" required minlength="10" maxlength="12" pattern="[0-9]{{10,12}}">
                        <div class="invalid-feedback">Please enter a valid 10 to 12 digit phone number.</div></div>
                    <div class="mb-3"><label for="ultrasound_name" class="form-label">Ultrasound Name</label><input type="text" class="form-control" id="ultrasound_name" name="ultrasound_name" required>
                        <div class="invalid-feedback">Please enter the ultrasound name.</div></div>
                    <button type="submit" class="btn btn-primary w-100 mt-3">Submit Registration</button>
                </form>
            </div>
        </div>
    </div></div>
</main>
<script>
    (() => {{ 'use strict'; const forms = document.querySelectorAll('.needs-validation'); Array.from(forms).forEach(form => {{ form.addEventListener('submit', event => {{ if (!form.checkValidity()) {{ event.preventDefault(); event.stopPropagation(); }} form.classList.add('was-validated'); }}, false); }}); }})();
</script>
</body></html>
"""

SUCCESS_TEMPLATE = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Success</title>
    {UI_STYLES}
    <style>body {{ display: flex; align-items: center; justify-content: center; height: 100vh; text-align: center;}}</style>
</head>
<body>
    <div>
        <h1 class="display-4" style="color: var(--primary-blue);">Registration Successful!</h1>
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
    content = render_template_string(content_template, **context)
    return render_template_string(ADMIN_LAYOUT_TEMPLATE, title=title, content=content)

# ##############################################################################
# ## 4. FLASK ROUTES
# ##############################################################################

@app.route('/')
def index():
    if 'logged_in' in session: return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

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

@app.route('/admin')
def admin_dashboard():
    if 'logged_in' not in session: return redirect(url_for('login'))
    
    filter_date_str = request.args.get('filter_date', datetime.now().strftime('%Y-%m-%d'))
    try:
        start_of_day = datetime.strptime(filter_date_str, '%Y-%m-%d')
    except ValueError:
        flash("Invalid date format. Showing today's results.", "warning")
        filter_date_str = datetime.now().strftime('%Y-%m-%d')
        start_of_day = datetime.strptime(filter_date_str, '%Y-%m-%d')
    end_of_day = start_of_day + timedelta(days=1)

    all_centers = list(centers_collection.find({}, sort=[('name', 1)]))
    
    pipeline = [
        {"$sort": {"name": 1}},
        {"$lookup": {"from": "medicals", "localField": "_id", "foreignField": "center_id", "as": "medicals"}},
        {"$unwind": {"path": "$medicals", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "patients", "let": {"medical_id": "$medicals._id"},
                "pipeline": [
                    {"$match": {
                        "$expr": {"$eq": ["$medical_id", "$$medical_id"]},
                        "timestamp": {"$gte": start_of_day, "$lt": end_of_day}
                    }},
                    {"$sort": {"timestamp": -1}}
                ], "as": "medicals.patients"
            }
        },
        {"$group": {
            "_id": "$medicals._id", "center_id": {"$first": "$_id"}, "center_name": {"$first": "$name"},
            "center_address": {"$first": "$address"}, "medical_name": {"$first": "$medicals.name"},
            "qr_code": {"$first": "$medicals.qr_code"}, "patients": {"$first": "$medicals.patients"}
        }},
        {"$group": {
            "_id": "$center_id", "name": {"$first": "$center_name"}, "address": {"$first": "$center_address"},
            "medicals": {"$push": {"_id": "$_id", "name": "$medical_name", "qr_code": "$qr_code", "patients": "$patients"}}
        }},
        {"$project": {
            "name": 1, "address": 1,
            "medicals": {"$filter": {"input": "$medicals", "as": "m", "cond": {"$ne": ["$$m._id", None]}}}
        }},
        {"$sort": {"name": 1}}
    ]
    centers_with_data = list(centers_collection.aggregate(pipeline))
    
    return render_admin_page("Admin Dashboard", ADMIN_TEMPLATE, centers=all_centers, centers_with_medicals=centers_with_data, filter_date=filter_date_str)

@app.route('/add-center', methods=['POST'])
def add_center():
    if 'logged_in' not in session: return redirect(url_for('login'))
    name, address = request.form.get('name'), request.form.get('address')
    if name and address:
        centers_collection.insert_one({'name': name, 'address': address})
        flash(f"Center '{name}' added successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/add-medical', methods=['POST'])
def add_medical():
    if 'logged_in' not in session: return redirect(url_for('login'))
    name, center_id_str = request.form.get('name'), request.form.get('center_id')
    if name and center_id_str:
        center_id = ObjectId(center_id_str)
        new_medical = medicals_collection.insert_one({'name': name, 'center_id': center_id, 'qr_code': ''})
        registration_url = f"{HOST_URL}/register/{new_medical.inserted_id}"
        qr_code_b64 = generate_qr_code_base64(registration_url)
        medicals_collection.update_one({'_id': new_medical.inserted_id}, {'$set': {'qr_code': qr_code_b64}})
        flash(f"Medical '{name}' added and QR code generated.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/register/<medical_id>', methods=['GET', 'POST'])
def register_patient(medical_id):
    try:
        medical_obj_id = ObjectId(medical_id)
        medical = medicals_collection.find_one({'_id': medical_obj_id})
        if not medical: return "<h2>Invalid registration link. Medical not found.</h2>", 404
        center = centers_collection.find_one({'_id': medical['center_id']})

        if request.method == 'POST':
            patient_name, patient_phone, ultrasound_name = request.form.get('name'), request.form.get('phone'), request.form.get('ultrasound_name')
            error = None
            if not all([patient_name, patient_phone, ultrasound_name]):
                error = "All fields are required."
            elif not patient_phone.isdigit() or not (10 <= len(patient_phone) <= 12):
                error = "Phone number must be 10 to 12 digits."
            
            if error:
                flash(error, "danger")
                return redirect(url_for('register_patient', medical_id=medical_id))

            patients_collection.insert_one({
                'name': patient_name, 'phone': patient_phone, 'ultrasound_name': ultrasound_name,
                'medical_id': medical_obj_id, 'center_id': medical['center_id'], 'timestamp': datetime.utcnow()
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
    app.run(host=os.getenv("FLASK_HOST", "0.0.0.0"), port=int(os.getenv("FLASK_PORT", 5000)), debug=True)