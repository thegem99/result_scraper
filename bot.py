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

# ================= WORKING SCRAPER LOGIC =================
def get_bseb_result(roll_code, roll_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.binary_location = "/usr/bin/google-chrome"
    
    # Force use of system driver
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get("https://www.bsebexam.com/")
        
        # Get Captcha (Direct from dataset as per your working script)
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha').dataset.value"
        ) is not None)
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        # Fill Form
        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # Submit (Direct JS submit as per your working script)
        driver.execute_script("document.getElementById('resultForm').submit()")

        # ===== ERROR CHECK (SweetAlert) =====
        try:
            error_text = driver.find_element(By.CLASS_NAME, "swal2-html-container").text
            return {"Roll No": roll_no, "Status": f"❌ {error_text}"}
        except:
            pass

        # ===== PARSE HTML =====
        soup = BeautifulSoup(driver.page_source, "html.parser")
        student_name = roll_number = aggregate_marks = None
        subject_data = {}

        # Student Info Logic
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if text == "Student's Name":
                student_name = td.find_next_sibling("td").get_text(strip=True)
            elif text == "Roll Number":
                roll_number = td.find_next_sibling("td").get_text(strip=True)
            elif text == "Aggregate Marks:":
                aggregate_marks = td.find_next_sibling("td").get_text(strip=True)

        # Subject Marks Logic (Exact matches your script)
        marks_table = soup.find("table", {"class": "text_center"})
        if marks_table:
            for row in marks_table.find_all("tr")[3:]:
                cells = row.find_all("td")
                if len(cells) >= 8:
                    subject = cells[0].get_text(strip=True)
                    theory = cells[3].get_text(strip=True)
                    practical = cells[4].get_text(strip=True)
                    total = cells[7].get_text(strip=True)
                    
                    subject_data[f"{subject}_Theory"] = theory
                    subject_data[f"{subject}_Practical"] = practical
                    subject_data[f"{subject}_Total"] = total

        row = {
            "Roll No": roll_number or roll_no,
            "Student Name": student_name,
            "Aggregate Marks": aggregate_marks
        }
        row.update(subject_data)
        return row

    except Exception as e:
        logger.error(f"Scraper error for {roll_no}: {e}")
        return {"Roll No": roll_no, "Status": "Failed to load"}
    finally:
        driver.quit()

# ================= TELEGRAM HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("BSEB Bot Online. Send /batch <roll_code> <start_roll> <count>")

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Usage: /batch 31082 26010001 5")
        return

    roll_code = context.args[0]
    start_roll = int(context.args[1])
    count = min(int(context.args[2]), 25) # Safety cap

    status_msg = await update.message.reply_text(f"⏳ Processing {count} results... please wait.")
    
    all_results = []
    for i in range(count):
        curr_roll = str(start_roll + i)
        res = get_bseb_result(roll_code, curr_roll)
        all_results.append(res)
        # Update user every 5 results
        if (i + 1) % 5 == 0:
            await status_msg.edit_text(f"⏳ Progress: {i+1}/{count} fetched...")

    # Build CSV using Pandas
    df = pd.DataFrame(all_results)
    csv_stream = io.BytesIO()
    df.to_csv(csv_stream, index=False)
    csv_stream.seek(0)

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=csv_stream,
        filename=f"BSEB_Results_{roll_code}.csv",
        caption=f"✅ Finished! Processed {len(all_results)} results."
    )
    await status_msg.delete()

# ================= RUNNER =================
if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))

    print("🚀 Bot starting...")
    # This prevents the conflict by dropping updates from the "Ghost" instance
    app.run_polling(drop_pending_updates=True)
