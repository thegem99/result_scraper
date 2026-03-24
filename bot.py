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

# ================= THE HARDENED SCRAPER =================
def get_bseb_result(roll_code, roll_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-debugging-port=9222")
    
    # 1. FORCE SYSTEM PATHS (Bypasses Selenium Manager Cache)
    chrome_bin = "/usr/bin/chromium"
    driver_bin = "/usr/bin/chromedriver"
    
    # Check if Nix installed them elsewhere and update path
    if not os.path.exists(chrome_bin):
        chrome_bin = shutil.which("chromium") or shutil.which("google-chrome")
    if not os.path.exists(driver_bin):
        driver_bin = shutil.which("chromedriver")

    options.binary_location = chrome_bin
    
    driver = None
    try:
        # 2. DIRECT SERVICE INITIALIZATION
        # This prevents the 'Status 127' error by using the system binary directly
        service = Service(executable_path=driver_bin)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(35)
        
        logger.info(f"🚀 Starting Scrape: {roll_no}")
        driver.get("https://www.bsebexam.com/")
        
        # 3. CAPTCHA LOGIC
        wait = WebDriverWait(driver, 20)
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ) is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        # 4. FORM SUBMISSION
        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # Trigger the site's own submit function
        driver.execute_script("document.getElementById('resultForm').submit()")
        
        # Wait for transition
        time.sleep(6) 
        
        # 5. DATA EXTRACTION
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if "Student's Name" not in driver.page_source:
            # Check for error message in the UI
            try:
                err = driver.find_element(By.CLASS_NAME, "swal2-html-container").text
                return {"Roll No": roll_no, "Status": f"Failed: {err}"}
            except:
                return {"Roll No": roll_no, "Status": "Data Not Found"}

        student_name = aggregate_marks = "N/A"
        subject_data = {}

        # Parsing Table
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if text == "Student's Name":
                student_name = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in text:
                aggregate_marks = td.find_next_sibling("td").get_text(strip=True)

        marks_table = soup.find("table", {"class": "text_center"})
        if marks_table:
            rows = marks_table.find_all("tr")
            for row in rows[3:]:
                cells = row.find_all("td")
                if len(cells) >= 8:
                    sub = cells[0].get_text(strip=True)
                    subject_data[f"{sub}_Total"] = cells[7].get_text(strip=True)

        res_row = {
            "Roll No": roll_no,
            "Student Name": student_name,
            "Aggregate Marks": aggregate_marks
        }
        res_row.update(subject_data)
        logger.info(f"✅ Success: {roll_no}")
        return res_row

    except Exception as e:
        logger.error(f"❌ Scraper Error on {roll_no}: {str(e)}")
        return {"Roll No": roll_no, "Status": "System/Network Error"}
    finally:
        if driver:
            driver.quit()

# ================= TELEGRAM HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BSEB Scraper is Live.\n\nUsage: /batch <rollcode> <start_roll> <count>")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Missing info! Example: /batch 31082 26010001 5")
        return

    roll_code = context.args[0]
    try:
        start_roll = int(context.args[1])
        count = min(int(context.args[2]), 15) # Safety limit
    except:
        await update.message.reply_text("❌ Roll/Count must be numbers.")
        return

    status_msg = await update.message.reply_text(f"⏳ Processing {count} students... please wait.")
    
    results = []
    for i in range(count):
        curr_roll = str(start_roll + i)
        data = get_bseb_result(roll_code, curr_roll)
        results.append(data)
        
        # Periodic Progress Update
        if (i+1) % 2 == 0 or i == count-1:
            try: await status_msg.edit_text(f"⏳ Progress: {i+1}/{count} fetched...")
            except: pass

    # CSV Generation
    df = pd.DataFrame(results)
    csv_stream = io.BytesIO()
    df.to_csv(csv_stream, index=False)
    csv_stream.seek(0)

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=csv_stream,
        filename=f"BSEB_{roll_code}.csv",
        caption=f"✅ Done! {len(results)} records processed."
    )
    await status_msg.delete()

# ================= EXECUTION =================
if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))
    
    print("🚀 Bot starting...")
    app.run_polling(drop_pending_updates=True)
