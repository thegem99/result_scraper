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
    
    # Force the binary location of the browser
    options.binary_location = "/usr/bin/chromium"
    
    # 🛠️ THE FIX: We manually start the Service object 
    # and then pass it to the Chrome object.
    try:
        service = Service(executable_path="/usr/bin/chromedriver")
        # We also pass 'service_args' to ensure it doesn't try to auto-update
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        logger.error(f"❌ Driver Start Failed: {e}")
        # Final fallback: If /usr/bin fails, try finding it via system path
        import shutil
        alt_driver = shutil.which("chromedriver")
        service = Service(executable_path=alt_driver)
        return webdriver.Chrome(service=service, options=options)

def get_bseb_result(roll_code, roll_no):
    driver = None
    try:
        driver = get_driver()
        driver.set_page_load_timeout(40) # BSEB is slow
        driver.get("https://www.bsebexam.com/")
        
        wait = WebDriverWait(driver, 25)
        
        # Check for Captcha
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ) is not None)
        
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        # Fill and Submit
        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # Using JS to click to avoid "Element not clickable" errors
        btn = driver.find_element(By.ID, "btnSubmit")
        driver.execute_script("arguments[0].click();", btn)
        
        # Long wait for BSEB results to process
        time.sleep(10)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if "Student's Name" not in driver.page_source:
            return {"Roll No": roll_no, "Status": "Not Found / Server Slow"}

        res = {"Roll No": roll_no}
        # Dynamic Extraction
        for td in soup.find_all("td"):
            txt = td.get_text(strip=True)
            if txt == "Student's Name":
                res["Name"] = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in txt:
                res["Marks"] = td.find_next_sibling("td").get_text(strip=True)

        logger.info(f"✅ Success: {roll_no}")
        return res

    except Exception as e:
        logger.error(f"❌ Scraper loop error: {str(e)[:100]}")
        return {"Roll No": roll_no, "Status": "System Error"}
    finally:
        if driver:
            driver.quit()

# --- Telegram Logic ---

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /batch <rollcode> <startroll> <count>")
        return
        
    roll_code, start_roll, count = context.args[0], int(context.args[1]), min(int(context.args[2]), 10)
    status_msg = await update.message.reply_text(f"⏳ Process started for {count} students...")
    
    results = []
    for i in range(count):
        curr = str(start_roll + i)
        results.append(get_bseb_result(roll_code, curr))
        if (i+1) % 2 == 0:
            try: await status_msg.edit_text(f"⏳ Progress: {i+1}/{count}...")
            except: pass
        
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
