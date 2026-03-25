from flask import Flask, request, render_template_string, Response
import requests
from bs4 import BeautifulSoup
import os
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
BASE_URL = "https://www.bsebexam.com"
CACHE = {}
SUBJECTS = ["english","hindi","physics","chemistry","mathematics","biology"]

# ===== SCRAPING LOGIC =====
def get_session():
    return requests.Session()

def get_token(session):
    res = session.get(BASE_URL + "/", timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    token = soup.find("input", {"name": "__RequestVerificationToken"})
    return token.get("value") if token else None

def normalize_subject(name):
    name = name.lower().strip()
    if "math" in name: return "mathematics"
    if "bio" in name: return "biology"
    if "physic" in name: return "physics"
    if "chem" in name: return "chemistry"
    if "english" in name: return "english"
    if "hindi" in name: return "hindi"
    return None

def fetch_result(session, token, rollcode, rollno):
    url = BASE_URL + "/Result/GetResult"
    payload = {"rollcode": rollcode,"rollno":rollno,"captcha":"123456","__RequestVerificationToken": token}
    headers = {"User-Agent":"Mozilla/5.0","Origin":BASE_URL,"Referer":BASE_URL+"/","Content-Type":"application/x-www-form-urlencoded"}
    res = session.post(url,data=payload,headers=headers,timeout=20)
    soup = BeautifulSoup(res.text,"html.parser")
    data={"name":"","father":"","roll_no":rollno,"school":"","total":"","subjects":{}}
    for row in soup.find_all("tr"):
        cols = [c.get_text(" ", strip=True) for c in row.find_all(["td","th"])]
        if len(cols)<2: continue
        key = cols[0].lower().strip()
        value = cols[-1].strip()
        if "student" in key and "name" in key: data["name"]=value
        elif "father" in key: data["father"]=value
        elif "school" in key: data["school"]=value
        elif "aggregate" in key: data["total"]=value
        elif len(cols)>=5:
            norm=normalize_subject(cols[0])
            if norm: data["subjects"][norm]=value
    return data

# ===== HOME PAGE =====
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>BSEB Result Portal</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
<style>
body {
    margin:0;
    padding:0;
    font-family:'Roboto',sans-serif;
    height:100vh;
    overflow:hidden;
    color:white;
    display:flex;
    justify-content:center;
    align-items:center;
    background:#1e1e2f;
}
#particles-js {
    position:absolute;
    width:100%;
    height:100%;
    top:0;
    left:0;
    z-index:1;
}
.box {
    background: rgba(255,255,255,0.95);
    color: black;
    padding: 40px;
    border-radius: 15px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
    text-align: center;
    width: 400px;
    animation: slideIn 1s ease-out;
    position: relative;   /* ensure it's above the particles */
    z-index: 2;
}
input, button {
    width: 100%;
    padding: 12px;
    margin: 10px 0;
    border-radius: 6px;
    border: none;
    outline: none;
    font-weight: bold;
    transition: 0.3s;
}
input {
    border: 2px solid #764ba2;
}
input:focus {
    border-color: #ff4d6d;
    box-shadow: 0 0 10px rgba(255,77,109,0.5);
}
button {
    background: linear-gradient(90deg,#667eea,#764ba2);
    color:white;
    cursor:pointer;
}
button:hover {
    transform: scale(1.05);
}
@keyframes slideIn {
    from {opacity:0; transform:translateY(-50px);}
    to {opacity:1; transform:translateY(0);}
}
h2 {
    margin-bottom:20px;
    text-transform:uppercase;
    color:#764ba2;
}
</style>
</head>
<body>
<div id="particles-js"></div>
<div class="box">
<h2>BSEB Result 2026</h2>
<form action="/view" method="get">
<input name="rollcode" placeholder="Roll Code" required>
<input name="rollno" placeholder="Starting Roll Number" required>
<input name="count" placeholder="Count (max 100)" value="1">
<button type="submit">Get Result</button>
</form>
</div>

<script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
<script>
particlesJS("particles-js", {
  "particles": {
    "number": {"value":60},
    "size": {"value":3},
    "move": {"speed":2},
    "line_linked": {"enable":true}
  },
  "interactivity": {
    "events": {"onhover":{"enable":true,"mode":"repulse"}}
  }
});
</script>
</body>
</html>
""")

# ===== VIEW PAGE WITH PARALLEL FETCH =====
@app.route("/view")
def view():
    rollcode = request.args.get("rollcode")
    rollno = request.args.get("rollno")
    count = min(max(int(request.args.get("count",1)),1),100)  # ensure 1 <= count <= 100
    session = get_session()
    results = []

    def fetch_single(rn):
        try:
            token = get_token(session)
            return fetch_result(session, token, rollcode, rn)
        except:
            return {"name":"Error","father":"","roll_no":rn,"school":"","total":"","subjects":{}}

    roll_numbers = [str(int(rollno)+i) for i in range(count)]

    with ThreadPoolExecutor(max_workers=min(count,100)) as executor:
        future_to_roll = {executor.submit(fetch_single,rn): rn for rn in roll_numbers}
        for future in as_completed(future_to_roll):
            results.append(future.result())

    results.sort(key=lambda x:int(x["roll_no"]))
    CACHE["data"] = results

    html = """
<html>
<head>
<style>
body{font-family:Arial;background:#1e1e2f;padding:20px;color:white;}
table{width:100%;border-collapse:collapse;background:#2c2c3e;color:white;box-shadow:0 5px 15px rgba(0,0,0,0.2);}
th,td{border:1px solid #555;padding:8px;text-align:center;transition:0.3s;}
th{background:#764ba2;position:sticky;top:0;}
tr:hover{background:#3d3d5c;transform:scale(1.01);}
button{padding:10px 20px;margin:10px;background:linear-gradient(90deg,#667eea,#764ba2);border:none;border-radius:6px;color:white;cursor:pointer;transition:0.3s;}
button:hover{transform:scale(1.05);}
</style>
</head>
<body>
<h2 align="center">Result Sheet</h2>
<div style="text-align:center;margin-bottom:15px;">
<a href="/download"><button>Download CSV</button></a>
<a href="/pdf"><button>Download PDF</button></a>
</div>
<table><tr>
"""
    headers = ["Name","Father","Roll No","School","Total"]+[s.title() for s in SUBJECTS]
    for h in headers: html+=f"<th>{h}</th>"
    html+="</tr>"

    for r in results:
        html+="<tr>"
        html+=f"<td>{r['name']}</td><td>{r['father']}</td><td>{r['roll_no']}</td><td>{r['school']}</td><td>{r['total']}</td>"
        for s in SUBJECTS: html+=f"<td>{r['subjects'].get(s,'')}</td>"
        html+="</tr>"
    html+="</table></body></html>"
    return html

# ===== CSV / PDF DOWNLOAD =====
@app.route("/download")
def download():
    results = CACHE.get("data",[])
    def generate():
        header=["Name","Father","Roll No","School","Total"]+[s.title() for s in SUBJECTS]
        yield ",".join(header)+"\n"
        for r in results:
            row=[r["name"],r["father"],r["roll_no"],r["school"],r["total"]]
            for s in SUBJECTS: row.append(r["subjects"].get(s,""))
            yield ",".join(f'"{x}"' for x in row)+"\n"
    return Response(generate(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=results.csv"})

@app.route("/pdf")
def pdf():
    results = CACHE.get("data",[])
    buffer = BytesIO()
    p = canvas.Canvas(buffer,pagesize=letter)
    width,height = letter
    y = height-40
    p.setFont("Helvetica-Bold",16)
    p.drawString(180,y,"BSEB Result Sheet")
    y-=30
    p.setFont("Helvetica",9)
    p.drawString(40,y,"Roll No | Name | Total | English | Hindi | Physics | Chemistry | Mathematics | Biology")
    y-=15
    for r in results:
        if y<50:
            p.showPage()
            y = height-40
        line=f"{r['roll_no']} | {r['name']} | {r['total']} | {r['subjects'].get('english','')} | {r['subjects'].get('hindi','')} | {r['subjects'].get('physics','')} | {r['subjects'].get('chemistry','')} | {r['subjects'].get('mathematics','')} | {r['subjects'].get('biology','')}"
        p.drawString(40,y,line)
        y-=15
    p.save()
    buffer.seek(0)
    return Response(buffer,mimetype='application/pdf',headers={"Content-Disposition":"attachment; filename=results.pdf"})

# ===== RUN APP =====
if __name__=="__main__":
    port=int(os.environ.get("PORT",8080))
    app.run(host="0.0.0.0",port=port)
