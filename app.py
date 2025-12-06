from flask import Flask, request, jsonify
import os
import json
import re
from groq import Groq
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

app = Flask(__name__)

# ----------------------------------------------------------
# LOAD GROQ API KEY
# ----------------------------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------------------------------------
# 🔥 WARM-UP ENDPOINT (USED BY FLUTTER TO WAKE RENDER)
# ----------------------------------------------------------
@app.route("/ping", methods=["GET"])
def ping():
    return {"status": "alive"}, 200


# ----------------------------------------------------------
# BARCODE DATABASE
# ----------------------------------------------------------
BARCODE_DB = {
    "5000112637922": {
        "food": "Coke Zero (330ml)",
        "serving": "330 ml",
        "calories": 1,
        "protein": 0,
        "carbs": 0,
        "fat": 0
    },
    "5000159484695": {
        "food": "Monster Ultra (Sugar Free 500ml)",
        "serving": "500 ml",
        "calories": 10,
        "protein": 0,
        "carbs": 2,
        "fat": 0
    }
}


# ----------------------------------------------------------
# BARCODE LOOKUP
# ----------------------------------------------------------
@app.route("/barcode", methods=["POST"])
def barcode_lookup():
    data = request.get_json(force=True)
    barcode = data.get("barcode")

    if not barcode:
        return jsonify({"error": "No barcode provided"}), 400

    if barcode not in BARCODE_DB:
        return jsonify({"error": "Barcode not found"}), 404

    return jsonify({"item": BARCODE_DB[barcode]})


# ----------------------------------------------------------
# MEAL ANALYSIS ENDPOINT
# ----------------------------------------------------------
@app.route("/analyze", methods=["POST"])
def analyze_image():
    try:
        data = request.get_json(force=True)
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        # SYSTEM PROMPT
        system_prompt = """
        You are a professional nutrition analyst.

        If the image shows a MEAL:
        Identify all major foods (2–5 items) and respond in EXACTLY this format:

        food1 | serving g/ml | calories | protein | carbs | fat
        food2 | serving g/ml | calories | protein | carbs | fat
        food3 | serving g/ml | calories | protein | carbs | fat
        TOTAL | total g/ml | total_cal | total_protein | total_carbs | total_fat

        RULES:
        - ALWAYS estimate serving size.
        - ALWAYS include TOTAL line.
        - NEVER return explanation, markdown or notes.
        - Values must be integers.
        """

        # SEND TO GROQ
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this meal. Follow formatting strictly."},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }},
                    ],
                },
            ],
            temperature=0.1,
            max_completion_tokens=256,
        )

        ai_text = completion.choices[0].message.content.strip()

        # ----------------------------------------------------------
        # PARSE MULTI-LINE FORMAT
        # ----------------------------------------------------------
        lines = [l.strip() for l in ai_text.split("\n") if "|" in l]

        items = []
        total_obj = None

        def to_int(t):
            m = re.search(r"-?\\d+", t)
            return int(m.group(0)) if m else 0

        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 6:
                continue

            food, serving, cal, prot, carb, fat = parts

            entry = {
                "food": food,
                "serving": serving,
                "calories": to_int(cal),
                "protein": to_int(prot),
                "carbs": to_int(carb),
                "fat": to_int(fat),
            }

            if food.lower() == "total":
                total_obj = entry
            else:
                items.append(entry)

        return jsonify({
            "items": items,
            "total": total_obj,
            "raw": ai_text
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------
# HOME ENDPOINT
# ----------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return "WESIVIO Nutrition API (multi-meal + barcode + auth) running."


# ----------------------------------------------------------
# USER AUTHENTICATION SYSTEM
# ----------------------------------------------------------
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=4)


@app.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    users = load_users()

    if email in users:
        return jsonify({"error": "Email already exists"}), 400

    user_id = str(uuid.uuid4())
    hashed_pw = generate_password_hash(password)

    users[email] = {
        "user_id": user_id,
        "password": hashed_pw
    }

    save_users(users)

    return jsonify({"status": "ok", "user_id": user_id})


@app.route("/login", methods=["POST"])
def login_user():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    users = load_users()

    if email not in users:
        return jsonify({"error": "User not found"}), 400

    user_record = users[email]

    if not check_password_hash(user_record["password"], password):
        return jsonify({"error": "Incorrect password"}), 400

    return jsonify({"status": "ok", "user_id": user_record["user_id"]})


# ----------------------------------------------------------
# FLASK DEV SERVER
# ----------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
