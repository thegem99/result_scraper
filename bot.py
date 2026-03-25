from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

BASE_URL = "https://www.bsebexam.com"


# =========================
# GET TOKEN + SESSION
# =========================
def get_session():
    session = requests.Session()
    res = session.get(BASE_URL, timeout=10)

    soup = BeautifulSoup(res.text, "html.parser")

    token = soup.find("input", {"name": "__RequestVerificationToken"})

    return session, token["value"] if token else None


# =========================
# FETCH RESULT
# =========================
def fetch_result(rollcode, rollno):
    try:
        session, token = get_session()

        if not token:
            return {"error": "token_not_found"}

        payload = {
            "rollcode": rollcode,
            "rollno": rollno,
            "__RequestVerificationToken": token
            # CAPTCHA NOT REQUIRED (client-only validation)
        }

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": BASE_URL
        }

        res = session.post(BASE_URL, data=payload, headers=headers, timeout=15)

        soup = BeautifulSoup(res.text, "html.parser")

        # -------------------------
        # SAFE PARSING
        # -------------------------
        def safe_text(selector):
            el = soup.select_one(selector)
            return el.text.strip() if el else None

        name = safe_text("#studentName")
        total = safe_text("#totalMarks")

        subjects = {}

        for row in soup.select("table tr"):
            cols = row.find_all("td")
            if len(cols) >= 2:
                subject = cols[0].text.strip()
                marks = cols[1].text.strip()
                subjects[subject] = marks

        return {
            "roll_no": rollno,
            "rollcode": rollcode,
            "status": "success",
            "student_name": name,
            "aggregate_marks": total,
            "subjects": subjects
        }

    except Exception as e:
        return {
            "roll_no": rollno,
            "status": "error",
            "error": str(e)
        }


# =========================
# SINGLE API
# =========================
@app.route("/result")
def result():
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")

    return jsonify(fetch_result(rollcode, rollno))


# =========================
# BATCH API
# =========================
@app.route("/batch")
def batch():
    rollcode = request.args.get("rollcode")
    start = int(request.args.get("start"))
    count = int(request.args.get("count"))

    results = []

    for i in range(count):
        rollno = str(start + i)
        results.append(fetch_result(rollcode, rollno))

    return jsonify(results)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
