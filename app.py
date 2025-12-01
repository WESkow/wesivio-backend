from flask import Flask, request, jsonify
from groq import Groq
import base64
import os

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

@app.route("/", methods=["GET"])
def home():
    return "WESIVIO Nutrition API running."

@app.route("/analyze", methods=["POST"])
def analyze_food():
    try:
        data = request.json

        if not data or "image" not in data:
            return jsonify({"error": "No image provided"}), 200

        image_b64 = data["image"]

        # Send to Groq Vision Model
        response = client.chat.completions.create(
            model="llava-v1.5-7b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Identify the food and return JSON with: name, calories, protein_g, carbs_g, fat_g."},
                        {
                            "type": "image_url",
                            "image_url": { "url": f"data:image/jpeg;base64,{image_b64}" }
                        }
                    ]
                }
            ],
            temperature=0
        )

        ai_text = response.choices[0].message.content

        # Very safe fallback parsing
        try:
            # If the model outputs JSON block ```json ... ```
            if "```" in ai_text:
                ai_text = ai_text.split("```")[1]
                ai_text = ai_text.replace("json", "").strip()

            result = eval(ai_text) if ai_text.startswith("{") else {"raw": ai_text}

        except Exception:
            # Never return 500 → always return safe JSON
            result = {"raw": ai_text}

        return jsonify(result), 200

    except Exception as e:
        # Last-chance fallback — still return JSON, not 500
        return jsonify({"error": str(e)}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
