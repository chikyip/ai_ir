import requests
import json
from config import API_URL, API_KEY, MODEL_NAME

def ask_qwen(prompt):
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
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
        return reply.get("choices", [{}])[0].get("message", {}).get("content", "[No response]")
    except Exception as e:
        return f"Error: {str(e)}"

def extract_cover_rationale(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        pages = json.load(f)
    for page in pages:
        text = page["text"]
        prompt = (
            "Extract the cover rationale from the following text. "
            "If not present, reply 'Not found.'\n\n"
            f"Text:\n{text}"
        )
        response = ask_qwen(prompt)
        if response.strip().lower() != "not found.":
            print(f"Page {page['page']} - Cover Rationale:\n{response}\n")
            break  # Stop at first found, or remove to search all pages

if __name__ == "__main__":
    extract_cover_rationale(r"c:\Users\chiky\irworkspace\ai_ir\output_analysis\pdf_analysis_summary.json")