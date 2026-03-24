import os
import time
import io
import logging
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # Tell Selenium where Chromium is
    options.binary_location = "/usr/bin/chromium"
    
    # Force Selenium to use the system driver and stop checking the cache
    service = Service(executable_path="/usr/bin/chromedriver")
    
    try:
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        logger.error(f"❌ Failed to start Chrome: {e}")
        raise e

def get_bseb_result(roll_code, roll_no):
    driver = None
    try:
        driver = get_driver()
        driver.get("https://www.bsebexam.com/")
        
        wait = WebDriverWait(driver, 20)
        # Wait for captcha
        wait.until(lambda d: d.execute_script("return document.getElementById('generatedCaptcha')?.dataset?.value") is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # Submit via JavaScript to be safe
        driver.execute_script("document.getElementById('resultForm').submit()")
        
        # Wait for government server to respond
        time.sleep(7)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if "Student's Name" not in driver.page_source:
            return {"Roll No": roll_no, "Status": "Not Found / Timeout"}

        name = marks = "N/A"
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            if txt == "Student's Name":
                name = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in txt:
                marks = td.find_next_sibling("td").get_text(strip=True)

        logger.info(f"✅ Success for {roll_no}")
        return {"Roll No": roll_no, "Student Name": name, "Marks": marks}

    except Exception as e:
        logger.error(f"❌ Scraper loop error: {e}")
        return {"Roll No": roll_no, "Status": "System Error"}
    finally:
        if driver:
            driver.quit()

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Format: /batch <rollcode> <startroll> <count>")
        return
        
    roll_code, start_roll, count = context.args[0], int(context.args[1]), min(int(context.args[2]), 10)
    status_msg = await update.message.reply_text(f"⏳ Fetching {count} results...")
    
    results = []
    for i in range(count):
        curr = str(start_roll + i)
        results.append(get_bseb_result(roll_code, curr))
        
    df = pd.DataFrame(results)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    
    await context.bot.send_document(chat_id=update.effective_chat.id, document=buf, filename="results.csv")
    await status_msg.delete()

if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("batch", batch))
    app.run_polling()
