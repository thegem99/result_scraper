import os
import time
import io
import logging
import shutil
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

# Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= FIXED SCRAPER LOGIC =================
def get_bseb_result(roll_code, roll_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Force Railway Chrome Path
    options.binary_location = "/usr/bin/google-chrome"
    
    # AUTO-LOCATE Driver Path (Fixes NoSuchDriverException)
    driver_path = shutil.which("chromedriver") or "/usr/bin/chromedriver"
    logger.info(f"Using Chromedriver found at: {driver_path}")
    
    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    wait = WebDriverWait(driver, 15)
    
    try:
        logger.info(f"🚀 Scraping {roll_no}...")
        driver.get("https://www.bsebexam.com/")
        
        # 1. Wait for Captcha Data
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ) is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        # 2. Fill Form
        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # 3. Submit
        driver.execute_script("document.getElementById('resultForm').submit()")
        
        # Wait for result page to load
        time.sleep(5) 
        
        # 4. Parse Content
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        if "Student's Name" not in driver.page_source:
            # Check for website error alerts
            try:
                err = driver.find_element(By.CLASS_NAME, "swal2-html-container").text
                return {"Roll No": roll_no, "Status": f"Error: {err}"}
            except:
                return {"Roll No": roll_no, "Status": "Not Found"}

        student_name = aggregate_marks = "N/A"
        subject_data = {}

        # Extract Student Info
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if text == "Student's Name":
                student_name = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in text: # Fuzzy match for the colon
                aggregate_marks = td.find_next_sibling("td").get_text(strip=True)

        # Extract Marks Table
        marks_table = soup.find("table", {"class": "text_center"})
        if marks_table:
            rows = marks_table.find_all("tr")
            for row in rows[3:]: # Skip headers
                cells = row.find_all("td")
                if len(cells) >= 8:
                    sub = cells[0].get_text(strip=True)
                    subject_data[f"{sub}_Total"] = cells[7].get_text(strip=True)

        result_row = {
            "Roll No": roll_no,
            "Student Name": student_name,
            "Total Marks": aggregate_marks
        }
        result_row.update(subject_data)
        logger.info(f"✅ Success for {roll_no}")
        return result_row

    except Exception as e:
        logger.error(f"❌ Scraper Crashed for {roll_no}: {e}")
        return {"Roll No": roll_no, "Status": "Timeout/System Error"}
    finally:
        driver.quit()

# ================= BOT HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BSEB Scraper is online.\nUsage: /batch <rollcode> <start_roll> <count>")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Usage: /batch 31082 26010001 5")
        return

    roll_code = context.args[0]
    try:
        start_roll = int(context.args[1])
        count = min(int(context.args[2]), 20) # Max 20 per request
    except:
        await update.message.reply_text("❌ Invalid numbers.")
        return

    status_msg = await update.message.reply_text(f"⏳ Processing {count} results... Check logs for details.")
    
    results = []
    for i in range(count):
        curr_roll = str(start_roll + i)
        res = get_bseb_result(roll_code, curr_roll)
        results.append(res)
        
        # Progress Update
        if (i+1) % 2 == 0 or i == count-1:
            try: await status_msg.edit_text(f"⏳ Progress: {i+1}/{count} completed...")
            except: pass

    # Generate CSV
    df = pd.DataFrame(results)
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=output,
        filename=f"BSEB_{roll_code}.csv",
        caption=f"✅ Done! Processed {len(results)} records."
    )
    await status_msg.delete()

# ================= RUNNER =================
if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))

    print("🚀 Bot starting...")
    app.run_polling(drop_pending_updates=True)
