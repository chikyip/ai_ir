import requests
import base64
import os  # <-- Add this line
from config import API_URL, API_KEY, MODEL_NAME

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

# === CHAT LOOP ===
while True:
    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit"]:
        print("Goodbye!")
        break

    image_path = input("Enter image file path (or leave blank for text only): ").strip()
    message_content = []

    if image_path:
        try:
            image_b64 = encode_image_to_base64(image_path)
            ext = os.path.splitext(image_path)[1].lower()
            if ext == ".jpg" or ext == ".jpeg":
                mime = "jpeg"
            else:
                mime = "png"
            image_data_url = f"data:image/{mime};base64,{image_b64}"
            # Use the correct OpenAI-compatible format for image_url
            message_content.append({
                "type": "image_url",
                "image_url": {"url": image_data_url}
            })
        except Exception as e:
            print(f"Error reading image: {e}")
            continue

    message_content.append({"type": "text", "text": user_input})

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
            {"role": "user", "content": message_content}
        ],
        "max_tokens": 1024
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        reply = response.json()

        # Print the message (you may need to adjust based on your server's format)
        print("Qwen:", reply.get("choices", [{}])[0].get("message", {}).get("content", "[No response]"))
    except Exception as e:
        print("Error:", str(e))