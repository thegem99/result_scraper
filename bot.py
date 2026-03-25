from flask import Flask, request, jsonify
import os

app = Flask(__name__)


# ================= HOME =================
@app.route("/")
def home():
    return {"status": "running", "message": "API is live"}


# ================= MAIN API =================
@app.route("/batch", methods=["GET"])
def batch():
    rollcode = request.args.get("rollcode")
    start = request.args.get("start")
    count = request.args.get("count")

    if not rollcode or not start or not count:
        return jsonify({"error": "rollcode, start, count required"}), 400

    start = int(start)
    count = int(count)

    results = []

    for i in range(count):
        roll_no = str(start + i)

        # TEMP MOCK RESPONSE (replace later with scraper)
        results.append({
            "roll_no": roll_no,
            "rollcode": rollcode,
            "status": "success",
            "student_name": None,
            "aggregate_marks": None,
            "subjects": {}
        })

    return jsonify(results)


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
