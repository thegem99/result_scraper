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
    
    # Path where Nixpacks installs Chromium
    options.binary_location = "/usr/bin/chromium"
    
    # Force the use of the system chromedriver
    service = Service(executable_path="/usr/bin/chromedriver")
    
    # This is the key: We pass the service and options separately 
    # and do NOT let Selenium try to find its own driver.
    try:
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        logger.error(f"❌ Failed to start Chrome: {e}")
        raise e

def get_bseb_result(roll_code, roll_no):
    driver = None
    try:
        driver = get_driver()
        driver.get("https://www.bsebexam.com/")
        
        # Wait for the site's captcha value
        wait = WebDriverWait(driver, 20)
        wait.until(lambda d: d.execute_script("return document.getElementById('generatedCaptcha')?.dataset?.value") is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # Use JavaScript to click the submit button
        driver.execute_script("document.getElementById('resultForm').submit()")
        
        # Wait for govt server
        time.sleep(8)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if "Student's Name" not in driver.page_source:
            return {"Roll No": roll_no, "Status": "Not Found / Slow Server"}

        name = "N/A"
        marks = "N/A"
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            if txt == "Student's Name":
                name = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in txt:
                marks = td.find_next_sibling("td").get_text(strip=True)

        logger.info(f"✅ Success: {roll_no}")
        return {"Roll No": roll_no, "Student Name": name, "Marks": marks}

    except Exception as e:
        logger.error(f"❌ Scraper error: {e}")
        return {"Roll No": roll_no, "Status": "Error"}
    finally:
        if driver:
            driver.quit()

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /batch <rollcode> <startroll> <count>")
        return
        
    roll_code, start_roll, count = context.args[0], int(context.args[1]), min(int(context.args[2]), 10)
    status_msg = await update.message.reply_text(f"⏳ Process started for {count} students...")
    
    results = []
    for i in range(count):
        curr_roll = str(start_roll + i)
        results.append(get_bseb_result(roll_code, curr_roll))
        
    df = pd.DataFrame(results)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    
    await context.bot.send_document(chat_id=update.effective_chat.id, document=buf, filename=f"BSEB_{roll_code}.csv")
    await status_msg.delete()

if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("batch", batch))
    app.run_polling()
