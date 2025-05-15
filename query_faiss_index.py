import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import requests
import base64
import os
from config import API_URL, API_KEY, MODEL_NAME

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def ask_qwen(message_content):  # Changed parameter to accept message content list
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
        return reply.get("choices", [{}])[0].get("message", {}).get("content", "[No response]")
    except Exception as e:
        return f"Error: {str(e)}"

# Load index and page order
index = faiss.read_index(r"c:\Users\chiky\irworkspace\ai_ir\faiss_pages.index")
with open(r"c:\Users\chiky\irworkspace\ai_ir\output_analysis\pdf_analysis_summary.json", "r", encoding="utf-8") as f:
    # When loading pages:
    pages = [page for page in json.load(f) if page["text"].strip()]

texts = [page["text"] for page in pages]
page_numbers = [page["page"] for page in pages]

model = SentenceTransformer("all-MiniLM-L6-v2")

last_question = None
last_grouped_text = None

while True:
    question = input("Enter your question (or type 'exit' to quit): ")
    if question.lower() in ["exit", "quit"]:
        break
    q_emb = model.encode([question], convert_to_numpy=True)
    
    # First get more results to have better candidates
    D, I = index.search(q_emb, k=10)
    
    # Boost pages containing question keywords
    question_keywords = set(question.lower().split())
    boosted_indices = []
    other_indices = []
    
    for idx in I[0]:
        page_text = texts[idx].lower()
        if any(keyword in page_text for keyword in question_keywords):
            boosted_indices.append(idx)
        else:
            other_indices.append(idx)
    
    # Combine boosted and regular results
    I = np.array([boosted_indices + other_indices])[:3]  # Keep top 3
    grouped_text = ""
    message_content = []  # Initialize message_content here
    
    for rank, idx in enumerate(I[0]):
        print(f"\nRank {rank+1}: Page {page_numbers[idx]}")
        print(texts[idx][:1000])
        grouped_text += f"\n---\nRank {rank+1}: Page {page_numbers[idx]}\n{texts[idx]}"
        
        # Image handling
        page_num = page_numbers[idx]
        img_path = f"c:\\Users\\chiky\\irworkspace\\ai_ir\\images\\page_{page_num}.png"
        
        if os.path.exists(img_path):
            try:
                image_b64 = encode_image_to_base64(img_path)
                ext = os.path.splitext(img_path)[1].lower()
                mime = "jpeg" if ext in [".jpg", ".jpeg"] else "png"
                image_data_url = f"data:image/{mime};base64,{image_b64}"
                
                # Add image to message_content
                message_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_data_url}
                })
                
            except Exception as e:
                print(f"Skipping image {img_path}: {str(e)}")

    # Add text content to message_content
    message_content.insert(0, {
        "type": "text",
        "text": f"Question: {question}\n\nGrouped Results:\n{grouped_text}"
    })
    
    # Send to Qwen
    qwen_response = ask_qwen(message_content)
    print(f"\nQwen response for grouped results:\n{qwen_response}\n")
    # Store for next round
    last_question = question
    last_grouped_text = grouped_text