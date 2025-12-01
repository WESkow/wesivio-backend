from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/analyze", methods=["POST"])
def analyze():
    """
    TEST ENDPOINT:
    Ignores the image and always returns a fake potato result.
    This lets us test the full pipeline without Groq.
    """
    data = request.get_json(force=True)  # just to ensure body is JSON
    # You can print it for debugging if you like:
    # print("Received keys:", list(data.keys()))

    result = {
        "food": "test potato",
        "serving": "150 g",
        "calories": 110,
        "protein": 3,
        "carbs": 26,
        "fat": 0
    }
    return jsonify(result), 200


@app.route("/", methods=["GET"])
def root():
    return "WESIVIO Nutrition API is running (TEST MODE)."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
