from flask import Flask, request, jsonify
import base64
import os
import json
import re
from groq import Groq

app = Flask(__name__)

# Load API key
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        prompt = """
        You are a nutrition analysis expert.
        Look at this food photo and return STRICT JSON ONLY:

        {
          "food": "...",
          "serving": "...",
          "calories": 0,
          "protein": 0,
          "carbs": 0,
          "fat": 0
        }

        No explanations. JSON only.
        """

        response = client.chat.completions.create(
            model="llava-v1.6-7b",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Analyze this meal."},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"}
                    ]
                }
            ],
            temperature=0.2,
        )

        ai_text = response.choices[0].message.content

        # Extract JSON safely
        json_match = re.search(r"\{.*\}", ai_text, re.DOTALL)

        if not json_match:
            return jsonify({"error": "AI did not return JSON", "raw": ai_text}), 500

        clean_json = json_match.group(0)

        try:
            ai_json = json.loads(clean_json)
        except:
            return jsonify({"error": "JSON parse error", "raw": ai_text}), 500

        return jsonify(ai_json)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def root():
    return "WESIVIO Nutrition API is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
