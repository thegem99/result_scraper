import os
import time
import io
import csv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

# ================= SELENIUM RESULT FETCHER =================
def get_bseb_result(roll_code, roll_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # On Railway with Nixpacks, Chrome is installed here:
    options.binary_location = "/usr/bin/google-chrome"
    
    # We do NOT use ChromeDriverManager anymore. 
    # We let Selenium 4.11.2 find the chromedriver installed by Nixpacks.
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get("https://www.bsebexam.com/")
        wait = WebDriverWait(driver, 15)

        # Wait for CAPTCHA
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ) is not None)
        
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        # Fill the form
        driver.find_element(By.ID, "rollcode").send_keys(roll_code)
        driver.find_element(By.ID, "rollno").send_keys(roll_no)
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # Submit via click
        submit_btn = driver.find_element(By.ID, "btnSubmit")
        submit_btn.click()

        # Wait for page transition
        time.sleep(3)
        html = driver.page_source
        
        soup = BeautifulSoup(html, "html.parser")
        
        # --- Extraction Logic ---
        student_name = "N/A"
        aggregate_marks = "N/A"
        
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if "Student's Name" in text:
                student_name = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in text:
                aggregate_marks = td.find_next_sibling("td").get_text(strip=True)

        subjects = []
        marks_table = soup.find("table", {"class": "text_center"})
        if marks_table:
            # Skip header rows
            rows = marks_table.find_all("tr")
            for row in rows[3:]:
                cells = row.find_all("td")
                if len(cells) >= 8:
                    subjects.append({
                        "Subject": cells[0].get_text(strip=True),
                        "Total": cells[7].get_text(strip=True)
                    })

        return {
            "Roll No": roll_no,
            "Name": student_name,
            "Aggregate Marks": aggregate_marks,
            "Subjects": subjects
        }

    finally:
        driver.quit() # Crucial for Railway memory management

# ================= TELEGRAM BOT HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Usage: /batch <roll_code> <start_roll> <count>")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /batch 32065 26030001 5")
        return

    roll_code = context.args[0]
    start_roll = int(context.args[1])
    count = min(int(context.args[2]), 20)

    await update.message.reply_text(f"Fetching {count} results. Please wait...")

    results = []
    for i in range(count):
        curr_roll = str(start_roll + i)
        try:
            res = get_bseb_result(roll_code, curr_roll)
            results.append(res)
        except Exception as e:
            results.append({"Roll No": curr_roll, "Name": "Error", "Aggregate Marks": str(e), "Subjects": []})

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll No", "Name", "Total Marks", "Subject Details"])
    for r in results:
        subj_str = " | ".join([f"{s['Subject']}:{s['Total']}" for s in r["Subjects"]])
        writer.writerow([r["Roll No"], r["Name"], r["Aggregate Marks"], subj_str])

    output.seek(0)
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(output.getvalue().encode()),
        filename=f"BSEB_{roll_code}.csv"
    )

if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))
    app.run_polling()
