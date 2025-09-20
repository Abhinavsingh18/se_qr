import os
import io
import qrcode
import base64
import csv
from datetime import datetime, timedelta
from bson import ObjectId
from flask import Flask, request, redirect, url_for, flash, render_template_string, session, Response
from pymongo import MongoClient
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import cloudinary
import cloudinary.uploader

# ##############################################################################
# ## 1. HTML TEMPLATES AS PYTHON STRINGS
# ##############################################################################

# === STYLES AND LAYOUTS ===
UI_STYLES = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<style>
    :root { --primary-blue: #0d6efd; --dark-blue: #0a2e5c; --light-blue: #eef7ff; --page-bg: #f8f9fa; --card-bg: #ffffff; --text-dark: #212529; --text-light: #f8f9fa; --border-color: #dee2e6; --shadow: 0 4px 12px rgba(0,0,0,0.08); }
    body { background-color: var(--page-bg); font-family: 'Poppins', sans-serif; color: var(--text-dark); }
    .navbar-custom { background: linear-gradient(90deg, #0d6efd, #0a2e5c); box-shadow: var(--shadow); }
    .card { border: none; box-shadow: var(--shadow); border-radius: 0.75rem; }
    .card-header { background-color: var(--light-blue); border-bottom: 1px solid var(--border-color); font-weight: 600; color: var(--dark-blue); border-radius: 0.75rem 0.75rem 0 0 !important; }
    .btn { border-radius: 0.5rem; font-weight: 600; }
    .form-control, .form-select { border: 1px solid var(--border-color); border-radius: 0.5rem; }
    .form-control:focus, .form-select:focus { border-color: var(--primary-blue); box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25); }
    .patient-list li { padding: 0.75rem; border-bottom: 1px solid var(--light-blue); }
    .patient-list li:last-child { border-bottom: none; }
    .photo-thumbnail { width: 40px; height: 40px; object-fit: cover; border-radius: 0.25rem; margin-right: 5px; }
</style>
"""

ADMIN_LAYOUT_TEMPLATE = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{{ title }} - Samriddhi Enterprises</title>
""" + UI_STYLES + """
</head><body>
<nav class="navbar navbar-expand-lg navbar-dark navbar-custom mb-4">
    <div class="container">
        <a class="navbar-brand" href="{{ url_for('index') }}"><i class="fas fa-qrcode me-2"></i><strong>Samriddhi Enterprises</strong></a>
        <ul class="navbar-nav ms-auto mb-2 mb-lg-0">
            {% if session.get('logged_in') %}
                <li class="nav-item"><a class="nav-link" href="{{ url_for('admin_dashboard') }}"><i class="fas fa-user-shield me-1"></i>Admin Panel</a></li>
                <li class="nav-item"><a class="nav-link" href="{{ url_for('analytics_dashboard') }}"><i class="fas fa-chart-line me-1"></i>Analytics</a></li>
                <li class="nav-item"><a href="{{ url_for('logout') }}" class="btn btn-outline-light ms-2"><i class="fas fa-sign-out-alt me-1"></i>Logout</a></li>
            {% elif session.get('center_id') %}
                 <li class="nav-item"><a class="nav-link active" href="{{ url_for('center_dashboard') }}"><i class="fas fa-clinic-medical me-1"></i>Center Dashboard</a></li>
                 <li class="nav-item"><a href="{{ url_for('center_logout') }}" class="btn btn-outline-light ms-2"><i class="fas fa-sign-out-alt me-1"></i>Logout</a></li>
            {% else %}
                 <li class="nav-item"><a class="nav-link" href="{{ url_for('login') }}">Admin Login</a></li>
                 <li class="nav-item"><a class="nav-link" href="{{ url_for('center_login') }}">Center Login</a></li>
            {% endif %}
        </ul>
    </div>
</nav>
<main class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}{% for category, message in messages %}
        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
            {{ message }}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
        {% endfor %}{% endif %}
    {% endwith %}
    {{ content | safe }}
</main>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
"""

# === SUPER ADMIN TEMPLATES ===
LOGIN_TEMPLATE = """
<div class="row justify-content-center mt-5"><div class="col-md-5"><div class="card">
<div class="card-header text-center"><h4><i class="fas fa-user-shield me-2"></i>Super Admin Login</h4></div>
<div class="card-body p-4"><form method="POST">
    <div class="mb-3"><label class="form-label">Username</label><input type="text" name="username" class="form-control" required></div>
    <div class="mb-3"><label class="form-label">Password</label><input type="password" name="password" class="form-control" required></div>
    <button type="submit" class="btn btn-primary w-100 mt-3"><i class="fas fa-sign-in-alt me-2"></i>Login</button>
</form></div></div></div></div>
"""

ADMIN_TEMPLATE = """
<div class="row g-4">
    <div class="col-12"><div class="card"><div class="card-header"><i class="fas fa-hospital me-2"></i>Center Management</div>
    <div class="card-body">
        <h5 class="card-title">Create New Center</h5>
        <form action="{{ url_for('add_center') }}" method="POST" class="row g-3 align-items-end p-2 border rounded bg-light mb-4">
            <div class="col-md-3"><label class="form-label">Center Name</label><input type="text" name="name" class="form-control" required></div>
            <div class="col-md-3"><label class="form-label">Address</label><input type="text" name="address" class="form-control" required></div>
            <div class="col-md-2"><label class="form-label">Username</label><input type="text" name="username" class="form-control" required></div>
            <div class="col-md-2"><label class="form-label">Password</label><input type="password" name="password" class="form-control" required></div>
            <div class="col-md-2"><button type="submit" class="btn btn-primary w-100"><i class="fas fa-plus me-1"></i>Create</button></div>
        </form>
        <h5 class="card-title mt-4">Existing Centers</h5>
        <div class="table-responsive"><table class="table table-hover">
            <thead><tr><th>Name</th><th>Address</th><th>Username</th><th>Action</th></tr></thead>
            <tbody>
            {% for center in centers %}
            <tr>
                <td>{{ center.name }}</td><td>{{ center.address }}</td><td>{{ center.username or 'N/A' }}</td>
                <td><button class="btn btn-sm btn-outline-danger" data-bs-toggle="modal" data-bs-target="#resetPassModal-{{center._id}}"><i class="fas fa-key me-1"></i>Reset Password</button></td>
            </tr>
            <div class="modal fade" id="resetPassModal-{{center._id}}"><div class="modal-dialog"><div class="modal-content">
                <form action="{{ url_for('reset_center_password', center_id=center._id) }}" method="POST">
                    <div class="modal-header"><h5 class="modal-title">Reset Password for {{center.name}}</h5></div>
                    <div class="modal-body"><label class="form-label">New Password</label><input type="password" name="new_password" class="form-control" required></div>
                    <div class="modal-footer"><button type="submit" class="btn btn-danger">Confirm Reset</button></div>
                </form>
            </div></div></div>
            {% endfor %}
            </tbody>
        </table></div>
    </div></div></div>
    <div class="col-12"><h4 class="mt-4">System Overview</h4><div class="row">
        <div class="col-lg-4"><div class="card"><div class="card-header"><i class="fas fa-user-md me-2"></i>Add Medical Staff</div>
        <div class="card-body"><form action="{{ url_for('add_medical') }}" method="POST">
            <div class="mb-3"><label class="form-label">Medical's Name</label><input type="text" name="name" class="form-control" required></div>
            <div class="mb-3"><label class="form-label">Assign to Center</label>
                <select class="form-select" name="center_id" required>
                    <option value="" disabled selected>Select...</option>
                    {% for center in centers %}<option value="{{ center._id }}">{{ center.name }}</option>{% endfor %}
                </select>
            </div>
            <button type="submit" class="btn btn-primary w-100"><i class="fas fa-qrcode me-1"></i>Add & Gen QR</button>
        </form></div></div></div>
        <div class="col-lg-8">
            <div class="card mb-4"><div class="card-body">
                <form method="GET" action="{{ url_for('admin_dashboard') }}" class="row g-2 align-items-end">
                    <div class="col-sm-8"><label class="form-label">Registrations For:</label><input type="date" name="filter_date" class="form-control" value="{{ filter_date }}"></div>
                    <div class="col-sm-4"><button type="submit" class="btn btn-info text-white w-100"><i class="fas fa-filter me-1"></i>Apply</button></div>
                </form>
            </div></div>
            {% for center in centers_with_medicals %}
            <div class="card mb-3"><div class="card-header">{{ center.name }}</div>
            <div class="list-group list-group-flush">
                {% for medical in center.medicals %}
                <div class="list-group-item p-3">
                    <div class="row align-items-center">
                        <div class="col-8"><h6 class="mb-1">{{ medical.name }}</h6><span class="badge bg-primary rounded-pill">{{ medical.patients | length }} Registrations</span></div>
                        <div class="col-2 text-center"><img src="data:image/png;base64,{{ medical.qr_code }}" alt="QR" style="width: 60px; height: 60px;"></div>
                        <div class="col-2 text-end"><button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#patients-{{ medical._id }}"><i class="fas fa-users me-1"></i></button></div>
                    </div>
                    <div class="collapse mt-3" id="patients-{{ medical._id }}">
                        <ul class="list-unstyled patient-list border-top pt-2">
                            {% for patient in medical.patients %}
                            <li><strong>{{ patient.name }}</strong> ({{ patient.phone }})
                                {% set status_color = 'warning' if patient.status == 'Pending' else 'info' if patient.status == 'Running' else 'success' %}
                                <span class="badge bg-{{ status_color }} text-dark ms-2">{{ patient.status }}</span>
                                <br><small class="text-muted">Ultrasound: {{ patient.ultrasound_name or 'N/A' }}</small>
                                <div>
                                    {% if patient.get('photo_url_1') %}<a href="{{ patient.photo_url_1 }}" target="_blank"><img src="{{ patient.photo_url_1 }}" class="photo-thumbnail"></a>{% endif %}
                                    {% if patient.get('photo_url_2') %}<a href="{{ patient.photo_url_2 }}" target="_blank"><img src="{{ patient.photo_url_2 }}" class="photo-thumbnail"></a>{% endif %}
                                </div>
                            </li>
                            {% else %}<li><small class="text-muted">No registrations on this date.</small></li>{% endfor %}
                        </ul>
                    </div>
                </div>
                {% endfor %}
            </div></div>
            {% endfor %}
        </div>
    </div></div>
</div>
"""

ANALYTICS_TEMPLATE = """
<div class="row g-4">
    <div class="col-12"><h4 class="mb-3"><i class="fas fa-chart-line me-2"></i>Analytics Dashboard</h4></div>
    <div class="col-md-12"><div class="card"><div class="card-header">Daily Registrations (Last 30 Days)</div>
        <div class="card-body"><canvas id="dailyRegistrationsChart"></canvas></div>
    </div></div>
    <div class="col-md-6"><div class="card"><div class="card-header">Top 5 Performing Centers</div>
        <div class="card-body"><canvas id="topCentersChart"></canvas></div>
    </div></div>
    <div class="col-md-6"><div class="card"><div class="card-header">Top 5 Performing Medical Staff</div>
        <div class="card-body"><canvas id="topMedicalsChart"></canvas></div>
    </div></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
    const chartColors = ['#0d6efd', '#6c757d', '#198754', '#ffc107', '#0dcaf0'];
    new Chart(document.getElementById('dailyRegistrationsChart'), {
        type: 'line',
        data: { labels: {{ daily_stats.labels|tojson }}, datasets: [{ label: 'Registrations', data: {{ daily_stats.data|tojson }}, tension: 0.1, fill: false, borderColor: chartColors[0] }] },
        options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
    });
    new Chart(document.getElementById('topCentersChart'), {
        type: 'bar',
        data: { labels: {{ top_centers.labels|tojson }}, datasets: [{ label: 'Total Registrations', data: {{ top_centers.data|tojson }}, backgroundColor: chartColors }] },
        options: { indexAxis: 'y', scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } }
    });
    new Chart(document.getElementById('topMedicalsChart'), {
        type: 'bar',
        data: { labels: {{ top_medicals.labels|tojson }}, datasets: [{ label: 'Total Registrations', data: {{ top_medicals.data|tojson }}, backgroundColor: chartColors }] },
        options: { indexAxis: 'y', scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } }
    });
</script>
"""

# === CENTER ADMIN TEMPLATES ===
CENTER_LOGIN_TEMPLATE = """
<div class="row justify-content-center mt-5"><div class="col-md-5"><div class="card">
<div class="card-header text-center"><h4><i class="fas fa-clinic-medical me-2"></i>Center Portal Login</h4></div>
<div class="card-body p-4"><form method="POST">
    <div class="mb-3"><label class="form-label">Username</label><input type="text" name="username" class="form-control" required></div>
    <div class="mb-3"><label class="form-label">Password</label><input type="password" name="password" class="form-control" required></div>
    <button type="submit" class="btn btn-primary w-100 mt-3"><i class="fas fa-sign-in-alt me-2"></i>Login</button>
</form></div></div></div></div>
"""

CENTER_DASHBOARD_TEMPLATE = """
<h4 class="mb-3">Dashboard for {{ session['center_name'] }}</h4>
<div class="card mb-4"><div class="card-body">
    <form method="GET" action="{{ url_for('center_dashboard') }}" class="row g-2 align-items-end">
        <div class="col-sm-5"><label class="form-label">Search Name/Phone:</label><input type="text" name="search_query" class="form-control" value="{{ search_query or '' }}"></div>
        <div class="col-sm-5"><label class="form-label">Registrations For:</label><input type="date" name="filter_date" class="form-control" value="{{ filter_date }}"></div>
        <div class="col-sm-2"><button type="submit" class="btn btn-primary w-100"><i class="fas fa-search me-1"></i>Filter</button></div>
    </form>
</div></div>
<div class="card">
    <div class="card-header">Total Registrations on {{ filter_date }}: <span class="badge bg-primary rounded-pill fs-6">{{ patients|length }}</span></div>
    <div class="table-responsive">
        <table class="table table-hover mb-0 align-middle">
            <thead><tr><th>Patient</th><th>Photos</th><th>Status</th><th class="text-center">Action</th></tr></thead>
            <tbody>
            {% for p in patients %}
            <tr>
                <td><strong>{{ p.name }}</strong><br><small class="text-muted">{{ p.phone }} | {{ p.ultrasound_name }}</small></td>
                <td>
                    {% if p.get('photo_url_1') %}<a href="{{ p.photo_url_1 }}" target="_blank"><img src="{{ p.photo_url_1 }}" class="photo-thumbnail"></a>{% endif %}
                    {% if p.get('photo_url_2') %}<a href="{{ p.photo_url_2 }}" target="_blank"><img src="{{ p.photo_url_2 }}" class="photo-thumbnail"></a>{% endif %}
                </td>
                <td>
                    {% set status_color = 'warning' if p.status == 'Pending' else 'info' if p.status == 'Running' else 'success' %}
                    <span class="badge bg-{{ status_color }} text-dark">{{ p.status }}</span>
                </td>
                <td class="text-center">
                    {% if p.status != 'Complete' %}
                    <div class="btn-group btn-group-sm">
                    {% if p.status == 'Pending' %}
                        <form action="{{ url_for('update_patient_status', patient_id=p._id) }}" method="POST" class="d-inline">
                            <input type="hidden" name="new_status" value="Running"><button type="submit" class="btn btn-info text-white" title="Mark as Running"><i class="fas fa-play"></i></button>
                        </form>
                    {% endif %}
                        <form action="{{ url_for('update_patient_status', patient_id=p._id) }}" method="POST" class="d-inline">
                            <input type="hidden" name="new_status" value="Complete"><button type="submit" class="btn btn-success" title="Mark as Complete"><i class="fas fa-check"></i></button>
                        </form>
                    </div>
                    {% else %}<span class="text-success"><i class="fas fa-check-circle"></i> Done</span>{% endif %}
                </td>
            </tr>
            {% else %}
            <tr><td colspan="4" class="text-center text-muted p-4">No registrations found.</td></tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
</div>
"""

# === PATIENT TEMPLATES ===
REGISTER_TEMPLATE = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Patient Registration</title>
""" + UI_STYLES + """
<style>body{padding-top:2rem;}</style></head>
<body><main class="container"><div class="row justify-content-center"><div class="col-md-6"><div class="card">
    <div class="card-header text-center"><h3><i class="fas fa-user-plus me-2"></i>Patient Registration</h3></div>
    <div class="card-body p-4">
        <p class="text-center">Registering with <strong>{{ medical.name }}</strong> at <strong>{{ center.name }}</strong>.</p>
        <form method="POST" enctype="multipart/form-data" class="needs-validation" novalidate>
            <div class="mb-3"><label class="form-label">Full Name</label><input type="text" class="form-control" name="name" required></div>
            <div class="mb-3"><label class="form-label">Phone Number</label><input type="tel" class="form-control" name="phone" required minlength="10" maxlength="12" pattern="[0-9]{10,12}"></div>
            <div class="mb-3"><label class="form-label">Ultrasound Name</label><input type="text" class="form-control" name="ultrasound_name" required></div>
            <hr>
            <div class="mb-3"><label class="form-label">Upload Photo 1 (Optional)</label><input type="file" class="form-control" name="photo1" accept="image/*"></div>
            <div class="mb-3"><label class="form-label">Upload Photo 2 (Optional)</label><input type="file" class="form-control" name="photo2" accept="image/*"></div>
            <button type="submit" class="btn btn-primary w-100 mt-3">Submit Registration</button>
        </form>
    </div></div></div></div>
</main>
<script>
    (() => { 'use strict'; const forms = document.querySelectorAll('.needs-validation'); Array.from(forms).forEach(form => { form.addEventListener('submit', event => { if (!form.checkValidity()) { event.preventDefault(); event.stopPropagation(); } form.classList.add('was-validated'); }, false); }); })();
</script>
</body></html>
"""
SUCCESS_TEMPLATE = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Success</title>
""" + UI_STYLES + """
<style>body{display:flex;align-items:center;justify-content:center;height:100vh;text-align:center;}</style></head>
<body><div>
<h1 class="display-4" style="color:var(--primary-blue);"><i class="fas fa-check-circle fa-2x"></i><br>Registration Successful!</h1>
<p class="lead">Thank you. Your information has been submitted.</p>
</div></body></html>
"""

# ##############################################################################
# ## 2. APPLICATION SETUP & HELPERS
# ##############################################################################
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_KEY")

cloudinary.config(cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"), api_key=os.getenv("CLOUDINARY_API_KEY"), api_secret=os.getenv("CLOUDINARY_API_SECRET"))
client = MongoClient(os.getenv("MONGO_URI"))
db = client.get_database()
centers_collection, medicals_collection, patients_collection = db.centers, db.medicals, db.patients
ADMIN_USER, ADMIN_PASSWORD = os.getenv("ADMIN_USER"), os.getenv("ADMIN_PASSWORD")
HOST_URL = os.getenv("HOST_URL")

def render_page(title, content, **context):
    return render_template_string(ADMIN_LAYOUT_TEMPLATE, title=title, content=render_template_string(content, **context))

def generate_qr_code_base64(data):
    img = qrcode.make(data)
    buffered = io.BytesIO()
    img.save(buffered)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# ##############################################################################
# ## 3. SUPER ADMIN ROUTES
# ##############################################################################
@app.route('/')
def index():
    if 'logged_in' in session: return redirect(url_for('admin_dashboard'))
    if 'center_id' in session: return redirect(url_for('center_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('admin_dashboard'))
    return render_page("Super Admin Login", LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if 'logged_in' not in session: return redirect(url_for('login'))
    
    filter_date_str = request.args.get('filter_date', datetime.now().strftime('%Y-%m-%d'))
    try: start_of_day = datetime.strptime(filter_date_str, '%Y-%m-%d')
    except ValueError:
        filter_date_str = datetime.now().strftime('%Y-%m-%d')
        start_of_day = datetime.strptime(filter_date_str, '%Y-%m-%d')
    end_of_day = start_of_day + timedelta(days=1)

    all_centers = list(centers_collection.find({}, sort=[('name', 1)]))
    pipeline = [
        {"$sort": {"name": 1}},
        {"$lookup": {"from": "medicals", "localField": "_id", "foreignField": "center_id", "as": "medicals"}},
        {"$unwind": {"path": "$medicals", "preserveNullAndEmptyArrays": True}},
        {"$lookup": {
            "from": "patients", "let": {"medical_id": "$medicals._id"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$medical_id", "$$medical_id"]}, "timestamp": {"$gte": start_of_day, "$lt": end_of_day}}},
                {"$sort": {"timestamp": -1}}
            ], "as": "medicals.patients"
        }},
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
            "name": 1, "address": 1, "medicals": {"$filter": {"input": "$medicals", "as": "m", "cond": {"$ne": ["$$m._id", None]}}}
        }},
        {"$sort": {"name": 1}}
    ]
    centers_with_data = list(centers_collection.aggregate(pipeline))
    
    return render_page("Super Admin Dashboard", ADMIN_TEMPLATE, centers=all_centers, centers_with_medicals=centers_with_data, filter_date=filter_date_str)

@app.route('/add-center', methods=['POST'])
def add_center():
    if 'logged_in' not in session: return redirect(url_for('login'))
    form = request.form
    if centers_collection.find_one({"username": form['username']}):
        flash(f"Username '{form['username']}' already exists.", "danger")
    else:
        centers_collection.insert_one({
            "name": form['name'], "address": form['address'], "username": form['username'],
            "password": generate_password_hash(form['password'])
        })
        flash(f"Center '{form['name']}' created.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/reset-center-password/<center_id>', methods=['POST'])
def reset_center_password(center_id):
    if 'logged_in' not in session: return redirect(url_for('login'))
    hashed_password = generate_password_hash(request.form.get('new_password'))
    centers_collection.update_one({"_id": ObjectId(center_id)}, {"$set": {"password": hashed_password}})
    flash("Password has been reset.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/add-medical', methods=['POST'])
def add_medical():
    if 'logged_in' not in session: return redirect(url_for('login'))
    name, center_id_str = request.form.get('name'), request.form.get('center_id')
    if name and center_id_str:
        new_medical = medicals_collection.insert_one({'name': name, 'center_id': ObjectId(center_id_str), 'qr_code': ''})
        registration_url = f"{HOST_URL}/register/{new_medical.inserted_id}"
        qr_code_b64 = generate_qr_code_base64(registration_url)
        medicals_collection.update_one({'_id': new_medical.inserted_id}, {'$set': {'qr_code': qr_code_b64}})
        flash(f"Medical staff '{name}' added.", "success")
    return redirect(url_for('admin_dashboard'))

# ##############################################################################
# ## 4. CENTER ADMIN ROUTES
# ##############################################################################
@app.route('/center-login', methods=['GET', 'POST'])
def center_login():
    if request.method == 'POST':
        center = centers_collection.find_one({"username": request.form['username']})
        if center and check_password_hash(center.get('password', ''), request.form['password']):
            session['center_id'], session['center_name'] = str(center['_id']), center['name']
            return redirect(url_for('center_dashboard'))
        flash("Invalid center username or password.", "danger")
    return render_page("Center Login", CENTER_LOGIN_TEMPLATE)

@app.route('/center-logout')
def center_logout():
    session.pop('center_id', None)
    session.pop('center_name', None)
    return redirect(url_for('center_login'))

@app.route('/center-dashboard')
def center_dashboard():
    if 'center_id' not in session: return redirect(url_for('center_login'))
    filter_date_str = request.args.get('filter_date', datetime.now().strftime('%Y-%m-%d'))
    search_query = request.args.get('search_query', '')
    start_of_day = datetime.strptime(filter_date_str, '%Y-%m-%d')
    end_of_day = start_of_day + timedelta(days=1)
    
    query = {"center_id": ObjectId(session['center_id']), "timestamp": {"$gte": start_of_day, "$lt": end_of_day}}
    if search_query:
        query["$or"] = [
            {"name": {"$regex": search_query, "$options": "i"}},
            {"phone": {"$regex": search_query, "$options": "i"}}
        ]
    patients = list(patients_collection.find(query, sort=[("timestamp", -1)]))
    return render_page(f"{session['center_name']} Dashboard", CENTER_DASHBOARD_TEMPLATE, patients=patients, filter_date=filter_date_str, search_query=search_query)

@app.route('/update-patient-status/<patient_id>', methods=['POST'])
def update_patient_status(patient_id):
    if 'center_id' not in session: return redirect(url_for('center_login'))
    new_status = request.form.get('new_status')
    patient = patients_collection.find_one({"_id": ObjectId(patient_id), "center_id": ObjectId(session['center_id'])})
    if patient and new_status in ['Pending', 'Running', 'Complete']:
        patients_collection.update_one({"_id": ObjectId(patient_id)}, {"$set": {"status": new_status}})
        flash(f"Status updated to {new_status}.", "success")
    return redirect(request.referrer or url_for('center_dashboard'))

# ##############################################################################
# ## 5. DATA EXPORT & ANALYTICS ROUTES
# ##############################################################################
@app.route('/analytics')
def analytics_dashboard():
    if 'logged_in' not in session: return redirect(url_for('login'))
    thirty_days_ago = datetime.now() - timedelta(days=30)
    daily_pipeline = [
        {"$match": {"timestamp": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    daily_data = list(patients_collection.aggregate(daily_pipeline))
    daily_stats = {'labels': [d['_id'] for d in daily_data], 'data': [d['count'] for d in daily_data]}
    top_centers_pipeline = [
        {"$group": {"_id": "$center_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 5},
        {"$lookup": {"from": "centers", "localField": "_id", "foreignField": "_id", "as": "center_info"}},
        {"$unwind": "$center_info"}
    ]
    top_centers_data = list(patients_collection.aggregate(top_centers_pipeline))
    top_centers = {'labels': [c['center_info']['name'] for c in top_centers_data], 'data': [c['count'] for c in top_centers_data]}
    top_medicals_pipeline = [
        {"$group": {"_id": "$medical_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 5},
        {"$lookup": {"from": "medicals", "localField": "_id", "foreignField": "_id", "as": "medical_info"}},
        {"$unwind": "$medical_info"}
    ]
    top_medicals_data = list(patients_collection.aggregate(top_medicals_pipeline))
    top_medicals = {'labels': [m['medical_info']['name'] for m in top_medicals_data], 'data': [m['count'] for m in top_medicals_data]}
    return render_page("Analytics", ANALYTICS_TEMPLATE, daily_stats=daily_stats, top_centers=top_centers, top_medicals=top_medicals)

# ##############################################################################
# ## 6. PATIENT REGISTRATION ROUTES
# ##############################################################################
@app.route('/register/<medical_id>', methods=['GET', 'POST'])
def register_patient(medical_id):
    try:
        medical = medicals_collection.find_one({'_id': ObjectId(medical_id)})
        if not medical: return "<h2>Invalid registration link.</h2>", 404
        center = centers_collection.find_one({'_id': medical['center_id']})
        if request.method == 'POST':
            photo1_url, photo2_url = '', ''
            if 'photo1' in request.files and request.files['photo1'].filename != '':
                photo1_url = cloudinary.uploader.upload(request.files['photo1']).get('secure_url')
            if 'photo2' in request.files and request.files['photo2'].filename != '':
                photo2_url = cloudinary.uploader.upload(request.files['photo2']).get('secure_url')
            patients_collection.insert_one({
                'name': request.form['name'], 'phone': request.form['phone'], 'ultrasound_name': request.form['ultrasound_name'],
                'medical_id': ObjectId(medical_id), 'center_id': medical['center_id'], 
                'timestamp': datetime.utcnow(), 'status': 'Pending',
                'photo_url_1': photo1_url, 'photo_url_2': photo2_url
            })
            return redirect(url_for('registration_success'))
        return render_template_string(REGISTER_TEMPLATE, medical=medical, center=center)
    except Exception as e:
        return f"<h2>An error occurred: {e}</h2>", 400

@app.route('/success')
def registration_success():
    return render_template_string(SUCCESS_TEMPLATE)

# ##############################################################################
# ## 7. RUN APP
# ##############################################################################
if __name__ == '__main__':
    app.run(host=os.getenv("FLASK_HOST", "0.0.0.0"), port=int(os.getenv("FLASK_PORT", 5000)), debug=True)