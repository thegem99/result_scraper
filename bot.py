from flask import Flask, request, render_template_string, Response, jsonify, session as flask_session, send_file
import requests
from bs4 import BeautifulSoup
import os
import time
from io import BytesIO, StringIO
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import json
import hashlib
import threading
from functools import wraps
import re

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-here-2026")
app.config['PERMANENT_SESSION_LIFETIME'] = 3600

BASE_URL = "https://www.bsebexam.com"
CACHE = {}
FETCH_LOCK = threading.Lock()
REQUEST_TIMEOUT = 20

SUBJECTS = ["english", "hindi", "physics", "chemistry", "mathematics", "biology"]
SUBJECT_FULL_NAMES = {
    "english": "English", "hindi": "Hindi", "physics": "Physics",
    "chemistry": "Chemistry", "mathematics": "Mathematics", "biology": "Biology"
}

# ================= DECORATORS =================
def async_action(f):
    """Decorator for async operations"""
    @wraps(f)
    def decorated(*args, **kwargs):
        thread = threading.Thread(target=f, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return jsonify({"status": "processing", "message": "Request is being processed"})
    return decorated

# ================= SESSION MANAGEMENT =================
def get_session():
    """Create a new session with headers"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })
    return session

def get_token(session):
    """Extract verification token with multiple fallback methods"""
    try:
        res = session.get(BASE_URL + "/", timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Try multiple token input patterns
        token = soup.find("input", {"name": "__RequestVerificationToken"})
        if not token:
            token = soup.find("input", {"name": "__RequestVerificationToken", "type": "hidden"})
        if not token:
            token = soup.find("input", {"value": re.compile(r"^[A-Za-z0-9\-_]+$"), "type": "hidden"})
        
        return token.get("value") if token else None
    except Exception as e:
        print(f"Token fetch error: {e}")
        return None

# ================= SUBJECT NORMALIZER =================
def normalize_subject(name):
    """Enhanced subject name normalization"""
    name = name.lower().strip()
    
    subject_mapping = {
        "math": "mathematics", "maths": "mathematics", "mathematic": "mathematics",
        "bio": "biology", "biological": "biology", "life science": "biology",
        "physic": "physics", "physical": "physics",
        "chem": "chemistry", "chemical": "chemistry",
        "english": "english", "eng": "english",
        "hindi": "hindi", "hind": "hindi"
    }
    
    for key, value in subject_mapping.items():
        if key in name:
            return value
    return None

def parse_grade(grade_text):
    """Parse grade with numeric conversion"""
    grade_text = str(grade_text).upper().strip()
    
    grade_points = {
        "A1": 10, "A2": 9, "B1": 8, "B2": 7, "C1": 6, "C2": 5,
        "D": 4, "E1": 3, "E2": 2
    }
    
    match = re.search(r'([A-Z][0-9]?)', grade_text)
    if match:
        grade = match.group(1)
        return grade, grade_points.get(grade, 0)
    return grade_text, 0

# ================= FETCH RESULT =================
def fetch_result(session, token, rollcode, rollno):
    """Enhanced result fetching with better error handling"""
    url = BASE_URL + "/Result/GetResult"
    payload = {
        "rollcode": rollcode,
        "rollno": rollno,
        "captcha": "123456",
        "__RequestVerificationToken": token
    }
    
    try:
        res = session.post(url, data=payload, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "html.parser")
        data = {
            "name": "", "father": "", "mother": "", "roll_no": rollno,
            "school": "", "school_code": "", "total": "", "percentage": "",
            "result": "", "subjects": {}, "grade_details": {}
        }
        
        # Enhanced parsing with more fields
        for row in soup.find_all("tr"):
            cols = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 2:
                continue
                
            key = cols[0].lower().strip()
            value = cols[-1].strip()
            
            if "student" in key and "name" in key:
                data["name"] = value
            elif "father" in key:
                data["father"] = value
            elif "mother" in key:
                data["mother"] = value
            elif "school" in key and "code" in key:
                data["school_code"] = value
            elif "school" in key:
                data["school"] = value
            elif "aggregate" in key or "total" in key:
                data["total"] = value
            elif "percentage" in key:
                data["percentage"] = value
            elif "result" in key:
                data["result"] = value
            elif len(cols) >= 5:
                norm = normalize_subject(cols[0])
                if norm:
                    grade, points = parse_grade(value)
                    data["subjects"][norm] = value
                    data["grade_details"][norm] = {"grade": grade, "points": points}
        
        # Calculate additional stats
        if data["grade_details"]:
            total_points = sum(g["points"] for g in data["grade_details"].values())
            if total_points > 0:
                data["cgpa"] = round(total_points / len(data["grade_details"]), 2)
        
        return data
    except Exception as e:
        print(f"Fetch error for roll {rollno}: {e}")
        return {
            "name": "Error", "father": "", "mother": "", "roll_no": rollno,
            "school": "", "school_code": "", "total": "", "percentage": "",
            "result": "Failed", "subjects": {}, "grade_details": {}, "error": str(e)
        }

# ================= BULK FETCH =================
def fetch_bulk_results(rollcode, start_rollno, count, progress_callback=None):
    """Fetch multiple results with progress tracking"""
    results = []
    session = get_session()
    
    for i in range(count):
        rn = str(int(start_rollno) + i)
        try:
            with FETCH_LOCK:
                token = get_token(session)
                if not token:
                    results.append({"roll_no": rn, "error": "Token fetch failed"})
                else:
                    res = fetch_result(session, token, rollcode, rn)
                    results.append(res)
                time.sleep(0.5)  # Rate limiting
            
            if progress_callback:
                progress_callback(i + 1, count)
        except Exception as e:
            results.append({"roll_no": rn, "error": str(e)})
    
    return results

# ================= MODERN HTML TEMPLATES =================
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>BSEB Result Portal 2026</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Animated Background */
        .bg-animation {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            overflow: hidden;
        }
        
        .bg-animation .circle {
            position: absolute;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            animation: float 20s infinite;
        }
        
        @keyframes float {
            0%, 100% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(-100px) rotate(180deg); }
        }
        
        /* Glassmorphism Container */
        .glass-container {
            position: relative;
            z-index: 1;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Header */
        .header {
            text-align: center;
            padding: 40px 20px;
            color: white;
            animation: slideDown 0.8s ease-out;
        }
        
        .header h1 {
            font-size: 3rem;
            font-weight: 800;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        .header .subtitle {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        /* Cards */
        .card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 30px 50px rgba(0,0,0,0.15);
        }
        
        /* Form Styles */
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        
        .form-control {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 16px;
            transition: all 0.3s;
            font-family: 'Inter', sans-serif;
        }
        
        .form-control:focus {
            outline: none;
            border-color: #764ba2;
            box-shadow: 0 0 0 3px rgba(118, 75, 162, 0.1);
        }
        
        /* Button Styles */
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-family: 'Inter', sans-serif;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-outline {
            background: transparent;
            border: 2px solid #764ba2;
            color: #764ba2;
        }
        
        .btn-outline:hover {
            background: #764ba2;
            color: white;
        }
        
        /* Result Table */
        .result-table-wrapper {
            overflow-x: auto;
            border-radius: 12px;
        }
        
        .result-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }
        
        .result-table th {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 15px;
            font-weight: 600;
            position: sticky;
            top: 0;
        }
        
        .result-table td {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .result-table tr:hover {
            background: #f8f9fa;
            transform: scale(1.01);
            transition: all 0.2s;
        }
        
        /* Score Cards */
        .score-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .score-card {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            transition: transform 0.3s;
        }
        
        .score-card:hover {
            transform: translateY(-5px);
        }
        
        .score-card .value {
            font-size: 2.5rem;
            font-weight: 800;
            margin: 10px 0;
        }
        
        /* Loading Animation */
        .loader {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 9999;
            justify-content: center;
            align-items: center;
        }
        
        .loader.active {
            display: flex;
        }
        
        .spinner {
            width: 50px;
            height: 50px;
            border: 5px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Toast Notifications */
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
        }
        
        .toast {
            background: white;
            border-radius: 12px;
            padding: 15px 20px;
            margin-bottom: 10px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            gap: 12px;
            animation: slideInRight 0.3s ease-out;
        }
        
        @keyframes slideInRight {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .header h1 { font-size: 2rem; }
            .card { padding: 20px; }
            .btn { padding: 10px 20px; }
        }
        
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border: none;
            background: none;
            font-weight: 600;
            color: #666;
            transition: all 0.3s;
        }
        
        .tab.active {
            color: #764ba2;
            border-bottom: 2px solid #764ba2;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
            animation: fadeIn 0.5s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        /* Statistics */
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .stat-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 12px;
            text-align: center;
        }
        
        .stat-label {
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 5px;
        }
        
        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: #764ba2;
        }
    </style>
</head>
<body>
    <div class="bg-animation" id="bgAnimation"></div>
    <div class="loader" id="loader">
        <div class="spinner"></div>
    </div>
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="glass-container">
        {% block content %}{% endblock %}
    </div>
    
    <script>
        // Animated Background
        function createCircles() {
            const container = document.getElementById('bgAnimation');
            for(let i = 0; i < 15; i++) {
                const circle = document.createElement('div');
                circle.className = 'circle';
                const size = Math.random() * 200 + 50;
                circle.style.width = size + 'px';
                circle.style.height = size + 'px';
                circle.style.left = Math.random() * 100 + '%';
                circle.style.top = Math.random() * 100 + '%';
                circle.style.animationDelay = Math.random() * 20 + 's';
                circle.style.animationDuration = Math.random() * 20 + 10 + 's';
                container.appendChild(circle);
            }
        }
        
        // Toast Notifications
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = 'toast';
            const icon = type === 'success' ? '✓' : '⚠️';
            toast.innerHTML = `<span style="font-size: 20px;">${icon}</span><span>${message}</span>`;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
        
        // Loading Control
        function showLoading() {
            document.getElementById('loader').classList.add('active');
        }
        
        function hideLoading() {
            document.getElementById('loader').classList.remove('active');
        }
        
        // Form Submit Handler
        document.addEventListener('DOMContentLoaded', () => {
            createCircles();
            
            // Auto-hide toasts after 3 seconds
            setInterval(() => {
                const toasts = document.querySelectorAll('.toast');
                toasts.forEach(toast => {
                    if(toast.getAttribute('data-timer')) return;
                    toast.setAttribute('data-timer', 'true');
                    setTimeout(() => toast.remove(), 3000);
                });
            }, 1000);
        });
    </script>
    {% block scripts %}{% endblock %}
</body>
</html>
"""

HOME_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<div class="header">
    <h1><i class="fas fa-graduation-cap"></i> BSEB Result Portal 2026</h1>
    <p class="subtitle">Bihar School Examination Board - Interactive Result Dashboard</p>
</div>

<div class="card">
    <h2><i class="fas fa-search"></i> Search Results</h2>
    <form id="resultForm" method="GET" action="/view">
        <div class="form-group">
            <label><i class="fas fa-qrcode"></i> Roll Code</label>
            <input type="text" name="rollcode" class="form-control" placeholder="Enter Roll Code" required>
        </div>
        
        <div class="form-group">
            <label><i class="fas fa-id-card"></i> Starting Roll Number</label>
            <input type="number" name="rollno" class="form-control" placeholder="Enter Starting Roll Number" required>
        </div>
        
        <div class="form-group">
            <label><i class="fas fa-layer-group"></i> Number of Results (max 100)</label>
            <input type="number" name="count" class="form-control" value="1" min="1" max="100">
        </div>
        
        <div class="form-group">
            <label><i class="fas fa-chart-line"></i> Advanced Options</label>
            <div style="display: flex; gap: 10px;">
                <label><input type="checkbox" name="stats" value="1"> Show Statistics</label>
                <label><input type="checkbox" name="charts" value="1"> Generate Charts</label>
                <label><input type="checkbox" name="compare" value="1"> Compare Results</label>
            </div>
        </div>
        
        <button type="submit" class="btn btn-primary" onclick="showLoading()">
            <i class="fas fa-download"></i> Fetch Results
        </button>
    </form>
</div>

<div class="card">
    <h3><i class="fas fa-info-circle"></i> Quick Guide</h3>
    <div class="score-grid">
        <div class="score-card">
            <i class="fas fa-tachometer-alt fa-2x"></i>
            <div class="value">Bulk Fetch</div>
            <div>Fetch up to 100 results at once</div>
        </div>
        <div class="score-card">
            <i class="fas fa-chart-pie fa-2x"></i>
            <div class="value">Analysis</div>
            <div>Real-time statistics & charts</div>
        </div>
        <div class="score-card">
            <i class="fas fa-download fa-2x"></i>
            <div class="value">Export</div>
            <div>CSV & PDF export options</div>
        </div>
    </div>
</div>

<script>
    document.getElementById('resultForm').addEventListener('submit', function(e) {
        showLoading();
    });
</script>
{% endblock %}
"""

# ================= FLASK ROUTES =================
@app.route("/")
def home():
    return render_template_string(BASE_TEMPLATE.replace("{% block content %}{% endblock %}", HOME_TEMPLATE), 
                                 base_template=BASE_TEMPLATE)

@app.route("/view")
def view():
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")
    count = min(int(request.args.get("count", 1)), 100)
    show_stats = request.args.get("stats") == "1"
    show_charts = request.args.get("charts") == "1"
    
    results = fetch_bulk_results(rollcode, rollno, count)
    CACHE["data"] = results
    CACHE["metadata"] = {
        "rollcode": rollcode,
        "start_roll": rollno,
        "count": count,
        "timestamp": datetime.now().isoformat()
    }
    
    # Calculate statistics
    stats = {}
    if show_stats:
        total_students = len([r for r in results if "error" not in r])
        passed = len([r for r in results if r.get("result", "").upper() == "PASS"])
        failed = total_students - passed
        
        subject_stats = {}
        for subject in SUBJECTS:
            marks = []
            for r in results:
                if subject in r.get("subjects", {}):
                    marks.append(r["subjects"][subject])
            if marks:
                subject_stats[subject] = {
                    "count": len(marks),
                    "avg": "N/A"  # Would need numeric conversion
                }
        
        stats = {
            "total": total_students,
            "passed": passed,
            "failed": failed,
            "pass_percentage": round((passed / total_students * 100) if total_students > 0 else 0, 2),
            "subjects": subject_stats
        }
    
    results_html = generate_results_html(results, stats, show_stats, show_charts)
    return render_template_string(BASE_TEMPLATE.replace("{% block content %}{% endblock %}", results_html),
                                 base_template=BASE_TEMPLATE)

def generate_results_html(results, stats, show_stats, show_charts):
    html = """
    <div class="header">
        <h1><i class="fas fa-chalkboard-user"></i> Examination Results</h1>
        <p class="subtitle">Fetch completed • {count} records found</p>
    </div>
    
    <div class="card">
        <div class="tabs">
            <button class="tab active" onclick="switchTab('table')"><i class="fas fa-table"></i> Table View</button>
            <button class="tab" onclick="switchTab('stats')"><i class="fas fa-chart-bar"></i> Statistics</button>
            <button class="tab" onclick="switchTab('cards')"><i class="fas fa-id-card"></i> Card View</button>
        </div>
        
        <div id="table-tab" class="tab-content active">
            <div style="margin-bottom: 20px; display: flex; gap: 10px; justify-content: center;">
                <a href="/download"><button class="btn btn-primary"><i class="fas fa-download"></i> Download CSV</button></a>
                <a href="/pdf"><button class="btn btn-primary"><i class="fas fa-file-pdf"></i> Download PDF</button></a>
                <button class="btn btn-outline" onclick="window.print()"><i class="fas fa-print"></i> Print</button>
            </div>
            <div class="result-table-wrapper">
                <table class="result-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Name</th>
                            <th>Father's Name</th>
                            <th>Roll No</th>
                            <th>School</th>
                            <th>Total</th>
                            <th>Result</th>
                            <th>CGPA</th>
                            """ + "".join([f"<th>{SUBJECT_FULL_NAMES[s]}</th>" for s in SUBJECTS]) + """
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for idx, r in enumerate(results, 1):
        html += f"""
            <tr>
                <td>{idx}</td>
                <td>{r.get('name', 'N/A')}</td>
                <td>{r.get('father', 'N/A')}</td>
                <td>{r.get('roll_no', 'N/A')}</td>
                <td>{r.get('school', 'N/A')[:30]}</td>
                <td>{r.get('total', 'N/A')}</td>
                <td><span class="{'pass-badge' if r.get('result') == 'PASS' else 'fail-badge'}">{r.get('result', 'N/A')}</span></td>
                <td>{r.get('cgpa', 'N/A')}</td>
                {"".join([f"<td>{r.get('subjects', {}).get(s, 'N/A')}</td>" for s in SUBJECTS])}
            </tr>
        """
    
    html += """
                    </tbody>
                </table>
            </div>
        </div>
        
        <div id="stats-tab" class="tab-content">
    """
    
    if show_stats and stats:
        html += f"""
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-label">Total Students</div>
                    <div class="stat-value">{stats.get('total', 0)}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Passed</div>
                    <div class="stat-value" style="color: #28a745;">{stats.get('passed', 0)}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Failed</div>
                    <div class="stat-value" style="color: #dc3545;">{stats.get('failed', 0)}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Pass Percentage</div>
                    <div class="stat-value">{stats.get('pass_percentage', 0)}%</div>
                </div>
            </div>
        """
        
        if show_charts:
            html += """
            <canvas id="resultChart" style="max-height: 400px; margin-top: 30px;"></canvas>
            <script>
                new Chart(document.getElementById('resultChart'), {
                    type: 'pie',
                    data: {
                        labels: ['Passed', 'Failed'],
                        datasets: [{
                            data: [""" + str(stats.get('passed', 0)) + ", " + str(stats.get('failed', 0)) + """],
                            backgroundColor: ['#28a745', '#dc3545']
                        }]
                    }
                });
            </script>
            """
    else:
        html += "<p><i class='fas fa-chart-line'></i> Enable statistics to view analysis</p>"
    
    html += """
        </div>
        
        <div id="cards-tab" class="tab-content">
            <div class="score-grid">
    """
    
    for r in results[:20]:  # Limit to 20 cards for performance
        html += f"""
            <div class="score-card" style="background: white; color: #333; border: 1px solid #e0e0e0;">
                <i class="fas fa-user-graduate" style="font-size: 2rem; color: #764ba2;"></i>
                <div class="value" style="font-size: 1.2rem;">{r.get('name', 'N/A')}</div>
                <div>Roll: {r.get('roll_no', 'N/A')}</div>
                <div>Total: {r.get('total', 'N/A')}</div>
                <div>Result: {r.get('result', 'N/A')}</div>
            </div>
        """
    
    html += """
            </div>
        </div>
    </div>
    
    <style>
        .pass-badge {
            background: #d4edda;
            color: #155724;
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .fail-badge {
            background: #f8d7da;
            color: #721c24;
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }
    </style>
    
    <script>
        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
            document.querySelector(`.tab[onclick="switchTab('${tabName}')"]`).classList.add('active');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        }
    </script>
    """
    
    return html

@app.route("/download")
def download():
    results = CACHE.get("data", [])
    if not results:
        return "No data available", 404
    
    output = StringIO()
    headers = ["Sl No", "Name", "Father", "Mother", "Roll No", "School", "School Code", "Total", "Percentage", "Result", "CGPA"] + [SUBJECT_FULL_NAMES[s] for s in SUBJECTS]
    output.write(",".join(f'"{h}"' for h in headers) + "\n")
    
    for idx, r in enumerate(results, 1):
        row = [
            idx, r.get("name", ""), r.get("father", ""), r.get("mother", ""),
            r.get("roll_no", ""), r.get("school", ""), r.get("school_code", ""),
            r.get("total", ""), r.get("percentage", ""), r.get("result", ""),
            r.get("cgpa", "")
        ]
        for s in SUBJECTS:
            row.append(r.get("subjects", {}).get(s, ""))
        
        # Fixed: Properly escape CSV values
        escaped_row = []
        for x in row:
            str_x = str(x)
            # Escape double quotes by doubling them
            str_x = str_x.replace('"', '""')
            escaped_row.append(f'"{str_x}"')
        
        output.write(",".join(escaped_row) + "\n")
    
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", 
                   headers={"Content-Disposition": "attachment; filename=bseb_results_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"})

@app.route("/pdf")
def pdf():
    results = CACHE.get("data", [])
    if not results:
        return "No data available", 404
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, spaceAfter=30)
    elements.append(Paragraph("Bihar School Examination Board - Result Summary", title_style))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Create table data
    table_data = [["Sl No", "Name", "Roll No", "Total", "Result"]]
    for idx, r in enumerate(results[:50], 1):
        table_data.append([str(idx), r.get("name", "N/A")[:30], r.get("roll_no", "N/A"), r.get("total", "N/A"), r.get("result", "N/A")])
    
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#764ba2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', 
                    download_name=f"bseb_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    as_attachment=True)

@app.route("/api/results", methods=["GET"])
def api_results():
    """REST API endpoint for results"""
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")
    count = min(int(request.args.get("count", 1)), 50)
    
    if not rollcode or not rollno:
        return jsonify({"error": "Roll code and roll number required"}), 400
    
    results = fetch_bulk_results(rollcode, rollno, count)
    return jsonify({
        "status": "success",
        "count": len(results),
        "results": results,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/statistics", methods=["GET"])
def api_statistics():
    """Get statistics for cached results"""
    results = CACHE.get("data", [])
    if not results:
        return jsonify({"error": "No data available"}), 404
    
    stats = {
        "total": len(results),
        "passed": len([r for r in results if r.get("result", "").upper() == "PASS"]),
        "failed": len([r for r in results if r.get("result", "").upper() == "FAIL"]),
        "average_total": "N/A",
        "subject_stats": {}
    }
    
    stats["pass_percentage"] = round((stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0, 2)
    
    return jsonify(stats)

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cached_results": len(CACHE.get("data", []))
    })

# ================= ERROR HANDLERS =================
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

# ================= RUN APPLICATION =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "False").lower() == "true"
    
    print("=" * 50)
    print("BSEB Result Portal Starting...")
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=port, debug=debug)
