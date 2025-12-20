from flask import Flask, request, jsonify
import os
import json
import re
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq

app = Flask(__name__)

# -------------------------------------------------
# GROQ CLIENT
# -------------------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# -------------------------------------------------
# HEALTH CHECK (USED BY FLUTTER)
# -------------------------------------------------
@app.route("/ping", methods=["GET"])
def ping():
    return {"status": "alive"}, 200


# -------------------------------------------------
# SIMPLE BARCODE DATABASE
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
    code = None

    if request.method == "GET":
        code = request.args.get("code")
    else:
        data = request.get_json(force=True) or {}
        code = data.get("barcode")

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
# AI IMAGE ANALYSIS
# -------------------------------------------------
SYSTEM_PROMPT = """
You are a professional nutrition analyst.

You receive a photo of a meal.
Detect ALL visible food items and estimate nutrition.

Respond EXACTLY in this format, one item per line:

food | serving g/ml | calories | protein | carbs | fat

End with:
TOTAL | total g/ml | total_cal | total_protein | total_carbs | total_fat
"""

def _to_int(text):
    m = re.search(r"-?\d+", str(text))
    return int(m.group(0)) if m else 0

def _extract_grams(serving):
    m = re.search(r"(\d+)\s*(g|gram|grams|ml)", serving, re.I)
    return int(m.group(1)) if m else 100


def analyze_image_b64(image_b64):
    completion = client.chat.completions.create(
        model="llama-3.2-vision-preview",  # ✅ VALID GROQ MODEL
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this meal."},
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
        max_completion_tokens=512,
    )

    raw = completion.choices[0].message.content.strip()
    lines = [l for l in raw.split("\n") if "|" in l]

    items = []
    total = None

    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 6:
            continue

        food, serving, cal, prot, carb, fat = parts

        entry = {
            "food": food,
            "serving": serving,
            "grams": _extract_grams(serving),
            "calories": _to_int(cal),
            "protein": _to_int(prot),
            "carbs": _to_int(carb),
            "fat": _to_int(fat),
        }

        if food.lower().startswith("total"):
            total = entry
        else:
            items.append(entry)

    main_item = max(items, key=lambda x: x["calories"]) if items else None

    response = {
        "items": items,
        "total": total,
        "raw": raw,
    }

    if main_item:
        response["name"] = main_item["food"]
        response["grams"] = main_item["grams"]
        response["nutrition"] = {
            "calories": main_item["calories"],
            "protein": main_item["protein"],
            "carbs": main_item["carbs"],
            "fat": main_item["fat"],
        }

    return response


@app.route("/analyze", methods=["POST"])
@app.route("/scan-image", methods=["POST"])
def analyze_image():
    try:
        data = request.get_json(force=True) or {}
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        result = analyze_image_b64(image_b64)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------
# USER AUTH
# -------------------------------------------------
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    users = load_users()
    if email in users:
        return jsonify({"error": "Email already exists"}), 400

    user_id = str(uuid.uuid4())
    users[email] = {
        "user_id": user_id,
        "password": generate_password_hash(password),
    }

    save_users(users)
    return jsonify({"status": "ok", "user_id": user_id})

@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    users = load_users()
    if email not in users:
        return jsonify({"error": "User not found"}), 400

    if not check_password_hash(users[email]["password"], password):
        return jsonify({"error": "Incorrect password"}), 400

    return jsonify({"status": "ok", "user_id": users[email]["user_id"]})


# -------------------------------------------------
# ROOT
# -------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return "WESIVIO API running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
