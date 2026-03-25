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

    res = session.post(url, data=payload, timeout=20)
    soup = BeautifulSoup(res.text, "html.parser")

    data = {
        "roll_no": rollno,
        "name": "",
        "father": "",
        "school": "",
        "total": "",
        "subjects": {}
    }

    # Extract all text
    text = soup.get_text()

    # Basic extraction (can improve later)
    if "Name" in text:
        data["name"] = text

    # Parse tables
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cols = [c.text.strip() for c in row.find_all(["td", "th"])]

            if len(cols) == 2:
                key, val = cols

                if "Father" in key:
                    data["father"] = val
                elif "School" in key:
                    data["school"] = val
                elif "Total" in key:
                    data["total"] = val
                else:
                    data["subjects"][key] = val

    return data


# -----------------------------
# HOME PAGE (FORM)
# -----------------------------
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>BSEB Result Portal</title>
<style>
body {
    font-family: Arial;
    background: linear-gradient(135deg,#667eea,#764ba2);
    color:white;
    text-align:center;
}
.box {
    background:white;
    color:black;
    padding:20px;
    margin:50px auto;
    width:350px;
    border-radius:10px;
}
input, select {
    width:90%;
    padding:10px;
    margin:10px;
}
button {
    padding:10px;
    width:95%;
    background:black;
    color:white;
}
</style>
</head>

<body>

<div class="box">
<h2>BSEB Result 2026</h2>

<form action="/view" method="get">

<input name="rollcode" placeholder="Roll Code" required>
<input name="rollno" placeholder="Roll Number" required>

<select name="mode" id="mode" onchange="toggleCount()">
<option value="single">Single</option>
<option value="batch">Batch</option>
</select>

<input name="count" id="count" value="1">

<button type="submit">Get Result</button>

</form>
</div>

<script>
function toggleCount(){
    let mode = document.getElementById("mode").value;
    let count = document.getElementById("count");

    if(mode === "single"){
        count.value = 1;
        count.readOnly = true;
    } else {
        count.readOnly = false;
    }
}
toggleCount();
</script>

</body>
</html>
""")


# -----------------------------
# RESULT PAGE
# -----------------------------
@app.route("/view")
def view():
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")
    mode = request.args.get("mode")
    count = int(request.args.get("count", 1))

    session = get_session()
    token = get_token(session)

    results = []

    for i in range(count):
        rn = str(int(rollno) + i)
        data = fetch_result(session, token, rollcode, rn)
        results.append(data)
        time.sleep(0.5)

    # Render results
    html = """
    <html><body style='font-family:Arial;background:#f5f5f5'>
    <h2 style='text-align:center'>Result</h2>
    """

    for r in results:
        html += f"""
        <div style='background:white;padding:20px;margin:20px;border-radius:10px'>
        <h3>Roll No: {r['roll_no']}</h3>
        <p><b>Name:</b> {r['name']}</p>
        <p><b>Father:</b> {r['father']}</p>
        <p><b>School:</b> {r['school']}</p>
        <p><b>Total:</b> {r['total']}</p>

        <h4>Subjects</h4>
        <table border="1" width="100%" cellpadding="5">
        """

        for k, v in r["subjects"].items():
            html += f"<tr><td>{k}</td><td>{v}</td></tr>"

        html += "</table></div>"

    html += "</body></html>"

    return html


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
