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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Path where Nixpacks (from the .toml above) installs Chromium
    options.binary_location = "/usr/bin/chromium"
    
    # Force the use of the system chromedriver
    # This prevents Selenium from downloading its own broken version
    service = Service(executable_path="/usr/bin/chromedriver")
    
    try:
        # Pass the service explicitly
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        logger.error(f"❌ Driver Start Failed: {e}")
        raise e

def get_bseb_result(roll_code, roll_no):
    driver = None
    try:
        driver = get_driver()
        driver.set_page_load_timeout(35)
        driver.get("https://www.bsebexam.com/")
        
        wait = WebDriverWait(driver, 25)
        
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
        
        # Govt servers are slow, wait for render
        time.sleep(10)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if "Student's Name" not in driver.page_source:
            return {"Roll No": roll_no, "Status": "Not Found / Site Timeout"}

        name = marks = "N/A"
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            if txt == "Student's Name":
                name = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in txt:
                marks = td.find_next_sibling("td").get_text(strip=True)

        logger.info(f"✅ Extracted Roll: {roll_no}")
        return {"Roll No": roll_no, "Student Name": name, "Marks": marks}

    except Exception as e:
        logger.error(f"❌ Scraper loop error: {str(e)[:100]}")
        return {"Roll No": roll_no, "Status": "System Error"}
    finally:
        if driver:
            driver.quit()

# --- Telegram Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BSEB Bot Active.\nFormat: /batch <rollcode> <startroll> <count>")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Example: /batch 31082 26010001 5")
        return
        
    roll_code, start_roll, count = context.args[0], int(context.args[1]), min(int(context.args[2]), 10)
    status_msg = await update.message.reply_text(f"⏳ Process started for {count} results...")
    
    results = []
    for i in range(count):
        curr = str(start_roll + i)
        results.append(get_bseb_result(roll_code, curr))
        if (i+1) % 2 == 0:
            try: await status_msg.edit_text(f"⏳ Progress: {i+1}/{count} fetched...")
            except: pass
        
    df = pd.DataFrame(results)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    
    await context.bot.send_document(chat_id=update.effective_chat.id, document=buf, filename=f"Results_{roll_code}.csv")
    await status_msg.delete()

if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))
    app.run_polling()
