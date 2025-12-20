from flask import Flask, request, jsonify
import os, json, uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI

app = Flask(__name__)

# -------------------------------------------------
# OPENAI CLIENT
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
# BARCODE DB (fallback)
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
        return jsonify({"error": "No barcode"}), 400
    item = BARCODE_DB.get(code)
    if not item:
        return jsonify({"error": "Not found"}), 404
    return jsonify(item)


# -------------------------------------------------
# IMAGE → AI ANALYSIS (STRICT JSON)
# -------------------------------------------------
SYSTEM_PROMPT = """
You are a nutrition expert.

Analyze the food in the image.

RULES:
- Respond with JSON ONLY
- No explanations
- No markdown
- No text outside JSON

Schema:
{
  "items": [
    {"food": "", "grams": 0, "calories": 0, "protein": 0, "carbs": 0, "fat": 0}
  ],
  "total": {"grams": 0, "calories": 0, "protein": 0, "carbs": 0, "fat": 0}
}
"""

def analyze_image_openai(image_b64: str):
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": SYSTEM_PROMPT},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_b64}",
                    },
                ],
            }
        ],
        max_output_tokens=600,
    )

    raw = response.output_text.strip()

    # 🔥 HARD SAFETY
    try:
        return json.loads(raw)
    except Exception as e:
        raise ValueError(f"AI returned invalid JSON:\n{raw}") from e


@app.route("/scan-image", methods=["POST"])
@app.route("/analyze", methods=["POST"])
def scan_image():
    try:
        data = request.get_json(force=True)
        image = data.get("image")
        if not image:
            return jsonify({"error": "No image"}), 400

        result = analyze_image_openai(image)
        items = result.get("items", [])

        main = max(items, key=lambda x: x.get("calories", 0)) if items else None

        response = {
            "items": items,
            "total": result.get("total"),
            "raw": result,
        }

        if main:
            response.update({
                "name": main["food"],
                "grams": main["grams"],
                "nutrition": {
                    "calories": main["calories"],
                    "protein": main["protein"],
                    "carbs": main["carbs"],
                    "fat": main["fat"],
                },
            })

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------
# ROOT
# -------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return "WESIVIO API running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
