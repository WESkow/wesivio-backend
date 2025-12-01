import os
import base64
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

@app.route("/", methods=["GET"])
def root():
    return "WESIVIO Nutrition API is running."

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "No image provided"}), 400

        image_bytes = base64.b64decode(data["image"])

        response = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Identify the food and estimate its calories."},
                        {"type": "input_image", "image_url": "data:image/jpeg;base64," + data["image"]}
                    ]
                }
            ],
            max_tokens=300
        )

        result = response.choices[0].message.content
        return jsonify({"result": result})

    except Exception as e:
        print("SERVER ERROR:", str(e))
        return jsonify({"error": "Server failed", "details": str(e)}), 500


# ========= RENDER PORT FIX =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port)
