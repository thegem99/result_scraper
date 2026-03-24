import os
import time
import io
import csv
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

# Enable logging to see errors in Railway logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ================= SELENIUM RESULT FETCHER =================
def get_bseb_result(roll_code, roll_no):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Path for Google Chrome in Railway/Nixpacks
    options.binary_location = "/usr/bin/google-chrome"
    
    # Selenium 4.11.2 automatically finds /usr/bin/chromedriver if installed via Nix
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get("https://www.bsebexam.com/")
        wait = WebDriverWait(driver, 15)

        # 1. Wait for CAPTCHA value to be injected into the data attribute
        wait.until(lambda d: d.execute_script(
            "return document.getElementById('generatedCaptcha')?.dataset?.value"
        ) is not None)
        
        captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

        # 2. Fill the form
        driver.find_element(By.ID, "rollcode").send_keys(str(roll_code))
        driver.find_element(By.ID, "rollno").send_keys(str(roll_no))
        driver.find_element(By.ID, "captchaInput").send_keys(captcha)
        
        # 3. Submit
        submit_btn = driver.find_element(By.ID, "btnSubmit")
        submit_btn.click()

        # 4. Wait for the results page to load
        time.sleep(3) 
        html = driver.page_source
        
        soup = BeautifulSoup(html, "html.parser")
        
        # --- Data Extraction ---
        student_name = "Not Found"
        aggregate_marks = "N/A"
        
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if "Student's Name" in text:
                student_name = td.find_next_sibling("td").get_text(strip=True)
            elif "Aggregate Marks" in text:
                # Look for the next td which contains the actual marks
                next_td = td.find_next_sibling("td")
                if next_td:
                    aggregate_marks = next_td.get_text(strip=True)

        subjects = []
        marks_table = soup.find("table", {"class": "text_center"})
        if marks_table:
            rows = marks_table.find_all("tr")
            # Usually rows 0-2 are headers; data starts from row 3
            for row in rows[3:]:
                cells = row.find_all("td")
                if len(cells) >= 8:
                    subjects.append({
                        "Subject": cells[0].get_text(strip=True),
                        "Total": cells[7].get_text(strip=True)
                    })

        return {
            "Roll No": roll_no,
            "Name": student_name,
            "Aggregate Marks": aggregate_marks,
            "Subjects": subjects
        }

    finally:
        # ALWAYS quit the driver to prevent memory leaks on Railway
        driver.quit()

# ================= TELEGRAM BOT HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Use the batch command to fetch results.\n\n"
        "Format: /batch <roll_code> <start_roll> <count>\n"
        "Example: /batch 32065 26030001 5"
    )

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Usage: /batch <roll_code> <start_roll> <count>")
        return

    roll_code = context.args[0]
    try:
        start_roll = int(context.args[1])
        count = int(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ Roll number and count must be numbers.")
        return

    # Limit count to 20 to prevent Railway timeouts or bot blocking
    count = min(count, 20)
    status_msg = await update.message.reply_text(f"⏳ Fetching {count} results... please wait.")

    results = []
    for i in range(count):
        curr_roll = str(start_roll + i)
        try:
            res = get_bseb_result(roll_code, curr_roll)
            results.append(res)
        except Exception as e:
            logging.error(f"Error fetching {curr_roll}: {e}")
            results.append({"Roll No": curr_roll, "Name": "Error", "Aggregate Marks": "Failed", "Subjects": []})

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll No", "Name", "Total Marks", "Subject Details"])
    
    for r in results:
        subj_str = " | ".join([f"{s['Subject']}:{s['Total']}" for s in r.get("Subjects", [])])
        writer.writerow([r["Roll No"], r["Name"], r["Aggregate Marks"], subj_str])

    output.seek(0)
    
    # Send the document
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(output.getvalue().encode()),
        filename=f"BSEB_Results_{roll_code}.csv",
        caption=f"✅ Successfully processed {len(results)} records."
    )
    await status_msg.delete()

# ================= MAIN ENTRY POINT =================
if __name__ == "__main__":
    TOKEN = "8623695113:AAF3VAXr4mbmoWGYjbCHJ_eTrnVHyDwfsP4"
    if not TOKEN:
        print("❌ FATAL: TOKEN environment variable is missing!")
        exit(1)

    # Build the application
    app = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))

    print("🚀 Bot is running... (Polling started)")
    
    # drop_pending_updates=True prevents the 'Conflict' error on restart
    app.run_polling(drop_pending_updates=True)
