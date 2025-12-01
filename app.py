@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        print("\n========== NEW REQUEST ==========")

        data = request.get_json()
        print("Received JSON:", data)

        if not data or "image" not in data:
            print("ERROR: Missing image")
            return jsonify({"error": "No image provided"}), 400

        # Decode base64
        try:
            image_bytes = base64.b64decode(data["image"])
            print("Image decoded OK. Bytes:", len(image_bytes))
        except Exception as e:
            print("Decode ERROR:", e)
            return jsonify({"error": "Image decode failed", "details": str(e)}), 400

        # ------------------------------
        #  GROQ REQUEST
        # ------------------------------
        print("Sending to Groq...")

        try:
            response = client.chat.completions.create(
                model="llama-3.2-90b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Identify food and estimate calories."},
                            {"type": "input_image",
                             "image_url": "data:image/jpeg;base64," + data["image"]}
                        ]
                    }
                ],
                max_tokens=300
            )

            print("Groq response OK")
            print("Groq RAW:", response)

            result = response.choices[0].message.content
            return jsonify({"result": result})

        except Exception as e:
            print("GROQ ERROR (full):")
            import traceback
            traceback.print_exc()
            return jsonify({"error": "Groq failure", "details": str(e)}), 500

    except Exception as e:
        print("SERVER ERROR (full):")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Server crashed", "details": str(e)}), 500
