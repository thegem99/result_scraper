from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os

app = Flask(__name__)


# ================= SCRAPER =================
def fetch_result(page, rollcode, roll_no):
    try:
        page.goto("https://www.bsebexam.com/", timeout=60000)

        page.wait_for_selector("#generatedCaptcha", timeout=20000)

        captcha = page.eval_on_selector(
            "#generatedCaptcha",
            "el => el.dataset.value"
        )

        page.fill("#rollcode", rollcode)
        page.fill("#rollno", roll_no)
        page.fill("#captchaInput", captcha)

        page.click("#resultForm button[type='submit']")

        page.wait_for_timeout(4000)

        soup = BeautifulSoup(page.content(), "html.parser")

        data = {
            "roll_no": roll_no,
            "student_name": None,
            "aggregate_marks": None,
            "subjects": {}
        }

        # ---- BASIC INFO ----
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)

            if text == "Student's Name":
                nxt = td.find_next_sibling("td")
                if nxt:
                    data["student_name"] = nxt.get_text(strip=True)

            if text == "Aggregate Marks:":
                nxt = td.find_next_sibling("td")
                if nxt:
                    data["aggregate_marks"] = nxt.get_text(strip=True)

        # ---- SUBJECTS ----
        table = soup.find("table", {"class": "text_center"})

        if table:
            rows = table.find_all("tr")[3:]
            for row in rows:
                cols = row.find_all("td")

                if len(cols) >= 8:
                    subject = cols[0].get_text(strip=True)

                    data["subjects"][subject] = {
                        "theory": cols[3].get_text(strip=True),
                        "practical": cols[4].get_text(strip=True),
                        "total": cols[7].get_text(strip=True)
                    }

        return data

    except Exception as e:
        return {
            "roll_no": roll_no,
            "error": str(e)
        }


# ================= PLAYWRIGHT INIT =================
playwright = sync_playwright().start()

browser = playwright.chromium.launch(
    headless=True,
    args=["--no-sandbox", "--disable-dev-shm-usage"]
)

context = browser.new_context()


# ================= API =================
@app.route("/batch", methods=["GET"])
def batch():
    rollcode = request.args.get("rollcode")
    start = request.args.get("start")
    count = request.args.get("count")

    if not all([rollcode, start, count]):
        return jsonify({"error": "missing parameters"}), 400

    start = int(start)
    count = int(count)

    results = []

    for i in range(count):
        roll_no = str(start + i)

        page = context.new_page()
        result = fetch_result(page, rollcode, roll_no)
        page.close()

        results.append(result)

    return jsonify(results)


# ================= HOME =================
@app.route("/")
def home():
    return {"status": "running"}


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
