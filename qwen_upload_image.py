import requests
import base64
import os  # <-- Add this import
import math
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # Remove decompression bomb protection
from io import BytesIO
from config import API_URL, API_KEY, MODEL_NAME, QWEN_PROMPT2, QWEN_PROMPT

# === CONFIG ===
# API_URL = "http://llm.chartnexus.com:8080/llm-api/qwen/chat/completions"
# API_KEY = "cy_test_1234"
# MODEL_NAME = "qwen-vl-max"

def encode_image_to_base64(image_path, max_size=(800, 800), quality=60, max_pixels=200000000):
    """Compress and resize image before encoding"""
    try:
        with Image.open(image_path) as img:
            # Check image size first
            if img.width * img.height > max_pixels:
                # Calculate required scaling
                scale = math.sqrt(max_pixels / (img.width * img.height))
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.LANCZOS)
                
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA'):
                img = img.convert('RGB')
            
            # Resize maintaining aspect ratio
            img.thumbnail(max_size, Image.LANCZOS)
            
            # Optimize compression
            buffer = BytesIO()
            ext = os.path.splitext(image_path)[1].lower()
            format = 'JPEG' if ext in ['.jpg', '.jpeg'] else 'PNG'
            
            if format == 'JPEG':
                img.save(buffer, format=format, quality=quality, optimize=True, progressive=True)
            else:
                img.save(buffer, format=format, optimize=True)
                
            buffer.seek(0)
            return base64.b64encode(buffer.read()).decode('utf-8')
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None

def main():
    image_path = input("Enter the path to your image: ")
    user_prompt = input("Enter your question about the image: ")

    image_b64 = encode_image_to_base64(image_path)
    # Compose the data URL for the image
    ext = os.path.splitext(image_path)[1].lower()
    mime = "jpeg" if ext in [".jpg", ".jpeg"] else "png"
    image_data_url = f"data:image/{mime};base64,{image_b64}"

    document_type = "annual"
    prompt = f"""
You are analyzing a {document_type} report document. 
{document_type.upper()} REPORT ANALYSIS INSTRUCTIONS:
""" + QWEN_PROMPT
            
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ]
    }

    # payload = {
    #     "model": MODEL_NAME,
    #     "messages": [
    #         {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
    #         {
    #             "role": "user",
    #             "content": [
    #                 {"type": "text", "text": user_prompt},
    #                 {"type": "image_url", "image_url": {"url": image_data_url}}
    #             ]
    #         }
    #     ],
    #     "max_tokens": 1024
    # }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        reply = response.json()
        print("Qwen:", reply.get("choices", [{}])[0].get("message", {}).get("content", "[No response]"))
    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    main()