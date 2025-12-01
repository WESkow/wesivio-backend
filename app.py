from flask import Flask, request, jsonify
import base64
import httpx
import os

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@app.route("/", methods=["GET"])
def home():
    return "API is running!"

@app.route("/analyze", methods=["POST"])
def analyze_image():
    try:
        data = request.get_json()
        if not data or "image" not in data:
            return jsonify({"error": "No image provided"}), 400

        base64_image = data["image"]

        # Send to Groq Vision API
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        body = {
            "model": "llama-3.2-11b-vision-preview",
            "input": [
                {
                    "image": base64_image
                },
                {
                    "text": "What food is this? Be accurate and short."
                }
            ]
        }

        response = httpx.post(
            "https://api.groq.com/openai/v1/responses",
            headers=headers,
            json=body,
            timeout=60
        )

        if response.status_code != 200:
            return jsonify({
                "error": "Groq API error",
                "details": response.text
            }), 500

        result = response.json()
        ai_text = result["output_text"] if "output_text" in result else "No result"

        return jsonify({"result": ai_text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
