from flask import Flask, request, render_template_string, Response, jsonify
import requests
from bs4 import BeautifulSoup
import os
import time
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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
    payload = {"rollcode": rollcode,"rollno": rollno,"captcha":"123456","__RequestVerificationToken": token}
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
body{margin:0;padding:0;font-family:'Roboto',sans-serif;height:100vh;background:#1e1e2f;overflow:hidden;color:white;display:flex;justify-content:center;align-items:flex-start;padding-top:50px;}
#particles-js{position:absolute;width:100%;height:100%;top:0;left:0;z-index:1;}
.box{background:rgba(255,255,255,0.95);color:black;padding:40px;border-radius:15px;box-shadow:0 10px 40px rgba(0,0,0,0.3);text-align:center;width:400px;position:relative;z-index:2;animation:slideIn 1s ease-out;}
input,button{width:100%;padding:12px;margin:10px 0;border-radius:6px;border:none;outline:none;font-weight:bold;transition:0.3s;}
input{border:2px solid #764ba2;}
input:focus{border-color:#ff4d6d;box-shadow:0 0 10px rgba(255,77,109,0.5);}
button{background:linear-gradient(90deg,#667eea,#764ba2);color:white;cursor:pointer;}
button:hover{transform:scale(1.05);}
@keyframes slideIn{from{opacity:0; transform:translateY(-50px);}to{opacity:1; transform:translateY(0);}}
h2{margin-bottom:20px;text-transform:uppercase;color:#764ba2;}

/* Spinner overlay */
#spinner-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:9999;justify-content:center;align-items:center;}
.spinner{border:8px solid #f3f3f3;border-top:8px solid #667eea;border-radius:50%;width:60px;height:60px;animation:spin 1s linear infinite;}
@keyframes spin{0%{transform:rotate(0deg);}100%{transform:rotate(360deg);}}
#results-container{margin-top:30px;width:90%;max-width:1200px;}
table{width:100%;border-collapse:collapse;background:#2c2c3e;color:white;box-shadow:0 5px 15px rgba(0,0,0,0.2);}
th,td{border:1px solid #555;padding:8px;text-align:center;transition:0.3s;}
th{background:#764ba2;position:sticky;top:0;}
tr:hover{background:#3d3d5c;transform:scale(1.01);}
</style>
</head>
<body>
<div id="particles-js"></div>
<div class="box">
<h2>BSEB Result 2026</h2>
<form id="result-form">
<input name="rollcode" placeholder="Roll Code" required>
<input name="rollno" placeholder="Starting Roll Number" required>
<input name="count" placeholder="Count (max 50)" value="1">
<button type="submit">Get Result</button>
</form>
</div>

<div id="spinner-overlay"><div class="spinner"></div></div>

<div id="results-container"></div>

<script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
<script>
particlesJS("particles-js",{
  "particles":{"number":{"value":60},"size":{"value":3},"move":{"speed":2},"line_linked":{"enable":true}},
  "interactivity":{"events":{"onhover":{"enable":true,"mode":"repulse"}}}
});

document.getElementById('result-form').onsubmit = async function(e){
    e.preventDefault();
    const overlay = document.getElementById('spinner-overlay');
    overlay.style.display='flex';
    const formData = new FormData(this);
    const params = new URLSearchParams(formData).toString();
    try{
        const res = await fetch('/ajax_view?' + params);
        const html = await res.text();
        document.getElementById('results-container').innerHTML = html;
    }catch(err){
        alert("Error fetching results");
    }finally{
        overlay.style.display='none';
    }
}
</script>
</body>
</html>
""")

# ===== AJAX VIEW FOR RESULTS =====
@app.route("/ajax_view")
def ajax_view():
    rollcode=request.args.get("rollcode")
    rollno=request.args.get("rollno")
    count=min(int(request.args.get("count",1)),50)
    session=get_session()
    results=[]
    for i in range(count):
        rn=str(int(rollno)+i)
        token=get_token(session)
        try: res=fetch_result(session,token,rollcode,rn)
        except: res={"name":"Error","father":"","roll_no":rn,"school":"","total":"","subjects":{}}
        results.append(res)
        time.sleep(0.2)
    CACHE["data"]=results
    # generate table HTML
    html="<div style='text-align:center;margin-bottom:15px;'>"
    html+='<a href="/download"><button>Download CSV</button></a> '
    html+='<a href="/pdf"><button>Download PDF</button></a></div>'
    html+="<table><tr>"
    headers=["Name","Father","Roll No","School","Total"]+[s.title() for s in SUBJECTS]
    for h in headers: html+=f"<th>{h}</th>"
    html+="</tr>"
    for r in results:
        html+="<tr>"
        html+=f"<td>{r['name']}</td><td>{r['father']}</td><td>{r['roll_no']}</td><td>{r['school']}</td><td>{r['total']}</td>"
        for s in SUBJECTS: html+=f"<td>{r['subjects'].get(s,'')}</td>"
        html+="</tr>"
    html+="</table>"
    return html

# ===== CSV & PDF =====
@app.route("/download")
def download():
    results=CACHE.get("data",[])
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
    results=CACHE.get("data",[])
    buffer=BytesIO()
    p=canvas.Canvas(buffer,pagesize=letter)
    width,height=letter
    y=height-40
    p.setFont("Helvetica-Bold",16)
    p.drawString(180,y,"BSEB Result Sheet")
    y-=30
    p.setFont("Helvetica",9)
    p.drawString(40,y,"Roll No | Name | Total | English | Hindi | Physics | Chemistry | Mathematics | Biology")
    y-=15
    for r in results:
        if y<50:
            p.showPage()
            y=height-40
        line=f"{r['roll_no']} | {r['name']} | {r['total']} | {r['subjects'].get('english','')} | {r['subjects'].get('hindi','')} | {r['subjects'].get('physics','')} | {r['subjects'].get('chemistry','')} | {r['subjects'].get('mathematics','')} | {r['subjects'].get('biology','')}"
        p.drawString(40,y,line)
        y-=15
    p.save()
    buffer.seek(0)
    return Response(buffer,mimetype='application/pdf',headers={"Content-Disposition":"attachment; filename=results.pdf"})

# ===== RUN =====
if __name__=="__main__":
    port=int(os.environ.get("PORT",8080))
    app.run(host="0.0.0.0",port=port)
