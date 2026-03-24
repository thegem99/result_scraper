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

# Setup Logging - Very important for Railway debugging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= WORKING SCRAPER LOGIC =================
def get_bseb_result(roll_code, roll_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # Tell the site we are a real Chrome browser
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.binary_location = "/usr/bin/google-chrome"
    
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30) # Prevent hanging forever
    wait = WebDriverWait(driver, 15)
    
    try:
        logger.info(f">>> Step 1: Loading Website for {roll_no}")
        driver.get("https://www.bsebexam.com/")
        
        # 1. Wait for Captcha dataset to populate
        logger.info(f">>> Step 2: Waiting for Captcha...")
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ) is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")
        logger.info(f">>> Captcha Found: {captcha}")

        # 2. Fill Form
        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # 3. Submit
        logger.info(f">>> Step 3: Submitting Form...")
        driver.execute_script("document.getElementById('resultForm').submit()")
        
        # 4. Wait for redirect/result page
        time.sleep(5) 
        
        # Check if we are still on the home page (Submit failed)
        if "Student's Name" not in driver.page_source:
            # Check for error message
            try:
                error_msg = driver.find_element(By.CLASS_NAME, "swal2-html-container").text
                logger.warning(f">>> Site Error for {roll_no}: {error_msg}")
                return {"Roll No": roll_no, "Status": f"Error: {error_msg}"}
            except:
                logger.warning(f">>> Result page did not load for {roll_no}")
                return {"Roll No": roll_no, "Status": "Page Not Loaded"}

        # 5. Parse Data
        logger.info(f">>> Step 4: Parsing Result...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        student_name = roll_number = aggregate_marks = "N/A"
        subject_data = {}

        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if text == "Student's Name":
                student_name = td.find_next_sibling("td").get_text(strip=True)
            elif text == "Roll Number":
                roll_number = td.find_next_sibling("td").get_text(strip=True)
            elif text == "Aggregate Marks:":
                aggregate_marks = td.find_next_sibling("td").get_text(strip=True)

        marks_table = soup.find("table", {"class": "text_center"})
        if marks_table:
            for row in marks_table.find_all("tr")[3:]:
                cells = row.find_all("td")
                if len(cells) >= 8:
                    subject = cells[0].get_text(strip=True)
                    subject_data[f"{subject}_Total"] = cells[7].get_text(strip=True)

        row = {
            "Roll No": roll_number or roll_no,
            "Student Name": student_name,
            "Aggregate Marks": aggregate_marks
        }
        row.update(subject_data)
        logger.info(f">>> Success for {roll_no}")
        return row

    except Exception as e:
        logger.error(f">>> Critical Scraper Error for {roll_no}: {str(e)}")
        return {"Roll No": roll_no, "Status": "System Timeout"}
    finally:
        driver.quit()

# ================= TELEGRAM HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BSEB Bot Ready. Format: /batch 31082 26010001 5")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Missing arguments!")
        return

    roll_code = context.args[0]
    start_roll = int(context.args[1])
    count = min(int(context.args[2]), 10) # Keep count low to test

    status_msg = await update.message.reply_text(f"⏳ Processing {count} results. Check Railway logs for live status...")
    
    all_results = []
    for i in range(count):
        curr_roll = str(start_roll + i)
        res = get_bseb_result(roll_code, curr_roll)
        all_results.append(res)
        
        # Update progress every result so we know it's not stuck
        try:
            await status_msg.edit_text(f"⏳ Progress: {i+1}/{count} completed...")
        except:
            pass

    # Build CSV
    if all_results:
        df = pd.DataFrame(all_results)
        csv_stream = io.BytesIO()
        df.to_csv(csv_stream, index=False)
        csv_stream.seek(0)

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=csv_stream,
            filename=f"BSEB_Results_{roll_code}.csv",
            caption="✅ Batch Completed."
        )
    else:
        await update.message.reply_text("❌ No data was fetched.")

# ================= MAIN =================
if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))
    
    print("🚀 Bot starting...")
    app.run_polling(drop_pending_updates=True)
