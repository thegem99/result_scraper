# from flask import Flask, request, render_template_string, Response
# import requests
# from bs4 import BeautifulSoup
# import os
# import time
# from io import BytesIO
# from reportlab.lib.pagesizes import letter
# from reportlab.pdfgen import canvas

# app = Flask(__name__)

# BASE_URL = "https://www.bsebexam.com"
# CACHE = {}

# SUBJECTS = ["english","hindi","physics","chemistry","mathematics","biology"]

# # ================= SESSION =================
# def get_session():
#     return requests.Session()

# # ================= TOKEN =================
# def get_token(session):
#     res = session.get(BASE_URL + "/", timeout=15)
#     soup = BeautifulSoup(res.text, "html.parser")
#     token = soup.find("input", {"name": "__RequestVerificationToken"})
#     return token.get("value") if token else None

# # ================= SUBJECT NORMALIZER =================
# def normalize_subject(name):
#     name = name.lower().strip()
#     if "math" in name: return "mathematics"
#     if "bio" in name: return "biology"
#     if "physic" in name: return "physics"
#     if "chem" in name: return "chemistry"
#     if "english" in name: return "english"
#     if "hindi" in name: return "hindi"
#     return None

# # ================= FETCH RESULT =================
# def fetch_result(session, token, rollcode, rollno):
#     url = BASE_URL + "/Result/GetResult"
#     payload = {
#         "rollcode": rollcode,
#         "rollno": rollno,
#         "captcha": "123456",
#         "__RequestVerificationToken": token
#     }
#     headers = {
#         "User-Agent": "Mozilla/5.0",
#         "Origin": BASE_URL,
#         "Referer": BASE_URL + "/",
#         "Content-Type": "application/x-www-form-urlencoded"
#     }
#     res = session.post(url, data=payload, headers=headers, timeout=20)
#     soup = BeautifulSoup(res.text, "html.parser")
#     data = {"name":"","father":"","roll_no":rollno,"school":"","total":"","subjects":{}}
#     for row in soup.find_all("tr"):
#         cols = [c.get_text(" ", strip=True) for c in row.find_all(["td","th"])]
#         if len(cols) < 2:
#             continue
#         key = cols[0].lower().strip()
#         value = cols[-1].strip()
#         if "student" in key and "name" in key:
#             data["name"] = value
#         elif "father" in key:
#             data["father"] = value
#         elif "school" in key:
#             data["school"] = value
#         elif "aggregate" in key:
#             data["total"] = value
#         elif len(cols) >= 5:
#             norm = normalize_subject(cols[0])
#             if norm:
#                 data["subjects"][norm] = value
#     return data

# # ================= HOME PAGE =================
# @app.route("/")
# def home():
#     return render_template_string("""
# <!DOCTYPE html>
# <html>
# <head>
# <title>BSEB Result Portal</title>
# <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
# <style>
# body{
#     margin:0;
#     padding:0;
#     font-family:'Roboto',sans-serif;
#     height:100vh;
#     background: linear-gradient(135deg,#667eea,#764ba2);
#     display:flex;
#     justify-content:center;
#     align-items:center;
#     overflow:hidden;
#     color:white;
# }
# .box{
#     background:rgba(255,255,255,0.95);
#     color:black;
#     padding:40px;
#     border-radius:15px;
#     box-shadow:0 10px 30px rgba(0,0,0,0.2);
#     text-align:center;
#     width:380px;
#     position:relative;
#     z-index:2;
#     animation: slideIn 1s ease-out;
# }
# input,button{
#     width:100%;
#     padding:12px;
#     margin:10px 0;
#     border-radius:6px;
#     border:1px solid #ddd;
#     transition: all 0.3s;
# }
# input:focus{
#     border-color:#764ba2;
#     box-shadow:0 0 10px rgba(118,75,162,0.3);
#     outline:none;
# }
# button{
#     background:#764ba2;
#     color:white;
#     border:none;
#     cursor:pointer;
#     font-weight:bold;
# }
# button:hover{
#     background:#667eea;
#     transform: scale(1.05);
# }
# @keyframes slideIn{
#     from{opacity:0; transform: translateY(-50px);}
#     to{opacity:1; transform: translateY(0);}
# }
# /* Particle effect */
# #particles-js{
#     position:absolute;
#     width:100%;
#     height:100%;
#     top:0;
#     left:0;
#     z-index:1;
# }
# </style>
# </head>
# <body>
# <div id="particles-js"></div>
# <div class="box">
# <h2>BSEB Result 2026</h2>
# <form action="/view">
# <input name="rollcode" placeholder="Roll Code" required>
# <input name="rollno" placeholder="Starting Roll Number" required>
# <input name="count" placeholder="Count (max 50)" value="1">
# <button>Get Result</button>
# </form>
# </div>
# <!-- particles.js library -->
# <script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
# <script>
# particlesJS("particles-js",{
#   "particles":{"number":{"value":50},"size":{"value":3},"move":{"speed":2},"line_linked":{"enable":true}},
#   "interactivity":{"events":{"onhover":{"enable":true,"mode":"repulse"}}}
# });
# </script>
# </body>
# </html>
# """)

# # ================= VIEW PAGE =================
# @app.route("/view")
# def view():
#     rollcode = request.args.get("rollcode")
#     rollno = request.args.get("rollno")
#     count = min(int(request.args.get("count", 1)), 50)
#     session = get_session()
#     results = []

#     for i in range(count):
#         rn = str(int(rollno)+i)
#         token = get_token(session)  # ✅ fresh token for each roll number
#         try:
#             res = fetch_result(session, token, rollcode, rn)
#         except:
#             res = {"name":"Error","father":"","roll_no":rn,"school":"","total":"","subjects":{}}
#         results.append(res)
#         time.sleep(0.3)

#     CACHE["data"] = results

#     html = """
# <html>
# <head>
# <style>
# body{font-family:Arial;background:#f4f6f9;padding:20px;}
# table{width:100%;border-collapse:collapse;background:white;box-shadow:0 5px 15px rgba(0,0,0,0.1);}
# th,td{border:1px solid #ddd;padding:8px;text-align:center;transition:0.3s;}
# th{background:#764ba2;color:white;position:sticky;top:0;}
# tr:hover{background:#e1f0ff;transform:scale(1.01);}
# button{padding:10px 20px;margin:10px;background:#667eea;color:white;border:none;border-radius:6px;cursor:pointer;transition:0.3s;}
# button:hover{background:#764ba2;transform:scale(1.05);}
# </style>
# </head>
# <body>
# <h2 align="center">Result Sheet</h2>
# <div style="text-align:center;margin-bottom:15px;">
# <a href="/download"><button>Download CSV</button></a>
# <a href="/pdf"><button>Download PDF</button></a>
# </div>
# <table><tr>
# """
#     headers = ["Name","Father","Roll No","School","Total"]+[s.title() for s in SUBJECTS]
#     for h in headers: html+=f"<th>{h}</th>"
#     html+="</tr>"
#     for r in results:
#         html+="<tr>"
#         html+=f"<td>{r['name']}</td><td>{r['father']}</td><td>{r['roll_no']}</td><td>{r['school']}</td><td>{r['total']}</td>"
#         for s in SUBJECTS: html+=f"<td>{r['subjects'].get(s,'')}</td>"
#         html+="</tr>"
#     html+="</table></body></html>"
#     return html

# # ================= DOWNLOAD CSV =================
# @app.route("/download")
# def download():
#     results = CACHE.get("data",[])
#     def generate():
#         header=["Name","Father","Roll No","School","Total"]+[s.title() for s in SUBJECTS]
#         yield ",".join(header)+"\n"
#         for r in results:
#             row=[r["name"],r["father"],r["roll_no"],r["school"],r["total"]]
#             for s in SUBJECTS: row.append(r["subjects"].get(s,""))
#             yield ",".join(f'"{x}"' for x in row)+"\n"
#     return Response(generate(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=results.csv"})

# # ================= DOWNLOAD PDF =================
# @app.route("/pdf")
# def pdf():
#     results = CACHE.get("data",[])
#     buffer = BytesIO()
#     p = canvas.Canvas(buffer,pagesize=letter)
#     width,height=letter
#     y=height-40
#     p.setFont("Helvetica-Bold",16)
#     p.drawString(180,y,"BSEB Result Sheet")
#     y-=30
#     p.setFont("Helvetica",9)
#     for r in results:
#         if y<40:
#             p.showPage()
#             y=height-40
#         line=f"{r['roll_no']} | {r['name']} | {r['total']}"
#         p.drawString(40,y,line)
#         y-=15
#     p.save()
#     buffer.seek(0)
#     return Response(buffer,mimetype='application/pdf',headers={"Content-Disposition":"attachment; filename=results.pdf"})

# # ================= RUN =================
# if __name__=="__main__":
#     port=int(os.environ.get("PORT",8080))
#     app.run(host="0.0.0.0",port=port)




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
    <title>BSEB Result Portal 2026 | Interactive Result Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/typed.js@2.0.12"></script>
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
            cursor: default;
        }
        
        /* Particle Background */
        #particles-js {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
        }
        
        /* Animated Background Shapes */
        .bg-shapes {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            overflow: hidden;
        }
        
        .shape {
            position: absolute;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            animation: float 20s infinite ease-in-out;
        }
        
        @keyframes float {
            0%, 100% {
                transform: translateY(0) translateX(0) rotate(0deg);
            }
            33% {
                transform: translateY(-30px) translateX(20px) rotate(120deg);
            }
            66% {
                transform: translateY(30px) translateX(-20px) rotate(240deg);
            }
        }
        
        /* Glassmorphism Container */
        .glass-container {
            position: relative;
            z-index: 1;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Animated Header */
        .header {
            text-align: center;
            padding: 50px 20px;
            color: white;
            animation: slideDown 0.8s ease-out;
            position: relative;
        }
        
        .header h1 {
            font-size: 3.5rem;
            font-weight: 800;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            background: linear-gradient(135deg, #fff, #f0f0f0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .header .subtitle {
            font-size: 1.2rem;
            opacity: 0.95;
        }
        
        .typed-text {
            font-size: 1.3rem;
            font-weight: 500;
            margin-top: 15px;
            color: #ffd700;
        }
        
        /* Cards */
        .card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .card:hover {
            transform: translateY(-8px);
            box-shadow: 0 30px 50px rgba(0,0,0,0.2);
        }
        
        /* Form Styles with Animation */
        .form-group {
            margin-bottom: 20px;
            position: relative;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
            transition: all 0.3s;
        }
        
        .form-control {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            font-size: 16px;
            transition: all 0.3s;
            font-family: 'Inter', sans-serif;
            background: white;
        }
        
        .form-control:focus {
            outline: none;
            border-color: #764ba2;
            box-shadow: 0 0 0 4px rgba(118, 75, 162, 0.2);
            transform: scale(1.02);
        }
        
        /* Glowing Button */
        .btn {
            padding: 14px 28px;
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
            position: relative;
            overflow: hidden;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        
        .btn-primary:active {
            transform: translateY(0);
        }
        
        .btn-primary::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255,255,255,0.3);
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }
        
        .btn-primary:active::before {
            width: 300px;
            height: 300px;
        }
        
        /* Result Table with Animation */
        .result-table-wrapper {
            overflow-x: auto;
            border-radius: 12px;
            animation: fadeInUp 0.6s ease-out;
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
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .result-table th:hover {
            background: linear-gradient(135deg, #764ba2, #667eea);
            transform: scale(1.02);
        }
        
        .result-table td {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
            transition: all 0.3s;
        }
        
        .result-table tr {
            animation: slideIn 0.3s ease-out;
            transition: all 0.3s;
        }
        
        .result-table tr:hover {
            background: linear-gradient(90deg, #f8f9fa, #e9ecef);
            transform: translateX(5px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        /* Score Cards with 3D Effect */
        .score-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 25px;
            margin-top: 20px;
        }
        
        .score-card {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 25px;
            border-radius: 20px;
            text-align: center;
            transition: all 0.4s;
            position: relative;
            overflow: hidden;
            cursor: pointer;
        }
        
        .score-card::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.2), transparent);
            transform: rotate(45deg);
            transition: all 0.6s;
            opacity: 0;
        }
        
        .score-card:hover::before {
            opacity: 1;
            transform: rotate(45deg) translate(50%, 50%);
        }
        
        .score-card:hover {
            transform: translateY(-10px) scale(1.05);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }
        
        .score-card .value {
            font-size: 2.5rem;
            font-weight: 800;
            margin: 15px 0;
            animation: pulse 2s infinite;
        }
        
        /* Loading Animation */
        .loader {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.85);
            z-index: 9999;
            justify-content: center;
            align-items: center;
            backdrop-filter: blur(5px);
        }
        
        .loader.active {
            display: flex;
            animation: fadeIn 0.3s;
        }
        
        .loader-content {
            text-align: center;
            color: white;
        }
        
        .spinner {
            width: 60px;
            height: 60px;
            border: 5px solid rgba(255,255,255,0.3);
            border-top-color: #fff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 20px;
        }
        
        .loader-text {
            font-size: 1.2rem;
            animation: pulse 1.5s infinite;
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
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            gap: 12px;
            animation: slideInRight 0.3s ease-out;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .toast:hover {
            transform: translateX(-5px);
            box-shadow: 0 15px 35px rgba(0,0,0,0.25);
        }
        
        /* Stats Cards */
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .stat-item {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            transition: all 0.3s;
            cursor: pointer;
            animation: fadeInUp 0.5s ease-out;
        }
        
        .stat-item:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }
        
        .stat-label {
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 8px;
            font-weight: 500;
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 800;
            color: #764ba2;
            animation: countUp 0.8s ease-out;
        }
        
        /* Animations */
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; transform: scale(1.05); }
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
        
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes countUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
            border-bottom: 2px solid #e0e0e0;
            flex-wrap: wrap;
        }
        
        .tab {
            padding: 12px 24px;
            cursor: pointer;
            border: none;
            background: none;
            font-weight: 600;
            color: #666;
            transition: all 0.3s;
            position: relative;
            border-radius: 10px 10px 0 0;
        }
        
        .tab:hover {
            color: #764ba2;
            background: rgba(118, 75, 162, 0.05);
        }
        
        .tab.active {
            color: #764ba2;
            background: rgba(118, 75, 162, 0.1);
        }
        
        .tab.active::after {
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #667eea, #764ba2);
            animation: slideIn 0.3s ease-out;
        }
        
        .tab-content {
            display: none;
            animation: fadeInUp 0.5s ease-out;
        }
        
        .tab-content.active {
            display: block;
        }
        
        /* Scrollbar Styling */
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(135deg, #764ba2, #667eea);
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .header h1 { font-size: 2rem; }
            .card { padding: 20px; }
            .btn { padding: 10px 20px; }
            .tabs { gap: 5px; }
            .tab { padding: 8px 16px; font-size: 14px; }
        }
        
        /* Badge Styles */
        .pass-badge {
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            display: inline-block;
            animation: pulse 2s infinite;
        }
        
        .fail-badge {
            background: linear-gradient(135deg, #dc3545, #c82333);
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        
        /* Floating Action Button */
        .fab {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
            transition: all 0.3s;
            z-index: 1000;
        }
        
        .fab:hover {
            transform: scale(1.1) rotate(90deg);
            box-shadow: 0 8px 25px rgba(0,0,0,0.4);
        }
        
        /* Tooltip */
        [data-tooltip] {
            position: relative;
            cursor: help;
        }
        
        [data-tooltip]:before {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            padding: 5px 10px;
            background: rgba(0,0,0,0.8);
            color: white;
            border-radius: 5px;
            font-size: 12px;
            white-space: nowrap;
            display: none;
            z-index: 1000;
        }
        
        [data-tooltip]:hover:before {
            display: block;
        }
    </style>
</head>
<body>
    <div id="particles-js"></div>
    <div class="bg-shapes" id="bgShapes"></div>
    <div class="loader" id="loader">
        <div class="loader-content">
            <div class="spinner"></div>
            <div class="loader-text">Fetching Results... <i class="fas fa-spinner fa-pulse"></i></div>
            <div style="margin-top: 10px; font-size: 0.9rem;">Please wait while we process your request</div>
        </div>
    </div>
    <div class="toast-container" id="toastContainer"></div>
    <div class="fab" onclick="window.scrollTo({top: 0, behavior: 'smooth'})" data-tooltip="Back to Top">
        <i class="fas fa-arrow-up"></i>
    </div>
    
    <div class="glass-container">
        {% block content %}{% endblock %}
    </div>
    
    <script>
        // Particles.js Configuration
        particlesJS("particles-js", {
            "particles": {
                "number": { "value": 80, "density": { "enable": true, "value_area": 800 } },
                "color": { "value": "#ffffff" },
                "shape": { "type": "circle" },
                "opacity": { "value": 0.5, "random": true },
                "size": { "value": 3, "random": true },
                "line_linked": { "enable": true, "distance": 150, "color": "#ffffff", "opacity": 0.2, "width": 1 },
                "move": { "enable": true, "speed": 2, "direction": "none", "random": true, "straight": false, "out_mode": "out" }
            },
            "interactivity": {
                "detect_on": "canvas",
                "events": {
                    "onhover": { "enable": true, "mode": "repulse" },
                    "onclick": { "enable": true, "mode": "push" }
                }
            },
            "retina_detect": true
        });
        
        // Animated Background Shapes
        function createShapes() {
            const container = document.getElementById('bgShapes');
            const shapes = ['circle', 'square', 'triangle'];
            for(let i = 0; i < 20; i++) {
                const shape = document.createElement('div');
                shape.className = 'shape';
                const size = Math.random() * 150 + 50;
                shape.style.width = size + 'px';
                shape.style.height = size + 'px';
                shape.style.left = Math.random() * 100 + '%';
                shape.style.top = Math.random() * 100 + '%';
                shape.style.animationDelay = Math.random() * 20 + 's';
                shape.style.animationDuration = Math.random() * 20 + 15 + 's';
                shape.style.opacity = Math.random() * 0.3;
                container.appendChild(shape);
            }
        }
        
        // Toast Notifications
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = 'toast';
            const icons = { success: '✓', error: '⚠️', info: 'ℹ️', warning: '⚠️' };
            const icon = icons[type] || '✓';
            const colors = { success: '#28a745', error: '#dc3545', info: '#17a2b8', warning: '#ffc107' };
            toast.style.borderLeft = `4px solid ${colors[type] || '#28a745'}`;
            toast.innerHTML = `<span style="font-size: 20px; color: ${colors[type] || '#28a745'}">${icon}</span><span>${message}</span>`;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.animation = 'slideInRight 0.3s reverse';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        // Loading Control
        function showLoading() {
            document.getElementById('loader').classList.add('active');
        }
        
        function hideLoading() {
            document.getElementById('loader').classList.remove('active');
        }
        
        // Form Submit Handler with Validation
        document.addEventListener('DOMContentLoaded', () => {
            createShapes();
            
            // Animated counter for stats
            const statValues = document.querySelectorAll('.stat-value');
            statValues.forEach(el => {
                const finalValue = el.innerText;
                el.innerText = '0';
                let current = 0;
                const increment = parseInt(finalValue) / 50;
                const timer = setInterval(() => {
                    current += increment;
                    if (current >= parseInt(finalValue)) {
                        el.innerText = finalValue;
                        clearInterval(timer);
                    } else {
                        el.innerText = Math.floor(current);
                    }
                }, 20);
            });
            
            // Auto-hide toasts
            setInterval(() => {
                const toasts = document.querySelectorAll('.toast');
                toasts.forEach(toast => {
                    if(toast.getAttribute('data-timer')) return;
                    toast.setAttribute('data-timer', 'true');
                    setTimeout(() => {
                        toast.style.animation = 'slideInRight 0.3s reverse';
                        setTimeout(() => toast.remove(), 300);
                    }, 3000);
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
    <div class="typed-text" id="typed"></div>
</div>

<div class="card">
    <h2><i class="fas fa-search"></i> Search Results</h2>
    <form id="resultForm" method="GET" action="/view">
        <div class="form-group">
            <label><i class="fas fa-qrcode"></i> Roll Code</label>
            <input type="text" name="rollcode" class="form-control" placeholder="Enter Roll Code" required data-tooltip="Enter your roll code">
        </div>
        
        <div class="form-group">
            <label><i class="fas fa-id-card"></i> Starting Roll Number</label>
            <input type="number" name="rollno" class="form-control" placeholder="Enter Starting Roll Number" required>
        </div>
        
        <div class="form-group">
            <label><i class="fas fa-layer-group"></i> Number of Results <span style="color: #764ba2;">(max 100)</span></label>
            <input type="range" name="count_range" min="1" max="100" value="1" oninput="this.nextElementSibling.value=this.value">
            <input type="number" name="count" class="form-control" value="1" min="1" max="100" style="margin-top: 10px;" oninput="this.previousElementSibling.value=this.value">
        </div>
        
        <div class="form-group">
            <label><i class="fas fa-chart-line"></i> Advanced Options</label>
            <div style="display: flex; gap: 15px; flex-wrap: wrap;">
                <label style="cursor: pointer;"><input type="checkbox" name="stats" value="1"> <i class="fas fa-chart-bar"></i> Show Statistics</label>
                <label style="cursor: pointer;"><input type="checkbox" name="charts" value="1"> <i class="fas fa-chart-pie"></i> Generate Charts</label>
                <label style="cursor: pointer;"><input type="checkbox" name="compare" value="1"> <i class="fas fa-chart-line"></i> Compare Results</label>
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
        <div class="score-card" onclick="showToast('You can fetch up to 100 results at once!', 'info')">
            <i class="fas fa-tachometer-alt fa-2x"></i>
            <div class="value">Bulk Fetch</div>
            <div>Fetch up to 100 results at once</div>
        </div>
        <div class="score-card" onclick="showToast('Real-time statistics and charts available!', 'info')">
            <i class="fas fa-chart-pie fa-2x"></i>
            <div class="value">Analysis</div>
            <div>Real-time statistics & charts</div>
        </div>
        <div class="score-card" onclick="showToast('Download results in CSV or PDF format', 'info')">
            <i class="fas fa-download fa-2x"></i>
            <div class="value">Export</div>
            <div>CSV & PDF export options</div>
        </div>
    </div>
</div>

<script>
    // Typed.js Animation
    var typed = new Typed('#typed', {
        strings: ['Check Your Results Instantly', 'Bihar Board Results 2026', 'Fast & Secure Portal', 'Interactive Dashboard'],
        typeSpeed: 50,
        backSpeed: 30,
        loop: true
    });
    
    // Slider synchronization
    const rangeInput = document.querySelector('input[name="count_range"]');
    const numberInput = document.querySelector('input[name="count"]');
    
    rangeInput.addEventListener('input', function() {
        numberInput.value = this.value;
    });
    
    numberInput.addEventListener('input', function() {
        rangeInput.value = this.value;
    });
    
    // Form validation
    document.getElementById('resultForm').addEventListener('submit', function(e) {
        const rollcode = document.querySelector('input[name="rollcode"]').value;
        const rollno = document.querySelector('input[name="rollno"]').value;
        
        if(!rollcode || !rollno) {
            e.preventDefault();
            showToast('Please fill all required fields!', 'error');
            return false;
        }
        
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
        <p class="subtitle">Fetch completed • """ + str(len(results)) + """ records found</p>
        <div class="typed-text" id="typed"></div>
    </div>
    
    <div class="card">
        <div class="tabs">
            <button class="tab active" onclick="switchTab('table')"><i class="fas fa-table"></i> Table View</button>
            <button class="tab" onclick="switchTab('stats')"><i class="fas fa-chart-bar"></i> Statistics</button>
            <button class="tab" onclick="switchTab('cards')"><i class="fas fa-id-card"></i> Card View</button>
        </div>
        
        <div id="table-tab" class="tab-content active">
            <div style="margin-bottom: 20px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                <a href="/download"><button class="btn btn-primary" onclick="showToast('Downloading CSV...', 'info')"><i class="fas fa-download"></i> Download CSV</button></a>
                <a href="/pdf"><button class="btn btn-primary" onclick="showToast('Generating PDF...', 'info')"><i class="fas fa-file-pdf"></i> Download PDF</button></a>
                <button class="btn btn-outline" onclick="window.print(); showToast('Printing...', 'info')"><i class="fas fa-print"></i> Print</button>
                <button class="btn btn-outline" onclick="copyTableToClipboard()"><i class="fas fa-copy"></i> Copy Table</button>
            </div>
            <div class="result-table-wrapper">
                <table class="result-table" id="resultTable">
                    <thead>
                        <tr>
                            <th onclick="sortTable(0)"># <i class="fas fa-sort"></i></th>
                            <th onclick="sortTable(1)">Name <i class="fas fa-sort"></i></th>
                            <th onclick="sortTable(2)">Father's Name <i class="fas fa-sort"></i></th>
                            <th onclick="sortTable(3)">Roll No <i class="fas fa-sort"></i></th>
                            <th>School</th>
                            <th onclick="sortTable(5)">Total <i class="fas fa-sort"></i></th>
                            <th onclick="sortTable(6)">Result <i class="fas fa-sort"></i></th>
                            <th>CGPA</th>
                            """ + "".join([f"<th>{SUBJECT_FULL_NAMES[s]}</th>" for s in SUBJECTS]) + """
                        </tr>
                    </thead>
                    <tbody>
    """
    
    for idx, r in enumerate(results, 1):
        result_class = 'pass-badge' if r.get('result') == 'PASS' else 'fail-badge'
        html += f"""
            <tr>
                <td>{idx}</td>
                <td><strong>{r.get('name', 'N/A')}</strong></td>
                <td>{r.get('father', 'N/A')}</td>
                <td>{r.get('roll_no', 'N/A')}</td>
                <td>{r.get('school', 'N/A')[:30]}</td>
                <td><strong>{r.get('total', 'N/A')}</strong></td>
                <td><span class="{result_class}">{r.get('result', 'N/A')}</span></td>
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
                <div class="stat-item" onclick="showToast('Total students fetched', 'info')">
                    <div class="stat-label"><i class="fas fa-users"></i> Total Students</div>
                    <div class="stat-value">{stats.get('total', 0)}</div>
                </div>
                <div class="stat-item" onclick="showToast('Successfully passed students', 'success')">
                    <div class="stat-label"><i class="fas fa-check-circle"></i> Passed</div>
                    <div class="stat-value" style="color: #28a745;">{stats.get('passed', 0)}</div>
                </div>
                <div class="stat-item" onclick="showToast('Failed students', 'error')">
                    <div class="stat-label"><i class="fas fa-times-circle"></i> Failed</div>
                    <div class="stat-value" style="color: #dc3545;">{stats.get('failed', 0)}</div>
                </div>
                <div class="stat-item" onclick="showToast('Overall pass percentage', 'info')">
                    <div class="stat-label"><i class="fas fa-percent"></i> Pass Percentage</div>
                    <div class="stat-value">{stats.get('pass_percentage', 0)}%</div>
                </div>
            </div>
        """
        
        if show_charts:
            html += """
            <canvas id="resultChart" style="max-height: 400px; margin-top: 30px;"></canvas>
            <canvas id="subjectChart" style="max-height: 400px; margin-top: 30px;"></canvas>
            <script>
                new Chart(document.getElementById('resultChart'), {
                    type: 'doughnut',
                    data: {
                        labels: ['Passed', 'Failed'],
                        datasets: [{
                            data: [""" + str(stats.get('passed', 0)) + ", " + str(stats.get('failed', 0)) + """],
                            backgroundColor: ['#28a745', '#dc3545'],
                            borderWidth: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'bottom' },
                            title: { display: true, text: 'Result Distribution' }
                        }
                    }
                });
            </script>
            """
    else:
        html += "<div style='text-align: center; padding: 40px;'><i class='fas fa-chart-line fa-3x' style='color: #764ba2;'></i><p style='margin-top: 20px;'>Enable statistics to view detailed analysis</p></div>"
    
    html += """
        </div>
        
        <div id="cards-tab" class="tab-content">
            <div class="score-grid">
    """
    
    for r in results[:20]:
        result_badge = '✅ PASS' if r.get('result') == 'PASS' else '❌ FAIL'
        html += f"""
            <div class="score-card" style="background: white; color: #333; border: 1px solid #e0e0e0;" onclick="showToast('{r.get('name', 'N/A')} - {r.get('total', 'N/A')}', 'info')">
                <i class="fas fa-user-graduate" style="font-size: 2rem; color: #764ba2;"></i>
                <div class="value" style="font-size: 1.2rem;">{r.get('name', 'N/A')}</div>
                <div><i class="fas fa-id-card"></i> Roll: {r.get('roll_no', 'N/A')}</div>
                <div><i class="fas fa-chart-line"></i> Total: <strong>{r.get('total', 'N/A')}</strong></div>
                <div><i class="fas fa-flag-checkered"></i> Result: {result_badge}</div>
                <div><i class="fas fa-chart-simple"></i> CGPA: {r.get('cgpa', 'N/A')}</div>
            </div>
        """
    
    html += """
            </div>
            <div style="text-align: center; margin-top: 20px;">
                <small><i class="fas fa-eye"></i> Showing first 20 results • Click on cards for details</small>
            </div>
        </div>
    </div>
    
    <script>
        var typed = new Typed('#typed', {
            strings: ['Viewing Results', 'Analysis Complete', 'Export Available', 'Share with Friends'],
            typeSpeed: 50,
            backSpeed: 30,
            loop: true
        });
        
        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
            document.querySelector(`.tab[onclick="switchTab('${tabName}')"]`).classList.add('active');
            document.getElementById(`${tabName}-tab`).classList.add('active');
            showToast(`Switched to ${tabName} view`, 'info');
        }
        
        function sortTable(column) {
            const table = document.getElementById('resultTable');
            const tbody = table.getElementsByTagName('tbody')[0];
            const rows = Array.from(tbody.rows);
            const isAscending = table.getAttribute('data-sort') === column.toString() ? 
                table.getAttribute('data-order') !== 'asc' : true;
            
            rows.sort((a, b) => {
                let aVal = a.cells[column].innerText;
                let bVal = b.cells[column].innerText;
                
                if(column === 0 || column === 3 || column === 5) {
                    aVal = parseInt(aVal) || 0;
                    bVal = parseInt(bVal) || 0;
                }
                
                if(isAscending) {
                    return aVal > bVal ? 1 : -1;
                } else {
                    return aVal < bVal ? 1 : -1;
                }
            });
            
            rows.forEach(row => tbody.appendChild(row));
            table.setAttribute('data-sort', column);
            table.setAttribute('data-order', isAscending ? 'asc' : 'desc');
            showToast(`Sorted by column ${column + 1}`, 'info');
        }
        
        function copyTableToClipboard() {
            const table = document.getElementById('resultTable');
            const range = document.createRange();
            range.selectNode(table);
            window.getSelection().removeAllRanges();
            window.getSelection().addRange(range);
            document.execCommand('copy');
            window.getSelection().removeAllRanges();
            showToast('Table copied to clipboard!', 'success');
        }
        
        // Search functionality
        const searchInput = document.createElement('input');
        searchInput.placeholder = '🔍 Search results...';
        searchInput.className = 'form-control';
        searchInput.style.marginBottom = '20px';
        searchInput.style.width = '300px';
        document.querySelector('#table-tab .result-table-wrapper').insertBefore(searchInput, document.querySelector('#resultTable'));
        
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const rows = document.querySelectorAll('#resultTable tbody tr');
            rows.forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
            showToast(`Searching: "${searchTerm}"`, 'info');
        });
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
        
        escaped_row = []
        for x in row:
            str_x = str(x)
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
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cached_results": len(CACHE.get("data", []))
    })

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "False").lower() == "true"
    
    print("=" * 50)
    print("BSEB Result Portal Starting...")
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=port, debug=debug)
