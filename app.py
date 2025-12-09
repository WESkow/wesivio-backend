from flask import Flask, request, jsonify
import os
import json
import re
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq

app = Flask(__name__)

# ------------------------------------
# LOAD GROQ API KEY
# ------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)


# ------------------------------------
# 🔥 WAKE-UP PING ENDPOINT
# ------------------------------------
@app.route("/ping", methods=["GET"])
def ping():
    return {"status": "alive"}, 200


# ------------------------------------
# BARCODE DATABASE
# wartości są NA PORCJĘ
# ------------------------------------
BARCODE_DB = {
    "5000112637922": {
        "name": "Coke Zero (330ml)",
        "serving": "330 ml",
        "grams": 330,
        "calories": 1,
        "protein": 0,
        "carbs": 0,
        "fat": 0,
    },
    "5000159484695": {
        "name": "Monster Ultra (Sugar Free 500ml)",
        "serving": "500 ml",
        "grams": 500,
        "calories": 10,
        "protein": 0,
        "carbs": 2,
        "fat": 0,
    },
}


def parse_int_from_str(text, default=100):
    if not text:
        return default
    m = re.search(r"\d+", str(text))
    if not m:
        return default
    try:
        return int(m.group(0))
    except ValueError:
        return default


@app.route("/barcode", methods=["GET", "POST"])
def barcode_lookup():
    # Obsługujemy GET ?code=... albo POST {"barcode": "..."}
    code = None
    if request.method == "GET":
        code = request.args.get("code") or request.args.get("barcode")
    else:
        data = request.get_json(force=True, silent=True) or {}
        code = data.get("barcode") or data.get("code")

    if not code:
        return jsonify({"error": "No barcode provided"}), 400

    item = BARCODE_DB.get(code)
    if not item:
        return jsonify({"error": "Barcode not found"}), 404

    grams = item.get("grams") or parse_int_from_str(item.get("serving"), 100)

    # Makra NA PORCJĘ – aplikacja przyjmie je jako "już przeliczone"
    nutrition = {
        "calories": item.get("calories", 0),
        "protein": item.get("protein", 0),
        "carbs": item.get("carbs", 0),
        "fat": item.get("fat", 0),
        # reszta mikro = 0
        "fiber": 0,
        "sugars": 0,
        "vitamin_a": 0,
        "vitamin_c": 0,
        "vitamin_k": 0,
        "vitamin_e": 0,
        "vitamin_b6": 0,
        "omega3": 0,
        "sodium": 0,
        "potassium": 0,
        "iron": 0,
        "calcium": 0,
        "magnesium": 0,
    }

    return jsonify(
        {
            "name": item["name"],
            "grams": grams,
            "nutrition": nutrition,
        }
    )


# ------------------------------------
# MEAL ANALYSIS (WIELE PRODUKTÓW)
# – zostawiamy jako "pełny raport"
# ------------------------------------
@app.route("/analyze", methods=["POST"])
def analyze_image():
    try:
        data = request.get_json(force=True)
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        system_prompt = """
        You are a professional nutrition analyst.

        Identify ALL visible food items on the plate (up to 6 different items).

        Respond in EXACTLY this line-based format (no extra text):

        food | serving g/ml | calories | protein | carbs | fat
        ...
        TOTAL | total g/ml | total_cal | total_protein | total_carbs | total_fat
        """

        completion = client.chat.completions.create(
    model="llama-3.2-vision-11b",
    messages=[
        {"role":"system", "content": system_prompt},
        {
            "role":"user",
            "content": [
                {"type": "text", "text": "Analyze this meal."},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"
                }},
            ]
        }
    ],
    temperature=0.1,
)


        ai_text = completion.choices[0].message.content.strip()
        lines = [l.strip() for l in ai_text.split("\n") if "|" in l]

        items = []
        total_obj = None

        def to_int(t):
            m = re.search(r"-?\d+", t)
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

        return jsonify({"items": items, "total": total_obj, "raw": ai_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------
# PROSTSZY ENDPOINT DLA APLIKACJI:
# /scan-image -> jeden główny produkt
# ------------------------------------
@app.route("/scan-image", methods=["POST"])
def scan_image_single():
    try:
        data = request.get_json(force=True)
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        # użyjemy tej samej logiki co /analyze
        system_prompt = """
        You are a professional nutrition analyst.

        Identify ALL visible food items on the plate (up to 6 different items).
        Then choose the SINGLE most dominant / central food item.

        Respond in EXACTLY this format, with ONLY ONE line (no TOTAL line):

        food | serving g/ml | calories | protein | carbs | fat
        """

        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this meal and pick main food."},
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
            max_completion_tokens=128,
        )

        ai_text = completion.choices[0].message.content.strip()

        # spodziewamy się jednej linii
        line = ai_text.strip()
        if "|" not in line:
            return jsonify({"error": "Bad AI format", "raw": ai_text}), 500

        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 6:
            return jsonify({"error": "Bad AI format", "raw": ai_text}), 500

        food, serving, cal, prot, carb, fat = parts

        grams = parse_int_from_str(serving, 100)

        def to_int(t):
            m = re.search(r"-?\d+", t)
            return int(m.group(0)) if m else 0

        nutrition = {
            "calories": to_int(cal),
            "protein": to_int(prot),
            "carbs": to_int(carb),
            "fat": to_int(fat),
            # mikro = 0 – aplikacja i tak ma fallback z lokalnego JSON
            "fiber": 0,
            "sugars": 0,
            "vitamin_a": 0,
            "vitamin_c": 0,
            "vitamin_k": 0,
            "vitamin_e": 0,
            "vitamin_b6": 0,
            "omega3": 0,
            "sodium": 0,
            "potassium": 0,
            "iron": 0,
            "calcium": 0,
            "magnesium": 0,
        }

        return jsonify(
            {
                "name": food,
                "grams": grams,
                "nutrition": nutrition,
                "serving_text": serving,
                "raw": ai_text,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------
# SAVE MEAL ONLINE
# ------------------------------------
@app.route("/save_meal", methods=["POST"])
def save_meal():
    data = request.json
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

    with open("meals.json", "a") as f:
        f.write(json.dumps(record) + "\n")

    return jsonify({"status": "ok"})


# ------------------------------------
# USER AUTH
# ------------------------------------
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


@app.route("/", methods=["GET"])
def home():
    return "WESIVIO API running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

