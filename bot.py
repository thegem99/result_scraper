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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # 🔍 This will find the browser installed by the .toml file above
    chrome_path = shutil.which("chromium") or shutil.which("google-chrome") or "/usr/bin/chromium"
    driver_path = shutil.which("chromedriver") or "/usr/bin/chromedriver"

    logger.info(f"📍 FOUND CHROME AT: {chrome_path}")
    logger.info(f"📍 FOUND DRIVER AT: {driver_path}")

    options.binary_location = chrome_path
    service = Service(executable_path=driver_path)
    
    return webdriver.Chrome(service=service, options=options)

def get_bseb_result(roll_code, roll_no):
    driver = None
    try:
        driver = get_driver()
        driver.get("https://www.bsebexam.com/")
        
        wait = WebDriverWait(driver, 15)
        # Wait for captcha
        wait.until(lambda d: d.execute_script("return document.getElementById('generatedCaptcha')?.dataset?.value") is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        driver.execute_script("document.getElementById('resultForm').submit()")
        
        time.sleep(6)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        if "Student's Name" not in driver.page_source:
            return {"Roll No": roll_no, "Status": "Not Found"}

        name = marks = "N/A"
        for td in soup.find_all("td"):
            if td.get_text(strip=True) == "Student's Name":
                name = td.find_next_sibling("td").get_text(strip=True)
            if "Aggregate Marks" in td.get_text():
                marks = td.find_next_sibling("td").get_text(strip=True)

        return {"Roll No": roll_no, "Student Name": name, "Marks": marks}

    except Exception as e:
        logger.error(f"❌ Scraper Failed: {e}")
        return {"Roll No": roll_no, "Status": "Engine Error"}
    finally:
        if driver: driver.quit()

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3: return
    roll_code, start_roll, count = context.args[0], int(context.args[1]), min(int(context.args[2]), 5)
    
    status = await update.message.reply_text(f"⏳ Processing {count} results...")
    results = [get_bseb_result(roll_code, str(start_roll + i)) for i in range(count)]
        
    df = pd.DataFrame(results)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    await context.bot.send_document(chat_id=update.effective_chat.id, document=buf, filename="results.csv")
    await status.delete()

if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("batch", batch))
    app.run_polling()
