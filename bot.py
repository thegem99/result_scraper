from flask import Flask, request, render_template_string, Response
import requests
from bs4 import BeautifulSoup
import os
import time
from io import BytesIO

app = Flask(__name__)

BASE_URL = "https://www.bsebexam.com"

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

    data = {"name":"","father":"","roll_no":rollno,"school":"","total":"","subjects":{}}

    for row in soup.find_all("tr"):
        cols = [c.get_text(" ", strip=True) for c in row.find_all(["td","th"])]
        if len(cols) < 2: continue

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
    height:100vh;
    display:flex;
    align-items:center;
    justify-content:center;
}

/* Tilted watermark */
body::before{
    content:"BSEB RESULT";
    position:absolute;
    font-size:80px;
    color:rgba(255,255,255,0.1);
    transform:rotate(-30deg);
    top:30%;
    left:10%;
}

/* Glass box */
.box{
    background:rgba(255,255,255,0.2);
    backdrop-filter:blur(10px);
    padding:30px;
    border-radius:15px;
    text-align:center;
    color:white;
    width:350px;
}

/* Inputs */
input,select,button{
    width:100%;
    padding:10px;
    margin:10px 0;
    border:none;
    border-radius:8px;
}

/* Button */
button{
    background:#2c3e50;
    color:white;
    font-weight:bold;
    cursor:pointer;
}

button:hover{
    background:#000;
}
</style>
</head>

<body>

<div class="box">
<h2>🎓 BSEB Result 2026</h2>

<form action="/view" method="get">
<input name="rollcode" placeholder="Roll Code" required>
<input name="rollno" placeholder="Starting Roll Number" required>

<select name="mode" id="mode" onchange="toggle()">
<option value="single">Single</option>
<option value="batch">Batch</option>
</select>

<input name="count" id="count" value="1">

<button type="submit">Get Result</button>
</form>
</div>

<script>
function toggle(){
    let m = document.getElementById("mode").value;
    let c = document.getElementById("count");
    if(m==="single"){c.value=1;c.readOnly=true;}
    else{c.readOnly=false;}
}
toggle();
</script>

</body>
</html>
""")

# ================= VIEW =================
@app.route("/view")
def view():
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")
    count = int(request.args.get("count", 1))

    session = get_session()
    token = get_token(session)

    results = []
    for i in range(count):
        rn = str(int(rollno) + i)
        results.append(fetch_result(session, token, rollcode, rn))
        time.sleep(0.2)

    html = """
<html>
<head>
<style>
body{
    font-family:Arial;
    background:#eef2f3;
    padding:20px;
}

body::before{
    content:"BSEB";
    position:fixed;
    font-size:120px;
    color:rgba(0,0,0,0.05);
    transform:rotate(-30deg);
    top:40%;
    left:20%;
}

table{
    width:100%;
    border-collapse:collapse;
    background:white;
    border-radius:10px;
    overflow:hidden;
}

th,td{
    padding:10px;
    border:1px solid #ddd;
}

th{
    background:#2c3e50;
    color:white;
}

tr:hover{
    background:#f1f1f1;
}

.btn{
    padding:10px 20px;
    border:none;
    border-radius:8px;
    margin:5px;
    cursor:pointer;
    color:white;
}

.csv{background:#27ae60;}
.pdf{background:#e74c3c;}
</style>
</head>
<body>

<h2 align="center">📊 Result Sheet</h2>
"""

    # Buttons
    html += f"""
<div style="text-align:center;">
<a href="/download?rollcode={rollcode}&rollno={rollno}&count={count}">
<button class="btn csv">Download CSV</button></a>

<a href="/pdf?rollcode={rollcode}&rollno={rollno}&count={count}">
<button class="btn pdf">Download PDF</button></a>
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
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")
    count = int(request.args.get("count", 1))

    session = get_session()
    token = get_token(session)

    results = []
    for i in range(count):
        rn = str(int(rollno) + i)
        results.append(fetch_result(session, token, rollcode, rn))
        time.sleep(0.2)

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
        headers={"Content-Disposition":"attachment; filename=results.csv"})

# ================= PDF =================
@app.route("/pdf")
def pdf():
    html = "<h2>BSEB Result Export</h2><p>Use browser Print → Save as PDF</p>"
    return Response(html, mimetype="text/html")

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
