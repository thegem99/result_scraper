from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup
import os
import time

app = Flask(__name__)

BASE_URL = "https://www.bsebexam.com"

# -----------------------------
# SESSION + TOKEN
# -----------------------------
def get_session():
    return requests.Session()

def get_token(session):
    res = session.get(BASE_URL + "/", timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    token = soup.find("input", {"name": "__RequestVerificationToken"})
    return token.get("value") if token else None


# -----------------------------
# FETCH RESULT
# -----------------------------
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

    text = soup.get_text(" ", strip=True)

    # -----------------------------
    # BASIC EXTRACTION (SAFE)
    # -----------------------------
    if "Name" in text:
        data["name"] = text

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cols = [c.text.strip() for c in row.find_all(["td", "th"])]

            if len(cols) == 2:
                k, v = cols

                k_low = k.lower()

                if "father" in k_low:
                    data["father"] = v
                elif "school" in k_low:
                    data["school"] = v
                elif "total" in k_low:
                    data["total"] = v
                else:
                    data["subjects"][k] = v

    return data


# -----------------------------
# HOME PAGE
# -----------------------------
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Result Portal</title>
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
    width:350px;
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
    background:black;
    color:white;
    border:none;
    cursor:pointer;
}
</style>
</head>

<body>

<div class="box">
<h2>BSEB Result 2026</h2>

<form action="/view" method="get">

<input name="rollcode" placeholder="Roll Code" required>
<input name="rollno" placeholder="Roll Number" required>

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


# -----------------------------
# RESULT TABLE PAGE
# -----------------------------
@app.route("/view")
def view():
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")
    count = int(request.args.get("count", 1))

    session = get_session()
    token = get_token(session)

    results = []
    all_subjects = set()

    # -----------------------------
    # FETCH DATA
    # -----------------------------
    for i in range(count):
        rn = str(int(rollno) + i)

        data = fetch_result(session, token, rollcode, rn)
        results.append(data)

        for s in data["subjects"]:
            all_subjects.add(s)

        time.sleep(0.3)

    subjects = sorted(list(all_subjects))

    # -----------------------------
    # TABLE UI
    # -----------------------------
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
</style>
</head>

<body>

<h2>BSEB Result Sheet</h2>

<table>

<tr>
<th>Name</th>
<th>Father Name</th>
<th>Roll No</th>
<th>School</th>
<th>Total Marks</th>
"""

    # SUBJECT HEADERS
    for s in subjects:
        html += f"<th>{s}</th>"

    html += "</tr>"

    # -----------------------------
    # ROWS
    # -----------------------------
    for r in results:
        html += "<tr>"

        html += f"<td>{r['name']}</td>"
        html += f"<td>{r['father']}</td>"
        html += f"<td>{r['roll_no']}</td>"
        html += f"<td>{r['school']}</td>"
        html += f"<td>{r['total']}</td>"

        for s in subjects:
            html += f"<td>{r['subjects'].get(s, '')}</td>"

        html += "</tr>"

    html += """
</table>

</body>
</html>
"""

    return html


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
