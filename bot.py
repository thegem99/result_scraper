import os
import time
import io
import csv
import logging
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

# ================= SELENIUM RESULT FETCHER =================
def get_bseb_result(roll_code, roll_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Path for Chrome in Railway/Nixpacks
    options.binary_location = "/usr/bin/google-chrome"
    
    # FORCE use of the system chromedriver to avoid Status Code 127
    # This points to the driver installed via nixpacks.toml
    service = Service("/usr/bin/chromedriver")
    
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        driver.get("https://www.bsebexam.com/")
        wait = WebDriverWait(driver, 15)

        # 1. Wait for CAPTCHA
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ) is not None)
        
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        # 2. Fill the form
        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # 3. Submit using JavaScript (more reliable in headless)
        driver.execute_script("document.getElementById('btnSubmit').click()")

        # 4. Wait for the results to load (increased time for slow gov servers)
        time.sleep(5) 
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        # --- Robust Extraction Logic ---
        student_name = "Not Found"
        aggregate_marks = "N/A"
        
        # Strategy: Find all table cells and look for keywords
        all_tds = soup.find_all("td")
        for i, td in enumerate(all_tds):
            text = td.get_text(strip=True)
            # Use 'in' keyword for fuzzy matching
            if "Student's Name" in text and i + 1 < len(all_tds):
                student_name = all_tds[i+1].get_text(strip=True)
            elif "Aggregate Marks" in text and i + 1 < len(all_tds):
                aggregate_marks = all_tds[i+1].get_text(strip=True)

        subjects = []
        # Find the main marks table
        marks_table = soup.find("table", {"class": "text_center"})
        if marks_table:
            rows = marks_table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                # Look for rows that actually contain marks (usually 7-8 columns)
                if len(cells) >= 7:
                    sub_name = cells[0].get_text(strip=True)
                    # Skip header rows
                    if "Subject" in sub_name or "Code" in sub_name:
                        continue
                    subjects.append({
                        "Subject": sub_name,
                        "Total": cells[-1].get_text(strip=True) # Usually the last column
                    })

        return {
            "Roll No": roll_no,
            "Name": student_name,
            "Aggregate Marks": aggregate_marks,
            "Subjects": subjects
        }

    except Exception as e:
        logger.error(f"Error scraping {roll_no}: {str(e)}")
        raise e
    finally:
        driver.quit()

# ================= TELEGRAM BOT HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "BSEB Result Bot is Ready!\n"
        "Usage: /batch <roll_code> <start_roll> <count>\n"
        "Example: /batch 32065 26030001 5"
    )

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Missing arguments. Example: /batch 32065 26030001 5")
        return

    roll_code = context.args[0]
    try:
        start_roll = int(context.args[1])
        count = int(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ Start roll and count must be numbers.")
        return

    # Cap count at 20 for Railway stability
    count = min(count, 20)
    status_msg = await update.message.reply_text(f"⏳ Fetching {count} results. This takes ~10s per result...")

    results = []
    for i in range(count):
        curr_roll = str(start_roll + i)
        try:
            res = get_bseb_result(roll_code, curr_roll)
            results.append(res)
        except Exception as e:
            results.append({"Roll No": curr_roll, "Name": "System Error", "Aggregate Marks": "Failed", "Subjects": []})

    # CSV Generation
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll No", "Name", "Total Marks", "Subject Marks"])
    
    for r in results:
        subj_str = " | ".join([f"{s['Subject']}:{s['Total']}" for s in r.get("Subjects", [])])
        writer.writerow([r["Roll No"], r["Name"], r["Aggregate Marks"], subj_str])

    output.seek(0)
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(output.getvalue().encode()),
        filename=f"Results_{roll_code}.csv",
        caption=f"✅ Done! Processed {len(results)} records."
    )
    await status_msg.delete()

# ================= MAIN =================
if __name__ == "__main__":
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        print("❌ TOKEN missing!")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))

    print("🚀 Bot is starting...")
    # drop_pending_updates prevents the 'Conflict' error
    app.run_polling(drop_pending_updates=True)
