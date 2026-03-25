from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

app = Flask(__name__)


# ================= SCRAPER =================
def get_result(page, rollcode, roll_no):
    try:
        page.goto("https://www.bsebexam.com/", timeout=60000)

        # wait for captcha element
        page.wait_for_selector("#generatedCaptcha", timeout=20000)

        captcha = page.eval_on_selector(
            "#generatedCaptcha",
            "el => el.dataset.value"
        )

        # fill form
        page.fill("#rollcode", rollcode)
        page.fill("#rollno", roll_no)
        page.fill("#captchaInput", captcha)

        page.click("#resultForm button[type='submit']")

        page.wait_for_timeout(3000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        result = {
            "roll_no": roll_no,
            "student_name": None,
            "aggregate_marks": None,
            "subjects": {}
        }

        # ================= BASIC INFO =================
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)

            if text == "Student's Name":
                result["student_name"] = td.find_next_sibling("td").get_text(strip=True)

            elif text == "Aggregate Marks:":
                result["aggregate_marks"] = td.find_next_sibling("td").get_text(strip=True)

        # ================= SUBJECT MARKS =================
        table = soup.find("table", {"class": "text_center"})

        if table:
            for row in table.find_all("tr")[3:]:
                cells = row.find_all("td")

                if len(cells) >= 8:
                    subject = cells[0].get_text(strip=True)

                    result["subjects"][subject] = {
                        "theory": cells[3].get_text(strip=True),
                        "practical": cells[4].get_text(strip=True),
                        "total": cells[7].get_text(strip=True)
                    }

        return result

    except Exception as e:
        return {
            "roll_no": roll_no,
            "error": str(e)
        }


# ================= GLOBAL PLAYWRIGHT =================
playwright = sync_playwright().start()
browser = playwright.chromium.launch(
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu"
    ]
)
context = browser.new_context()


# ================= API =================
@app.route("/batch", methods=["GET"])
def batch():
    rollcode = request.args.get("rollcode")
    start = request.args.get("start")
    count = request.args.get("count")

    if not rollcode or not start or not count:
        return jsonify({"error": "rollcode, start, count required"})

    start = int(start)
    count = int(count)

    results = []

    for i in range(count):
        roll_no = str(start + i)
        print("Fetching:", roll_no)

        page = context.new_page()
        data = get_result(page, rollcode, roll_no)
        page.close()

        results.append(data)

    return jsonify(results)


# ================= HEALTH =================
@app.route("/")
def home():
    return {"status": "running (playwright)"}


# ================= SHUTDOWN CLEANUP =================
@app.route("/shutdown")
def shutdown():
    try:
        context.close()
        browser.close()
        playwright.stop()
    except:
        pass
    return {"message": "shutdown complete"}


# ================= RUN =================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
