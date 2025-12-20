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
# OPENAI CLIENT (VISION)
# -------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------
@app.route("/ping", methods=["GET"])
def ping():
    return {"status": "alive"}, 200

# -------------------------------------------------
# BARCODE DATABASE
# -------------------------------------------------
BARCODE_DB = {
    "5000112637922": {
        "name": "Coke Zero (330ml)",
        "grams": 330,
        "nutrition": {"calories": 1, "protein": 0, "carbs": 0, "fat": 0},
    }
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

    return jsonify(item)

# -------------------------------------------------
# IMAGE → AI
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

def _analyze_image(image_b64):
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

    return json.loads(response.choices[0].message.content)

@app.route("/scan-image", methods=["POST"])
def analyze_image():
    try:
        data = request.get_json(force=True)
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        result = _analyze_image(image_b64)

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
# ROOT
# -------------------------------------------------
@app.route("/")
def home():
    return "WESIVIO API running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
