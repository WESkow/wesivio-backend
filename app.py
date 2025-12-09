from flask import Flask, request, jsonify
import os
import json
import re
import uuid
import base64
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq

app = Flask(__name__)

# ------------------------------------
# GROQ CLIENT
# ------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# ------------------------------------
# PING
# ------------------------------------
@app.route("/ping", methods=["GET"])
def ping():
    return {"status": "alive"}, 200


# ------------------------------------
# BARCODE DB
# ------------------------------------
BARCODE_DB = {
    "5000112637922": {
        "name": "Coke Zero (330ml)",
        "grams": 330,
        "nutrition": {
            "calories": 1,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
        },
    },
    "5000159484695": {
        "name": "Monster Ultra (sugar-free 500ml)",
        "grams": 500,
        "nutrition": {
            "calories": 10,
            "protein": 0,
            "carbs": 2,
            "fat": 0,
        },
    },
}


@app.route("/barcode", methods=["GET", "POST"])
def barcode_lookup():
    """
    GET  /barcode?code=123
    POST /barcode  { "barcode": "123" }
    """
    code = None
    if request.method == "GET":
        code = request.args.get("code")
    else:
        data = request.get_json(force=True) or {}
        code = data.get("barcode") or data.get("code")

    if not code:
        return jsonify({"error": "No barcode provided"}), 400

    item = BARCODE_DB.get(code)
    if not item:
        return jsonify({"error": "Barcode not found"}), 404

    return jsonify({
        "code": code,
        "name": item["name"],
        "grams": item.get("grams", 100),
        "item": item,
    })


# ------------------------------------
# MEAL ANALYSIS (IMAGE -> AI)
# ------------------------------------
SYSTEM_PROMPT = """
You are a professional nutrition analyst.

You receive a photo of a meal. Detect ALL food items you can
and estimate their nutrition.

Respond in EXACTLY this table-like format, one line per item:

food | serving g/ml | calories | protein | carbs | fat
...

Then last line must be:

TOTAL | total g/ml | total_cal | total_protein | total_carbs | total_fat
"""


def _to_int(text: str) -> int:
    m = re.search(r"-?\d+", text)
    return int(m.group(0)) if m else 0


def _extract_grams(serving: str) -> int:
    """
    Try to extract grams/ml from 'serving g/ml' column.
    If nothing found -> 100.
    """
    m = re.search(r"(\d+)\s*(g|gram|grams|ml|milliliters?)", serving, re.I)
    if not m:
        return 100
    return int(m.group(1))


def _analyze_image_from_b64(image_b64: str):
    completion = client.chat.completions.create(
        model="llama-3.2-vision-11b",   # 🔥 multi-item vision model
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this meal."},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}"
                    }},
                ],
            },
        ],
        temperature=0.1,
        max_completion_tokens=512,
    )

    ai_text = completion.choices[0].message.content.strip()
    lines = [l.strip() for l in ai_text.split("\n") if "|" in l]

    items = []
    total_obj = None

    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 6:
            continue

        food, serving, cal, prot, carb, fat = parts
        entry = {
            "food": food,
            "serving": serving,
            "calories": _to_int(cal),
            "protein": _to_int(prot),
            "carbs": _to_int(carb),
            "fat": _to_int(fat),
            "grams": _extract_grams(serving),
        }

        if food.lower().startswith("total"):
            total_obj = entry
        else:
            items.append(entry)

    main_item = None
    if items:
        # choose item with highest calories as "main"
        main_item = max(items, key=lambda x: x["calories"])

    response = {
        "items": items,
        "total": total_obj,
        "raw": ai_text,
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
@app.route("/scan-image", methods=["POST"])  # alias for the app
def analyze_image():
    try:
        data = request.get_json(force=True) or {}
        image_b64 = data.get("image")
        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        result = _analyze_image_from_b64(image_b64)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------
# SAVE MEAL ONLINE
# ------------------------------------
@app.route("/save_meal", methods=["POST"])
def save_meal():
    data = request.json or {}
    user_id = data.get("user_id")
    items = data.get("items")
    total = data.get("total")
    timestamp = data.get("timestamp")

    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    record = {
        "user_id": user_id,
        "items": items,
        "total": total,
        "timestamp": timestamp,
    }

    with open("meals.json", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return jsonify({"status": "ok"})


# ------------------------------------
# USER AUTH
# ------------------------------------
USERS_FILE = "users.json"


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


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
    hashed_pw = generate_password_hash(password)

    users[email] = {"user_id": user_id, "password": hashed_pw}
    save_users(users)

    return jsonify({"status": "ok", "user_id": user_id})


@app.route("/login", methods=["POST"])
def login_user():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    users = load_users()

    if email not in users:
        return jsonify({"error": "User not found"}), 400

    user_record = users[email]

    if not check_password_hash(user_record["password"], password):
        return jsonify({"error": "Incorrect password"}), 400

    return jsonify({"status": "ok", "user_id": user_record["user_id"]})


@app.route("/", methods=["GET"])
def home():
    return "WESIVIO API running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
