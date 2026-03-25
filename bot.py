from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

BASE_URL = "https://www.bsebexam.com"

session = requests.Session()


# -----------------------------
# GET CAPTCHA + TOKEN PAGE
# -----------------------------
def get_initial_page():
    url = f"{BASE_URL}/"
    r = session.get(url, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    token = soup.find("input", {"name": "__RequestVerificationToken"})
    token_value = token["value"] if token else None

    return token_value


# -----------------------------
# FETCH RESULT
# -----------------------------
def fetch_result(rollcode, rollno):
    token = get_initial_page()

    if not token:
        return {"error": "Token not found"}

    url = f"{BASE_URL}/Result/GetResult"

    payload = {
        "rollcode": rollcode,
        "rollno": rollno,
        "__RequestVerificationToken": token
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/"
    }

    res = session.post(url, data=payload, headers=headers, timeout=20)

    soup = BeautifulSoup(res.text, "html.parser")

    # -----------------------------
    # PARSE RESULT (SAFE DEFAULT)
    # -----------------------------
    result = {
        "roll_no": rollno,
        "rollcode": rollcode,
        "student_name": None,
        "aggregate_marks": None,
        "subjects": {}
    }

    # Example parsing logic (adjust if HTML changes)
    name_tag = soup.find("span", {"id": "studentName"})
    if name_tag:
        result["student_name"] = name_tag.text.strip()

    # Table parsing (generic)
    rows = soup.find_all("tr")
    for row in rows:
        cols = [c.text.strip() for c in row.find_all("td")]

        if len(cols) >= 2:
            subject = cols[0]
            mark = cols[1]
            result["subjects"][subject] = mark

    # Aggregate marks fallback search
    if "Total" in res.text:
        result["aggregate_marks"] = "Found"

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

    data = fetch_result(rollcode, rollno)
    return jsonify(data)


# -----------------------------
# BATCH API
# -----------------------------
@app.route("/batch")
def batch():
    rollcode = request.args.get("rollcode")
    start = int(request.args.get("start"))
    count = int(request.args.get("count", 1))

    results = []

    for i in range(start, start + count):
        rollno = str(i)
        try:
            data = fetch_result(rollcode, rollno)
            results.append(data)
        except Exception as e:
            results.append({
                "roll_no": rollno,
                "error": str(e)
            })

    return jsonify(results)


# -----------------------------
# HEALTH CHECK (IMPORTANT FOR RAILWAY)
# -----------------------------
@app.route("/")
def home():
    return "BSEB Scraper Running"


# -----------------------------
# RAILWAY ENTRYPOINT SAFE RUN
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
