from flask import Flask, request, jsonify
import os
import json
import re
from groq import Groq

app = Flask(__name__)

# Groq API key from Render environment
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(force=True)
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        # Prompt: ask for ONE pipe-separated line, no extra text
        system_prompt = """
        You are a professional nutrition analyst.

        Look at the food or drink in the image and respond with EXACTLY ONE LINE
        in this format (no extra words, no markdown):

        food/drink name | serving amount and unit | calories (integer) | protein g (integer) | carbs g (integer) | fat g (integer)

        Examples:
        potato | 150 g | 110 | 3 | 26 | 0
        sugar-free coke | 330 ml | 1 | 0 | 0 | 0
        coffee with 3 tsp double cream | 250 ml | 72 | 1 | 1 | 7

        Rules:
        - Do NOT write any explanation.
        - Do NOT add text before or after the line.
        - ONLY return the line with fields separated by "|".
        """

        # Build Groq request – this matches Groq's current vision docs
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this item and follow the format strictly.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                            },
                        },
                    ],
                },
            ],
            temperature=0.2,
            max_completion_tokens=128,
        )

        # Groq returns text content
        ai_text = completion.choices[0].message.content.strip()

        # ------------------------------------------------------------------
        # Parse the line: "food | serving | calories | protein | carbs | fat"
        # ------------------------------------------------------------------
        parts = [p.strip() for p in ai_text.split("|")]

        if len(parts) != 6:
            # If model didn't follow the format, return raw for debugging
            return jsonify({
                "error": "Unexpected AI format",
                "raw": ai_text,
            }), 500

        food, serving, cal_text, prot_text, carb_text, fat_text = parts

        def first_int(text, default=0):
            m = re.search(r"-?\d+", text)
            return int(m.group(0)) if m else default

        result = {
            "food": food,
            "serving": serving,
            "calories": first_int(cal_text),
            "protein": first_int(prot_text),
            "carbs": first_int(carb_text),
            "fat": first_int(fat_text),
            "raw": ai_text,
        }

        return jsonify(result)

    except Exception as e:
        # Return error text so Flutter can show it instead of just "500"
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def root():
    return "WESIVIO Nutrition API is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
