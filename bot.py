from flask import Flask, request, render_template_string
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

    # ================= PARSE TABLE =================
    for row in soup.find_all("tr"):
        cols = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]

        if len(cols) < 2:
            continue

        key = cols[0].lower().strip()
        value = cols[-1].strip()

        # ---------------- BASIC INFO ----------------
        if "student" in key and "name" in key:
            data["name"] = value

        elif "father" in key:
            data["father"] = value

        elif "school" in key:
            data["school"] = value

        elif "aggregate" in key:
            data["total"] = value

        # ---------------- IGNORE NOISE ----------------
        elif any(x in key for x in [
            "print", "back", "copy", "web",
            "bihar school examination board",
            "intermediate", "result",
            "roll code", "roll number",
            "registration",
            "grace", "swapping", "regulation"
        ]):
            continue

        # ---------------- SUBJECTS ----------------
        elif len(cols) >= 5:
            subject_raw = cols[0].strip()

            norm = normalize_subject(subject_raw)

            if norm:
                data["subjects"][norm] = value

    return data


# ================= HOME PAGE =================
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
    box-shadow:0 10px 20px rgba(0,0,0,0.2);
}

input,select,button{
    width:90%;
    padding:10px;
    margin:10px;
    border:1px solid #ddd;
    border-radius:6px;
}

button{
    background:#2c3e50;
    color:white;
    cursor:pointer;
}

button:hover{
    background:#1a252f;
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


# ================= RESULT PAGE =================
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

    # ================= HTML =================
    html = """
<html>
<head>
<style>
body{
    font-family:Arial;
    background:#f4f6f9;
    padding:20px;
}

h2{
    text-align:center;
}

table{
    width:100%;
    border-collapse:collapse;
    background:white;
    box-shadow:0 5px 10px rgba(0,0,0,0.1);
}

th,td{
    border:1px solid #ddd;
    padding:8px;
    text-align:center;
    font-size:13px;
}

th{
    background:#2c3e50;
    color:white;
    position:sticky;
    top:0;
}

tr:nth-child(even){
    background:#f9f9f9;
}

tr:hover{
    background:#f1f1f1;
}
</style>
</head>

<body>

<h2>BSEB Clean Result Sheet</h2>

<table>

<tr>
<th>Name</th>
<th>Father</th>
<th>Roll No</th>
<th>School</th>
<th>Total Marks</th>
"""

    # ================= SUBJECT HEADERS =================
    for s in SUBJECTS:
        html += f"<th>{s.title()}</th>"

    html += "</tr>"

    # ================= ROWS =================
    for r in results:
        html += "<tr>"

        html += f"<td>{r['name']}</td>"
        html += f"<td>{r['father']}</td>"
        html += f"<td>{r['roll_no']}</td>"
        html += f"<td>{r['school']}</td>"
        html += f"<td>{r['total']}</td>"

        for s in SUBJECTS:
            value = r["subjects"].get(s, "")
            html += f"<td>{value}</td>"

        html += "</tr>"

    html += """
</table>

</body>
</html>
"""

    return html


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
