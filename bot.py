from flask import Flask, request, render_template_string, Response
import requests
from bs4 import BeautifulSoup
import os
import time
from io import BytesIO

# PDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

BASE_URL = "https://www.bsebexam.com"

# cache (avoids double scraping)
CACHE = {}

# ================= SESSION =================
def get_session():
    return requests.Session()

# ================= TOKEN =================
def get_token(session):
    res = session.get(BASE_URL + "/", timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    token = soup.find("input", {"name": "__RequestVerificationToken"})
    return token.get("value") if token else None

# ================= SUBJECT NORMALIZER =================
def normalize_subject(name):
    name = name.lower().strip()

    if "math" in name: return "mathematics"
    if "bio" in name: return "biology"
    if "physic" in name: return "physics"
    if "chem" in name: return "chemistry"
    if "english" in name: return "english"
    if "hindi" in name: return "hindi"

    return None

# ================= SUBJECT ORDER =================
SUBJECTS = ["english","hindi","physics","chemistry","mathematics","biology"]

# ================= FETCH RESULT =================
def fetch_result(session, token, rollcode, rollno):
    url = BASE_URL + "/Result/GetResult"

    payload = {
        "rollcode": rollcode,
        "rollno": rollno,
        "captcha": "123456",
        "__RequestVerificationToken": token
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    res = session.post(url, data=payload, headers=headers, timeout=20)
    soup = BeautifulSoup(res.text, "html.parser")

    data = {
        "name":"",
        "father":"",
        "roll_no":rollno,
        "school":"",
        "total":"",
        "subjects":{}
    }

    for row in soup.find_all("tr"):
        cols = [c.get_text(" ", strip=True) for c in row.find_all(["td","th"])]

        if len(cols) < 2:
            continue

        key = cols[0].lower().strip()
        value = cols[-1].strip()

        if "student" in key and "name" in key:
            data["name"] = value

        elif "father" in key:
            data["father"] = value

        elif "school" in key:
            data["school"] = value

        elif "aggregate" in key:
            data["total"] = value

        elif len(cols) >= 5:
            norm = normalize_subject(cols[0])
            if norm:
                data["subjects"][norm] = value

    return data

# ================= HOME =================
@app.route("/")
def home():
    return render_template_string("""
<html>
<head>
<title>BSEB Result Portal</title>
<style>
body{
    font-family:Arial;
    background:linear-gradient(135deg,#4facfe,#00f2fe);
    display:flex;
    justify-content:center;
    align-items:center;
    height:100vh;
}

/* Tilt watermark */
body::before{
    content:"BSEB RESULT";
    position:absolute;
    font-size:80px;
    color:rgba(255,255,255,0.15);
    transform:rotate(-30deg);
}

.box{
    background:rgba(255,255,255,0.2);
    backdrop-filter:blur(10px);
    padding:30px;
    border-radius:15px;
    text-align:center;
    color:white;
}

input,button{
    width:100%;
    padding:10px;
    margin:10px 0;
    border:none;
    border-radius:8px;
}

button{
    background:#2c3e50;
    color:white;
    cursor:pointer;
}
</style>
</head>
<body>

<div class="box">
<h2>🎓 BSEB Result 2026</h2>

<form action="/view">
<input name="rollcode" placeholder="Roll Code" required>
<input name="rollno" placeholder="Starting Roll Number" required>
<input name="count" value="1" placeholder="Count (max 50)">
<button>Get Result</button>
</form>

</div>
</body>
</html>
""")

# ================= VIEW =================
@app.route("/view")
def view():
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")

    count = min(int(request.args.get("count", 1)), 50)

    session = get_session()
    token = get_token(session)

    results = []

    for i in range(count):
        rn = str(int(rollno) + i)

        try:
            result = fetch_result(session, token, rollcode, rn)
        except:
            result = {
                "name":"Error",
                "father":"",
                "roll_no":rn,
                "school":"",
                "total":"",
                "subjects":{}
            }

        results.append(result)
        time.sleep(0.4)

    CACHE["data"] = results

    html = """
    <html>
    <head>
    <style>
    body{font-family:Arial;background:#f4f6f9;padding:20px;}
    table{width:100%;border-collapse:collapse;background:white;}
    th,td{border:1px solid #ddd;padding:8px;text-align:center;}
    th{background:#2c3e50;color:white;}
    .btn{padding:10px 20px;margin:5px;border:none;color:white;border-radius:6px;}
    .csv{background:#27ae60;}
    .pdf{background:#e74c3c;}
    </style>
    </head>
    <body>

    <h2 align="center">Result Sheet</h2>

    <div align="center">
    <a href="/download"><button class="btn csv">Download CSV</button></a>
    <a href="/pdf"><button class="btn pdf">Download PDF</button></a>
    </div>
    """

    html += "<table><tr>"
    headers = ["Name","Father","Roll No","School","Total"] + [s.title() for s in SUBJECTS]

    for h in headers:
        html += f"<th>{h}</th>"
    html += "</tr>"

    for r in results:
        html += "<tr>"
        html += f"<td>{r['name']}</td>"
        html += f"<td>{r['father']}</td>"
        html += f"<td>{r['roll_no']}</td>"
        html += f"<td>{r['school']}</td>"
        html += f"<td>{r['total']}</td>"

        for s in SUBJECTS:
            html += f"<td>{r['subjects'].get(s,'')}</td>"

        html += "</tr>"

    html += "</table></body></html>"
    return html

# ================= CSV =================
@app.route("/download")
def download():
    results = CACHE.get("data", [])

    def generate():
        header = ["Name","Father","Roll No","School","Total"] + [s.title() for s in SUBJECTS]
        yield ",".join(header) + "\n"

        for r in results:
            row = [r["name"],r["father"],r["roll_no"],r["school"],r["total"]]
            for s in SUBJECTS:
                row.append(r["subjects"].get(s,""))

            yield ",".join(f'"{x}"' for x in row) + "\n"

    return Response(generate(),
        mimetype="text/csv",
        headers={"Content-Disposition":"attachment; filename=results.csv"}
    )

# ================= PDF =================
@app.route("/pdf")
def pdf():
    results = CACHE.get("data", [])

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    width, height = letter
    y = height - 40

    # Title
    p.setFont("Helvetica-Bold", 14)
    p.drawString(200, y, "BSEB Result Sheet")
    y -= 25

    # Headers
    p.setFont("Helvetica-Bold", 8)
    headers = ["Name","Father","Roll","Total"] + [s[:4].upper() for s in SUBJECTS]

    x_positions = [40, 120, 200, 250, 300, 340, 380, 420, 460, 500]

    for i, h in enumerate(headers):
        if i < len(x_positions):
            p.drawString(x_positions[i], y, h)

    y -= 15

    # Data rows
    p.setFont("Helvetica", 7)

    for r in results:
        if y < 40:
            p.showPage()
            y = height - 40

        row = [
            r["name"][:10],
            r["father"][:10],
            r["roll_no"],
            r["total"]
        ]

        for s in SUBJECTS:
            row.append(r["subjects"].get(s,"")[:5])

        for i, val in enumerate(row):
            if i < len(x_positions):
                p.drawString(x_positions[i], y, str(val))

        y -= 15

    p.save()
    buffer.seek(0)

    return Response(buffer,
        mimetype='application/pdf',
        headers={"Content-Disposition":"attachment; filename=results.pdf"}
    )

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
