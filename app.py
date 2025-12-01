import base64
import json
import os
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        if not data or "image" not in data:
            return jsonify({"error": "No image received"}), 400

        # Decode Base64
        image_bytes = base64.b64decode(data["image"])

        # Query Groq
        response = client.chat.completions.create(
            model="llava-v1.5-7b",
            messages=[
                {"role": "user", "content": [
                    {"type": "input_text", "text": "Identify the food and give approximate nutrition."},
                    {
                        "type": "input_image",
                        "image": image_bytes
                    }
                ]}
            ],
            max_tokens=200,
            temperature=0.2
        )

        # THE FIX — read plain text instead of JSON
        ai_text = response.choices[0].message["content"]

        # return plain text to the app
        return jsonify({"result": ai_text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def root():
    return "WESIVIO Nutrition API is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
