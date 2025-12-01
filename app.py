@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        print("====== NEW REQUEST RECEIVED ======")

        data = request.get_json()
        print("Incoming JSON:", data)

        if not data or "image" not in data:
            print("ERROR: No image in request")
            return jsonify({"error": "No image provided"}), 400

        # Decode image
        try:
            image_bytes = base64.b64decode(data["image"])
            print("Image decoded OK. Size:", len(image_bytes))
        except Exception as e:
            print("ERROR decoding image:", e)
            return jsonify({"error": "Image decode failed"}), 400

        # ======================
        # CALL GROQ
        # ======================
        try:
            print("Sending request to Groq…")

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

            print("Groq responded OK")
            print("Groq RAW:", response)

            result = response.choices[0].message.content
            return jsonify({"result": result})

        except Exception as e:
            print("GROQ ERROR:", str(e))
            return jsonify({"error": "Groq failed", "details": str(e)}), 500

    except Exception as e:
        print("BIG SERVER ERROR:", str(e))
        return jsonify({"error": "Server crashed", "details": str(e)}), 500
