from flask import Flask, request, jsonify
import os
import json
import re
from groq import Groq

app = Flask(__name__)

# Load API key from environment
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)


# ----------------------------------------------------------
# BARCODE DATABASE (add more as you test items)
# ----------------------------------------------------------
BARCODE_DB = {
    "5000112637922": {  # Example: Coca-Cola Zero can 330ml
        "food": "Coke Zero (330ml)",
        "serving": "330 ml",
        "calories": 1,
        "protein": 0,
        "carbs": 0,
        "fat": 0
    },
    "5000159484695": {  # Example barcodes
        "food": "Monster Ultra (Sugar Free 500ml)",
        "serving": "500 ml",
        "calories": 10,
        "protein": 0,
        "carbs": 2,
        "fat": 0
    }
}


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

        # ----------------------------------------------------------
        # SYSTEM PROMPT FOR MEAL DETECTION (multi-item)
        # ----------------------------------------------------------
        system_prompt = """
        You are a professional nutrition analyst.

        If the image shows a MEAL:
        Identify all major foods (2–5 items) and respond in EXACTLY this format:

        food1 | serving g/ml | calories | protein | carbs | fat
        food2 | serving g/ml | calories | protein | carbs | fat
        food3 | serving g/ml | calories | protein | carbs | fat
        TOTAL | total g/ml | total_cal | total_protein | total_carbs | total_fat

        RULES:
        - ALWAYS estimate serving size (NEVER leave blank).
        - ALWAYS include TOTAL line.
        - NEVER return explanation, markdown, or text outside the lines.
        - Round all nutrition values to full integers.

        Serving estimation hints:
        - Protein/meat: 80–200 g
        - Carbs (rice/pasta): 100–250 g
        - Vegetables: 50–150 g
        - Sauces: 10–40 g
        - Mixed plates: estimate each component separately
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

        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 6:
                continue

            food, serving, cal, prot, carb, fat = parts

            def to_int(t):
                m = re.search(r"-?\d+", t)
                return int(m.group(0)) if m else 0

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


@app.route("/", methods=["GET"])
def home():
    return "WESIVIO Nutrition API (multi-meal + barcode) is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
