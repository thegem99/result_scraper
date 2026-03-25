from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import os
import time

app = Flask(__name__)

# ================= CHROME SETUP =================
def create_driver():
    options = webdriver.ChromeOptions()

    # Railway / Nix chromium setup
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # IMPORTANT: DO NOT USE Selenium Manager
    # Force system binaries from nix
    chromedriver_path = "/usr/bin/chromedriver"
    chromium_path = "/usr/bin/chromium"

    # fallback safety (some Railway builds differ)
    if not os.path.exists(chromedriver_path):
        chromedriver_path = "/nix/store/*/bin/chromedriver"

    if os.path.exists(chromium_path):
        options.binary_location = chromium_path

    return webdriver.Chrome(
        service=Service(chromedriver_path),
        options=options
    )


# ================= SCRAPER =================
def get_result(rollcode, roll_no):
    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 20)

        driver.get("https://www.bsebexam.com/")

        # wait captcha
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ))

        captcha = driver.execute_script(
            "return document.getElementById('generatedCaptcha').dataset.value"
        )

        # fill form via JS (avoids interactable errors)
        driver.execute_script(
            "document.getElementById('rollcode').value = arguments[0];", rollcode
        )
        driver.execute_script(
            "document.getElementById('rollno').value = arguments[0];", roll_no
        )
        driver.execute_script(
            "document.getElementById('captchaInput').value = arguments[0];", captcha
        )

        driver.execute_script("document.getElementById('resultForm').submit();")

        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")

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

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


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

        data = get_result(rollcode, roll_no)
        results.append(data)

    return jsonify(results)


# ================= HEALTH =================
@app.route("/")
def home():
    return {"status": "running"}


# ================= DEBUG (VERY IMPORTANT) =================
@app.route("/debug")
def debug():
    return {
        "chromedriver": os.popen("which chromedriver").read(),
        "chromium": os.popen("which chromium || which chromium-browser").read()
    }


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
