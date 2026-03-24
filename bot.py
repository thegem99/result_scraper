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

# Set Environment Variable via code as well for double safety
os.environ["SE_OFFLINE"] = "true"

def get_bseb_result(roll_code, roll_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222") # Helps in containers
    
    # 1. Force Paths
    chrome_bin = shutil.which("chromium") or "/usr/bin/chromium"
    driver_bin = shutil.which("chromedriver") or "/usr/bin/chromedriver"
    
    options.binary_location = chrome_bin
    
    # 2. Initialize with minimal interference
    try:
        service = Service(executable_path=driver_bin)
        # Using a direct call to bypass Selenium Manager's discovery logic
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        logger.error(f"❌ Initialization Failed: {e}")
        return {"Roll No": roll_no, "Status": "Selenium Driver Error"}

    driver.set_page_load_timeout(30)
    wait = WebDriverWait(driver, 15)
    
    try:
        logger.info(f"🚀 Scraping Roll: {roll_no}")
        driver.get("https://www.bsebexam.com/")
        
        # Wait for Captcha dataset
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ) is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        # Fill Form
        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # Submit
        driver.execute_script("document.getElementById('resultForm').submit()")
        
        time.sleep(5) 
        
        # Parse Results
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if "Student's Name" not in driver.page_source:
            return {"Roll No": roll_no, "Status": "Record Not Found"}

        student_name = aggregate_marks = "N/A"
        subject_data = {}

        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if text == "Student's Name":
                student_name = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in text:
                aggregate_marks = td.find_next_sibling("td").get_text(strip=True)

        marks_table = soup.find("table", {"class": "text_center"})
        if marks_table:
            for row in marks_table.find_all("tr")[3:]:
                cells = row.find_all("td")
                if len(cells) >= 8:
                    sub_name = cells[0].get_text(strip=True)
                    subject_data[f"{sub_name}_Total"] = cells[7].get_text(strip=True)

        result = {
            "Roll No": roll_no,
            "Student Name": student_name,
            "Aggregate Marks": aggregate_marks
        }
        result.update(subject_data)
        logger.info(f"✅ Fetched {roll_no}")
        return result

    except Exception as e:
        logger.error(f"❌ Loop Error: {e}")
        return {"Roll No": roll_no, "Status": "Processing Error"}
    finally:
        driver.quit()

# ================= TELEGRAM HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BSEB Bot Active. Usage: /batch <roll_code> <start_roll> <count>")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /batch 31082 26010001 5")
        return

    roll_code, start_roll, count = context.args[0], int(context.args[1]), min(int(context.args[2]), 20)
    status_msg = await update.message.reply_text(f"⏳ Processing {count} results...")
    
    all_data = []
    for i in range(count):
        curr = str(start_roll + i)
        res = get_bseb_result(roll_code, curr)
        all_data.append(res)
        if (i+1) % 2 == 0: await status_msg.edit_text(f"⏳ Progress: {i+1}/{count}...")

    df = pd.DataFrame(all_data)
    csv_file = io.BytesIO()
    df.to_csv(csv_file, index=False)
    csv_file.seek(0)

    await context.bot.send_document(chat_id=update.effective_chat.id, document=csv_file, filename=f"BSEB_{roll_code}.csv")
    await status_msg.delete()

if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))
    app.run_polling(drop_pending_updates=True)
