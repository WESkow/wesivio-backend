from flask import Flask, request, jsonify
import base64
import os
import json
import re
from groq import Groq

app = Flask(__name__)

# Load API key from Render environment variable
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        # Prompt for nutrition analysis
        prompt = """
        You are a professional nutrition analyst.
        Look at the meal image and respond with STRICT JSON ONLY:
        {
          "food": "...",
          "serving": "amount + unit (e.g. 150 g, 1 slice, 1 bowl)",
          "calories": <integer>,
          "protein": <integer>,
          "carbs": <integer>,
          "fat": <integer>
        }
        Do NOT add explanations, notes, markdown, or text outside JSON.
        """

        response = client.chat.completions.create(
            model="llava-v1.6-34b",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Analyze this meal and return ONLY JSON."
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{image_b64}"
                        }
                    ]
                }
            ],
            temperature=0.2,
        )

        # AI response text
        ai_text = response.choices[0].message.content

        # -------------------------------------------------------------------
        # SAFE JSON EXTRACTION (fixes invalid JSON issues)
        # -------------------------------------------------------------------

        # Find JSON { ... } inside text
        json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)

        if not json_match:
            return jsonify({
                "error": "AI returned no JSON",
                "raw": ai_text
            }), 500

        clean_json = json_match.group(0)

        try:
            ai_json = json.loads(clean_json)
        except Exception:
            return jsonify({
                "error": "AI JSON parse error",
                "raw": ai_text
            }), 500

        return jsonify(ai_json)

        # -------------------------------------------------------------------

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def root():
    return "WESIVIO Nutrition API is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
