from flask import Flask, request, render_template_string, Response
import requests
from bs4 import BeautifulSoup
import os
import time

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

    if "math" in name:
        return "mathematics"
    if "bio" in name:
        return "biology"
    if "physic" in name:
        return "physics"
    if "chem" in name:
        return "chemistry"
    if "english" in name:
        return "english"
    if "hindi" in name:
        return "hindi"

    return None

# ================= SUBJECT ORDER =================
SUBJECTS = [
    "english",
    "hindi",
    "physics",
    "chemistry",
    "mathematics",
    "biology"
]

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
        "name": "",
        "father": "",
        "roll_no": rollno,
        "school": "",
        "total": "",
        "subjects": {}
    }

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

        elif "school" in key:
            data["school"] = value

        elif "aggregate" in key:
            data["total"] = value

        elif any(x in key for x in [
            "print", "back", "copy", "web",
            "bihar school examination board",
            "intermediate", "result",
            "roll code", "roll number",
            "registration",
            "grace", "swapping", "regulation"
        ]):
            continue

        elif len(cols) >= 5:
            subject_raw = cols[0].strip()
            norm = normalize_subject(subject_raw)
            if norm:
                data["subjects"][norm] = value

    return data

# ================= HOME =================
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>BSEB Result Portal</title>
<style>
body{
    font-family:Arial;
    background:linear-gradient(135deg,#667eea,#764ba2);
    text-align:center;
    color:white;
}
.box{
    background:white;
    color:black;
    width:380px;
    margin:50px auto;
    padding:20px;
    border-radius:12px;
}
input,select,button{
    width:90%;
    padding:10px;
    margin:10px;
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
<h2>BSEB Result 2026</h2>

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
    let mode = document.getElementById("mode").value;
    let c = document.getElementById("count");

    if(mode === "single"){
        c.value = 1;
        c.readOnly = true;
    } else {
        c.readOnly = false;
    }
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
body{font-family:Arial;background:#f4f6f9;padding:20px;}
table{width:100%;border-collapse:collapse;background:white;}
th,td{border:1px solid #ddd;padding:8px;text-align:center;}
th{background:#2c3e50;color:white;}
</style>
</head>
<body>

<h2>BSEB Clean Result Sheet</h2>
"""

    # ===== DOWNLOAD BUTTON =====
    html += f"""
<div style="text-align:center;margin-bottom:15px;">
<a href="/download?rollcode={rollcode}&rollno={rollno}&count={count}">
<button style="padding:10px 20px;background:#27ae60;color:white;border:none;border-radius:6px;">
Download CSV
</button>
</a>
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

# ================= DOWNLOAD CSV =================
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
            row = [
                r["name"],
                r["father"],
                r["roll_no"],
                r["school"],
                r["total"]
            ]

            for s in SUBJECTS:
                row.append(r["subjects"].get(s, ""))

            # safer CSV (handles commas)
            yield ",".join(f'"{x}"' for x in row) + "\n"

    return Response(generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"}
    )

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
