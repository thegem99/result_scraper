from flask import Flask, request, jsonify, render_template_string
import requests
from bs4 import BeautifulSoup
import os
import time

app = Flask(__name__)

BASE_URL = "https://www.bsebexam.com"

# -----------------------------
# CREATE SESSION
# -----------------------------
def get_session():
    return requests.Session()


# -----------------------------
# GET TOKEN
# -----------------------------
def get_token(session):
    res = session.get(BASE_URL + "/", timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")

    token_input = soup.find("input", {"name": "__RequestVerificationToken"})
    if token_input:
        return token_input.get("value")

    return None


# -----------------------------
# FETCH SINGLE RESULT
# -----------------------------
def fetch_result(session, token, rollcode, rollno):
    url = BASE_URL + "/Result/GetResult"

    payload = {
        "rollcode": rollcode,
        "rollno": rollno,
        "captcha": "123456",  # dummy (frontend-only captcha)
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

    result = {
        "roll_no": rollno,
        "rollcode": rollcode,
        "status": "success",
        "student_name": None,
        "subjects": {}
    }

    # Parse tables
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")

        for row in rows:
            cols = [c.text.strip() for c in row.find_all(["td", "th"])]

            if len(cols) >= 2:
                result["subjects"][cols[0]] = cols[1]

    if len(result["subjects"]) == 0:
        result["status"] = "no_data"

    return result


# -----------------------------
# SINGLE RESULT API
# -----------------------------
@app.route("/result")
def result():
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")

    if not rollcode or not rollno:
        return jsonify({"error": "Missing parameters"}), 400

    session = get_session()
    token = get_token(session)

    if not token:
        return jsonify({"error": "Token fetch failed"}), 500

    data = fetch_result(session, token, rollcode, rollno)

    return jsonify(data)


# -----------------------------
# BATCH API
# -----------------------------
@app.route("/batch")
def batch():
    rollcode = request.args.get("rollcode")
    start = request.args.get("start")
    count = int(request.args.get("count", 1))

    if not rollcode or not start:
        return jsonify({"error": "Missing parameters"}), 400

    start = int(start)

    session = get_session()
    token = get_token(session)

    if not token:
        return jsonify({"error": "Token fetch failed"}), 500

    results = []

    for i in range(start, start + count):
        rollno = str(i)

        try:
            data = fetch_result(session, token, rollcode, rollno)
            results.append(data)

            time.sleep(0.5)  # avoid blocking

        except Exception as e:
            results.append({
                "roll_no": rollno,
                "status": "error",
                "error": str(e)
            })

    return jsonify(results)


# -----------------------------
# WEB UI
# -----------------------------
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>BSEB Result Checker</title>
    <style>
        body {
            font-family: Arial;
            background: linear-gradient(135deg, #667eea, #764ba2);
            text-align: center;
            padding: 40px;
            color: white;
        }
        .box {
            background: white;
            color: black;
            padding: 20px;
            border-radius: 10px;
            width: 350px;
            margin: auto;
        }
        input, button {
            width: 90%;
            padding: 10px;
            margin: 10px;
        }
        button {
            background: black;
            color: white;
            cursor: pointer;
        }
        #result {
            margin-top: 20px;
            text-align: left;
        }
    </style>
</head>
<body>

<div class="box">
    <h2>BSEB Result 2026</h2>

    <input id="rollcode" placeholder="Roll Code">
    <input id="rollno" placeholder="Roll Number">

    <button onclick="getResult()">Get Result</button>

    <div id="result"></div>
</div>

<script>
function getResult() {
    let rollcode = document.getElementById("rollcode").value;
    let rollno = document.getElementById("rollno").value;

    fetch(`/result?rollcode=${rollcode}&rollno=${rollno}`)
    .then(res => res.json())
    .then(data => {
        let html = "<h3>Result:</h3>";

        if(data.status !== "success"){
            html += "<p>No data found</p>";
        } else {
            html += `<p><b>Roll No:</b> ${data.roll_no}</p>`;
            html += `<p><b>Roll Code:</b> ${data.rollcode}</p>`;

            html += "<h4>Subjects:</h4>";

            for(let key in data.subjects){
                html += `<p>${key}: ${data.subjects[key]}</p>`;
            }
        }

        document.getElementById("result").innerHTML = html;
    });
}
</script>

</body>
</html>
""")


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
