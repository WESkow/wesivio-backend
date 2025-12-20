from flask import Flask, request, jsonify
import os
import json
import re
import uuid
import base64
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI

# -------------------------------------------------
# APP
# -------------------------------------------------
app = Flask(__name__)

# -------------------------------------------------
# OPENAI CLIENT (GPT-4o VISION)
# -------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------
@app.route("/ping", methods=["GET"])
def ping():
    return {"status": "alive"}, 200


# -------------------------------------------------
# BARCODE DATABASE (LOCAL FALLBACK)
# -------------------------------------------------
BARCODE_DB = {
    "5000112637922": {
        "name": "Coke Zero (330ml)",
        "grams": 330,
        "nutrition": {"calories": 1, "protein": 0, "carbs": 0, "fat": 0},
    },
    "5000159484695": {
        "name": "Monster Ultra (500ml)",
        "grams": 500,
        "nutrition": {"calories": 10, "protein": 0, "carbs": 2, "fat": 0},
    },
}


@app.route("/barcode", methods=["GET", "POST"])
def barcode_lookup():
    data = request.get_json(silent=True) or {}
    code = request.args.get("code") or data.get("barcode")

    if not code:
        return jsonify({"error": "No barcode provided"}), 400

    item = BARCODE_DB.get(code)
    if not item:
        return jsonify({"error": "Barcode not found"}), 404

    return jsonify({
        "code": code,
        "name": item["name"],
        "grams": item["grams"],
        "nutrition": item["nutrition"],
    })


# -------------------------------------------------
# IMAGE → AI ANALYSIS
# -------------------------------------------------
SYSTEM_PROMPT = """
You are a professional nutrition analyst.

Analyze the food in the image.
Detect ALL visible food items.

Return JSON ONLY in this format:

{
  "items": [
    {
      "food": "name",
      "grams": number,
      "calories": number,
      "protein": number,
      "carbs": number,
      "fat": number
    }
  ],
  "total": {
    "grams": number,
    "calories": number,
    "protein": number,
    "carbs": number,
    "fat": number
  }
}
"""

def _analyze_image(image_b64: str):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this food image."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        },
                    },
                ],
            },
        ],
        temperature=0.1,
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


@app.route("/analyze", methods=["POST"])
@app.route("/scan-image", methods=["POST"])
def analyze_image():
    try:
        data = request.get_json(force=True)
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        result = _analyze_image(image_b64)

        # Pick main item (highest calories)
        items = result.get("items", [])
        main = max(items, key=lambda x: x.get("calories", 0)) if items else None

        response = {
            "items": items,
            "total": result.get("total"),
            "raw": result,
        }

        if main:
            response["name"] = main["food"]
            response["grams"] = main["grams"]
            response["nutrition"] = {
                "calories": main["calories"],
                "protein": main["protein"],
                "carbs": main["carbs"],
                "fat": main["fat"],
            }

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------
# SAVE MEAL (OPTIONAL)
# -------------------------------------------------
@app.route("/save_meal", methods=["POST"])
def save_meal():
    data = request.json or {}
    record = {
        "user_id": data.get("user_id"),
        "items": data.get("items"),
        "total": data.get("total"),
        "timestamp": datetime.utcnow().isoformat(),
    }

    with open("meals.json", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return jsonify({"status": "ok"})


# -------------------------------------------------
# USER AUTH
# -------------------------------------------------
USERS_FILE = "users.json"


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    users = load_users()
    if email in users:
        return jsonify({"error": "Email exists"}), 400

    users[email] = {
        "user_id": str(uuid.uuid4()),
        "password": generate_password_hash(password),
    }
    save_users(users)

    return jsonify({"status": "ok", "user_id": users[email]["user_id"]})


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    users = load_users()
    if email not in users:
        return jsonify({"error": "User not found"}), 400

    if not check_password_hash(users[email]["password"], password):
        return jsonify({"error": "Invalid password"}), 400

    return jsonify({"status": "ok", "user_id": users[email]["user_id"]})


@app.route("/", methods=["GET"])
def home():
    return "WESIVIO API running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
