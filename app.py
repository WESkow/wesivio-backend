from flask import Flask, request, jsonify
from groq import Groq
import base64
import json
import os

app = Flask(__name__)
groq_api_key = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=groq_api_key)

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.json
        img_b64 = data.get("image")

        if not img_b64:
            return jsonify({"error": "image missing"}), 400

        prompt = """
You are a nutrition AI. Analyze the food in the image and respond ONLY with this exact JSON structure:

{
  "food": "name",
  "serving_grams": 123,
  "calories": 123,
  "protein_g": 0,
  "carbs_g": 0,
  "fat_g": 0
}

Rules:
- No explanations
- No comments
- No text outside JSON
- No markdown
- Always return valid JSON
"""

        image_bytes = base64.b64decode(img_b64)

        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Analyze this meal."},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{img_b64}"
                        }
                    ]
                }
            ],
            temperature=0.2
        )

        ai_text = response.choices[0].message.content.strip()

        try:
            ai_json = json.loads(ai_text)
        except json.JSONDecodeError:
            return jsonify({
                "error": "Invalid JSON from AI",
                "raw": ai_text
            }), 500

        return jsonify(ai_json)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return "WESIVIO Nutrition API is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
