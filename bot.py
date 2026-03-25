from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

BASE_URL = "https://www.bsebexam.com"

# -----------------------------
# CREATE SESSION
# -----------------------------
def get_session():
    return requests.Session()


# -----------------------------
# GET TOKEN + COOKIE
# -----------------------------
def get_token(session):
    url = BASE_URL + "/"
    res = session.get(url, timeout=15)

    soup = BeautifulSoup(res.text, "html.parser")

    token_input = soup.find("input", {"name": "__RequestVerificationToken"})
    if not token_input:
        return None

    return token_input.get("value")


# -----------------------------
# FETCH RESULT
# -----------------------------
def fetch_result(rollcode, rollno):
    session = get_session()

    token = get_token(session)
    if not token:
        return {
            "roll_no": rollno,
            "status": "failed",
            "error": "Token not found"
        }

    url = BASE_URL + "/Result/GetResult"

    payload = {
        "rollcode": rollcode,
        "rollno": rollno,
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
        "aggregate_marks": None,
        "subjects": {}
    }

    # -----------------------------
    # PARSE STUDENT NAME (try multiple ways)
    # -----------------------------
    possible_name = soup.find(text=lambda x: x and "Name" in x)
    if possible_name:
        result["student_name"] = possible_name.strip()

    # -----------------------------
    # PARSE TABLE DATA
    # -----------------------------
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")

        for row in rows:
            cols = [c.text.strip() for c in row.find_all(["td", "th"])]

            if len(cols) >= 2:
                key = cols[0]
                value = cols[1]

                # Try detect subjects
                if key.lower() not in ["roll code", "roll no"]:
                    result["subjects"][key] = value

    # -----------------------------
    # CHECK IF NO DATA FOUND
    # -----------------------------
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
        return jsonify({"error": "Missing rollcode or rollno"}), 400

    data = fetch_result(rollcode, rollno)
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

    results = []

    for i in range(start, start + count):
        rollno = str(i)

        try:
            data = fetch_result(rollcode, rollno)
            results.append(data)
        except Exception as e:
            results.append({
                "roll_no": rollno,
                "status": "error",
                "error": str(e)
            })

    return jsonify(results)


# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.route("/")
def home():
    return "BSEB API Running 🚀"


# -----------------------------
# LOCAL RUN (IGNORED BY RAILWAY)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
