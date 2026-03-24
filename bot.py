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
    
    # 1. SMARTER PATH DETECTION FOR NIXPACKS
    # We look for 'chromium' first as it's the most reliable on Railway
    chrome_bin = shutil.which("chromium") or shutil.which("google-chrome") or "/usr/bin/chromium"
    driver_bin = shutil.which("chromedriver") or "/usr/bin/chromedriver"
    
    logger.info(f"🔍 System Check - Browser: {chrome_bin} | Driver: {driver_bin}")

    if chrome_bin:
        options.binary_location = chrome_bin
    
    # 2. INITIALIZE SERVICE
    try:
        # Use the detected driver path explicitly
        service = Service(executable_path=driver_bin)
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        logger.error(f"❌ Selenium failed to start: {e}")
        return {"Roll No": roll_no, "Status": "System Driver Mismatch"}

    driver.set_page_load_timeout(30)
    wait = WebDriverWait(driver, 15)
    
    try:
        logger.info(f"🚀 Scraping Roll No: {roll_no}")
        driver.get("https://www.bsebexam.com/")
        
        # 1. Wait for Captcha (Check for the dataset value specifically)
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ) is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        # 2. Fill Form
        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # 3. Submit using the internal JS function
        driver.execute_script("document.getElementById('resultForm').submit()")
        
        # Give the result page time to render
        time.sleep(5) 
        
        # 4. Parse Results
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        if "Student's Name" not in driver.page_source:
            # Look for error alerts from the site
            try:
                err_text = driver.find_element(By.CLASS_NAME, "swal2-html-container").text
                return {"Roll No": roll_no, "Status": f"Site Error: {err_text}"}
            except:
                return {"Roll No": roll_no, "Status": "Data Not Found"}

        student_name = aggregate_marks = "N/A"
        subject_data = {}

        # Extract info using your working script logic
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if text == "Student's Name":
                student_name = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in text:
                aggregate_marks = td.find_next_sibling("td").get_text(strip=True)

        marks_table = soup.find("table", {"class": "text_center"})
        if marks_table:
            rows = marks_table.find_all("tr")
            for row in rows[3:]: # Skip table headers
                cells = row.find_all("td")
                if len(cells) >= 8:
                    sub_name = cells[0].get_text(strip=True)
                    # We grab the 'Total' column (index 7)
                    subject_data[f"{sub_name}_Total"] = cells[7].get_text(strip=True)

        result = {
            "Roll No": roll_no,
            "Student Name": student_name,
            "Aggregate Marks": aggregate_marks
        }
        result.update(subject_data)
        logger.info(f"✅ Successfully fetched: {roll_no}")
        return result

    except Exception as e:
        logger.error(f"❌ Scraper loop error: {e}")
        return {"Roll No": roll_no, "Status": "Timeout/Error"}
    finally:
        driver.quit()

# ================= TELEGRAM HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BSEB Result Scraper Online.\n\nUse: /batch <roll_code> <start_roll> <count>")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Missing arguments!\nExample: /batch 31082 26010001 5")
        return

    roll_code = context.args[0]
    try:
        start_roll = int(context.args[1])
        count = min(int(context.args[2]), 20) # Limit to 20 for RAM safety
    except ValueError:
        await update.message.reply_text("❌ Start Roll and Count must be numbers.")
        return

    status_msg = await update.message.reply_text(f"⏳ Processing {count} results... please wait.")
    
    all_data = []
    for i in range(count):
        current_roll = str(start_roll + i)
        res = get_bseb_result(roll_code, current_roll)
        all_data.append(res)
        
        # Live update in Telegram every 2 results
        if (i + 1) % 2 == 0 or i == count - 1:
            try:
                await status_msg.edit_text(f"⏳ Progress: {i+1}/{count} completed...")
            except:
                pass

    # Create CSV using Pandas
    df = pd.DataFrame(all_data)
    csv_file = io.BytesIO()
    df.to_csv(csv_file, index=False)
    csv_file.seek(0)

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=csv_file,
        filename=f"BSEB_Results_{roll_code}.csv",
        caption=f"✅ Finished! Processed {len(all_data)} records."
    )
    await status_msg.delete()

# ================= MAIN RUNNER =================
if __name__ == "__main__":
    # Your Token
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))
    
    print("🚀 Bot is starting and polling for updates...")
    app.run_polling(drop_pending_updates=True)
