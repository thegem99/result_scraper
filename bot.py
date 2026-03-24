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
    """Locates binaries and initializes the driver."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # 1. Search for Chromium
    chrome_path = (
        shutil.which("chromium") or 
        shutil.which("chromium-browser") or 
        shutil.which("google-chrome") or 
        "/usr/bin/chromium"
    )
    
    # 2. Search for Chromedriver
    driver_path = (
        shutil.which("chromedriver") or 
        "/usr/bin/chromedriver" or 
        "/usr/local/bin/chromedriver"
    )

    logger.info(f"Using Chrome: {chrome_path}")
    logger.info(f"Using Driver: {driver_path}")

    # Validation to prevent the 'NoneType' error
    if not chrome_path or not os.path.exists(chrome_path):
        raise RuntimeError("Chromium binary not found!")
    if not driver_path or not os.path.exists(driver_path):
        raise RuntimeError("Chromedriver binary not found!")

    options.binary_location = chrome_path
    service = Service(executable_path=driver_path)
    return webdriver.Chrome(service=service, options=options)

def get_bseb_result(roll_code, roll_no):
    driver = None
    try:
        driver = get_driver()
        driver.set_page_load_timeout(30)
        driver.get("https://www.bsebexam.com/")
        
        wait = WebDriverWait(driver, 15)
        # Wait for captcha
        wait.until(lambda d: d.execute_script("return document.getElementById('generatedCaptcha')?.dataset?.value") is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        driver.execute_script("document.getElementById('resultForm').submit()")
        
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        if "Student's Name" not in driver.page_source:
            return {"Roll No": roll_no, "Status": "Not Found"}

        # Basic extraction
        name = "N/A"
        marks = "N/A"
        for td in soup.find_all("td"):
            if td.get_text(strip=True) == "Student's Name":
                name = td.find_next_sibling("td").get_text(strip=True)
            if "Aggregate Marks" in td.get_text():
                marks = td.find_next_sibling("td").get_text(strip=True)

        return {"Roll No": roll_no, "Student Name": name, "Marks": marks}

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {"Roll No": roll_no, "Status": f"Error: {str(e)[:50]}"}
    finally:
        if driver:
            driver.quit()

# Telegram logic remains the same
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Active. Use /batch <rollcode> <startroll> <count>")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3: return
    roll_code, start_roll, count = context.args[0], int(context.args[1]), min(int(context.args[2]), 10)
    
    results = []
    for i in range(count):
        results.append(get_bseb_result(roll_code, str(start_roll + i)))
        
    df = pd.DataFrame(results)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    await context.bot.send_document(chat_id=update.effective_chat.id, document=buf, filename="results.csv")

if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))
    app.run_polling()
