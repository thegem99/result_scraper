import os
import asyncio
import time
import io
import csv
from bs4 import BeautifulSoup

from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ================= SELENIUM RESULT FETCHER =================
def get_bseb_result(roll_code, roll_no):
    options = webdriver.ChromeOptions()
    options.binary_location = "/usr/bin/google-chrome"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 10)

    driver.get("https://www.bsebexam.com/")
    
    wait.until(lambda d: d.execute_script(
        "return document.getElementById('generatedCaptcha').dataset.value"
    ) is not None)
    captcha = driver.execute_script("return document.getElementById('generatedCaptcha').dataset.value")

    driver.find_element(By.ID, "rollcode").send_keys(roll_code)
    driver.find_element(By.ID, "rollno").send_keys(roll_no)
    driver.find_element(By.ID, "captchaInput").send_keys(captcha)
    driver.execute_script("document.getElementById('resultForm').submit()")
    
    time.sleep(2)
    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "html.parser")
    student_name = roll_number = aggregate_marks = "N/A"

    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if text == "Student's Name":
            student_name = td.find_next_sibling("td").get_text(strip=True)
        elif text == "Roll Number":
            roll_number = td.find_next_sibling("td").get_text(strip=True)
        elif text == "Aggregate Marks:":
            aggregate_marks = td.find_next_sibling("td").get_text(strip=True)

    subjects = []
    marks_table = soup.find("table", {"class": "text_center"})
    if marks_table:
        for row in marks_table.find_all("tr")[3:]:
            cells = row.find_all("td")
            if len(cells) >= 8:
                subjects.append({
                    "Subject": cells[0].get_text(strip=True),
                    "Theory": cells[3].get_text(strip=True),
                    "Practical": cells[4].get_text(strip=True),
                    "Total": cells[7].get_text(strip=True)
                })

    return {"Roll No": roll_number, "Name": student_name, "Aggregate Marks": aggregate_marks, "Subjects": subjects}

# ================= TELEGRAM BOT HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Send /batch <roll_code> <start_roll> <count> to fetch results.\nExample: /batch 32065 26030001 10"
    )

async def batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        roll_code = context.args[0]
        start_roll = int(context.args[1])
        count = int(context.args[2])
    except (IndexError, ValueError):
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Usage: /batch <roll_code> <start_roll> <count>")
        return

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Fetching results... This may take some time.")

    results = []
    for i in range(count):
        roll_no = str(start_roll + i)
        try:
            res = get_bseb_result(roll_code, roll_no)
            results.append(res)
        except Exception as e:
            results.append({"Roll No": roll_no, "Name": "Error fetching", "Aggregate Marks": str(e), "Subjects": []})

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll No", "Name", "Aggregate Marks", "Subjects"])
    for r in results:
        subjects_str = "; ".join([f"{s['Subject']}:{s['Total']}" for s in r["Subjects"]])
        writer.writerow([r["Roll No"], r["Name"], r["Aggregate Marks"], subjects_str])
    output.seek(0)
    await context.bot.send_document(chat_id=update.effective_chat.id, document=output, filename="bseb_results.csv")

# ================= MAIN BOT =================
async def main():
    TOKEN = os.environ.get("TOKEN")
    if not TOKEN:
        raise ValueError("Please set the TOKEN environment variable!")

    bot_instance = Bot(TOKEN)
    # Await webhook deletion to avoid RuntimeWarning
    await bot_instance.delete_webhook()
    print("Webhook cleared.")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("batch", batch))

    print("Bot is running...")
    await app.run_polling()

# Run main with asyncio
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
