from flask import Flask, request, jsonify
import base64
import os
import json
import re
from groq import Groq

app = Flask(__name__)

# Load API key from environment
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)


# --------------------------------------------------------
# Helper: extract any numbers if JSON fails
# --------------------------------------------------------
def extract_nutrition(text):
    """
    Extracts calories, protein, carbs, fat from plain text.
    Example fallback: "This contains 20 calories, 1g protein..."
    """
    def find(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    return {
        "food": "unknown",
        "serving": "unknown",
        "calories": find(r'(\d+)\s*cal'),
        "protein": find(r'(\d+)\s*g\s*protein'),
        "carbs": find(r'(\d+)\s*g\s*carb'),
        "fat": find(r'(\d+)\s*g\s*fat'),
        "raw_text_used": True
    }


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        # --------------------------
        # PROMPT FOR STRICT JSON
        # --------------------------
        prompt = """
        You are a nutrition AI.
        Look at the meal image and respond in STRICT JSON ONLY:
        {
          "food": "...",
          "serving": "...",
          "calories": <integer>,
          "protein": <integer>,
          "carbs": <integer>,
          "fat": <integer>
        }
        No text outside JSON. No markdown. No explanation.
        """

        response = client.chat.completions.create(
            model="llava-v1.6-34b",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Analyze this meal."},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{image_b64}"
                        }
                    ]
                }
            ],
            temperature=0.1,
        )

        ai_text = response.choices[0].message.content

        # -------------------------------
        # STEP 1: Try to extract JSON
        # -------------------------------
        json_match = re.search(r'\{.*?\}', ai_text, re.DOTALL)

        if json_match:
            clean_json = json_match.group(0)
            try:
                parsed = json.loads(clean_json)
                return jsonify(parsed)
            except Exception:
                pass  # JSON found but broken → fallback

        # --------------------------------
        # STEP 2: Fallback → extract text
        # --------------------------------
        fallback = extract_nutrition(ai_text)

        return jsonify({
            "warning": "AI JSON invalid. Fallback extracted from text.",
            "ai_raw": ai_text,
            "data": fallback
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return "WESIVIO Nutrition API is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
