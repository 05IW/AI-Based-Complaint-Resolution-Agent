from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import random
import json
import urllib.request
import urllib.error

app = Flask(__name__)
import os

CORS(app)

DATABASE = "complaints.db"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/gemini-3.8-flash:generateContent"
)

def init_database():

    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT UNIQUE,
            complaint TEXT,
            category TEXT,
            priority TEXT,
            department TEXT,
            resolution TEXT,
            status TEXT
        )
    """)

    conn.commit()
    conn.close()


init_database()


@app.route("/")
def home():

    return "AI-BASED COMPLAINT RESOLUTION AGENT BACKEND IS RUNNING!"


# =========================
# 🤖 REAL GEMINI AI ANALYSIS
# =========================

@app.route("/analyze", methods=["POST"])
def analyze():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "No complaint received"
        }), 400

    complaint = data.get("complaint", "").strip()

    if not complaint:
        return jsonify({
            "error": "Please enter a complaint"
        }), 400

    prompt = f"""
You are an AI Complaint Resolution Agent.

Analyze the following customer complaint:

{complaint}

Return ONLY valid JSON in exactly this format:

{{
  "category": "Complaint category",
  "priority": "Low, Medium, or High",
  "department": "Responsible department",
  "resolution": "Short suggested resolution"
}}

Do not add markdown.
Do not add explanations outside JSON.
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    try:

        req = urllib.request.Request(
            GEMINI_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=60) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

        ai_text = result["candidates"][0]["content"]["parts"][0]["text"]

        # Remove possible markdown formatting
        ai_text = ai_text.strip()

        if ai_text.startswith("```"):
            ai_text = ai_text.replace("```json", "")
            ai_text = ai_text.replace("```", "")
            ai_text = ai_text.strip()

        ai_result = json.loads(ai_text)

        return jsonify({
            "category": ai_result.get(
                "category",
                "General Issue"
            ),

            "priority": ai_result.get(
                "priority",
                "Medium"
            ),

            "department": ai_result.get(
                "department",
                "Customer Support"
            ),

            "resolution": ai_result.get(
                "resolution",
                "Our support team will review your complaint."
            )
        })

    except urllib.error.HTTPError as e:

        error_message = e.read().decode("utf-8")

        print("Gemini API Error:", error_message)

        return jsonify({
            "error": "Gemini AI API error",
            "details": error_message
        }), 500

    except Exception as e:

        print("AI Error:", str(e))

        return jsonify({
            "error": "AI analysis failed",
            "details": str(e)
        }), 500


# =========================
# SUBMIT COMPLAINT
# =========================

@app.route("/submit", methods=["POST"])
def submit():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "No complaint data received"
        }), 400

    complaint_id = "CRA" + str(random.randint(1000, 9999))

    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        INSERT INTO complaints
        (
            complaint_id,
            complaint,
            category,
            priority,
            department,
            resolution,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_id,
        data.get("complaint", ""),
        data.get("category", ""),
        data.get("priority", ""),
        data.get("department", ""),
        data.get("resolution", ""),
        "Submitted"
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "complaint_id": complaint_id,
        "status": "Submitted"
    })


# =========================
# CHECK STATUS
# =========================

@app.route("/status/<complaint_id>", methods=["GET"])
def status(complaint_id):

    conn = sqlite3.connect(DATABASE)

    row = conn.execute("""
        SELECT
            complaint_id,
            category,
            priority,
            department,
            resolution,
            status
        FROM complaints
        WHERE complaint_id = ?
    """, (complaint_id,)).fetchone()

    conn.close()

    if row is None:

        return jsonify({
            "error": "Complaint ID not found"
        }), 404

    return jsonify({
        "complaint_id": row[0],
        "category": row[1],
        "priority": row[2],
        "department": row[3],
        "resolution": row[4],
        "status": row[5]
    })


# =========================
# ADMIN - ALL COMPLAINTS
# =========================

@app.route("/admin/complaints", methods=["GET"])
def admin_complaints():

    conn = sqlite3.connect(DATABASE)

    rows = conn.execute("""
        SELECT
            complaint_id,
            complaint,
            category,
            priority,
            department,
            resolution,
            status
        FROM complaints
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    complaints = []

    for row in rows:

        complaints.append({
            "complaint_id": row[0],
            "complaint": row[1],
            "category": row[2],
            "priority": row[3],
            "department": row[4],
            "resolution": row[5],
            "status": row[6]
        })

    return jsonify(complaints)


# =========================
# ADMIN - UPDATE STATUS
# =========================

@app.route("/admin/update-status", methods=["POST"])
def update_status():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "No data received"
        }), 400

    complaint_id = data.get("complaint_id")
    new_status = data.get("status")

    allowed_status = [
        "Submitted",
        "In Progress",
        "Resolved"
    ]

    if new_status not in allowed_status:

        return jsonify({
            "error": "Invalid status"
        }), 400

    conn = sqlite3.connect(DATABASE)

    cursor = conn.execute("""
        UPDATE complaints
        SET status = ?
        WHERE complaint_id = ?
    """, (
        new_status,
        complaint_id
    ))

    conn.commit()

    updated = cursor.rowcount

    conn.close()

    if updated == 0:

        return jsonify({
            "error": "Complaint ID not found"
        }), 404

    return jsonify({
        "message": "Status updated successfully",
        "complaint_id": complaint_id,
        "status": new_status
    })


# =========================
# START SERVER
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )