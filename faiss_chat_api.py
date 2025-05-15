import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import requests
import base64
import os
import re
import subprocess  # Add this import
from flask import Flask, request, jsonify, send_from_directory
from config import API_URL, API_KEY, MODEL_NAME
from flask import Response, stream_with_context

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def ask_qwen_stream(message_content, assistant_text="You are a helpful assistant."):
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": assistant_text}]},
            {"role": "user", "content": message_content}
        ],
        "max_tokens": 1024,
        "stream": True  # Enable streaming mode
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    print("Sending payload to Qwen API (streaming mode):")
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    response = requests.post(API_URL, json=payload, headers=headers, stream=True)
    full_result = ""
    for line in response.iter_lines():
        line = line.strip() if isinstance(line, bytes) else line
        if not line:
            continue  # Skip empty lines
        # --- Fix: Remove 'data: ' prefix if present ---
        if isinstance(line, bytes):
            line = line.decode('utf-8')
        if line.startswith('data: '):
            line = line[len('data: '):]
        if line == '[DONE]':
            break
        try:
            data = json.loads(line)
            delta = data.get("choices", [{}])[0].get("delta", {}).get("content", [])
            if isinstance(delta, list):
                for item in delta:
                    text = item.get("text", "")
                    if text:
                        print(f"Streaming chunk: {text}", flush=True)
                        full_result += text
                        yield text
            else:
                if delta:
                    print(f"Streaming chunk: {delta}", flush=True)
                    full_result += delta
                    yield delta
        except Exception as e:
            print(f"Streaming parse error 12: {e} | Raw line: {line}", flush=True)
            continue
    print(f"Full Qwen result: {full_result}", flush=True)

def ask_qwen(message_content):
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

# Load index and page order once at startup
# Remove or comment out these lines:
# index = faiss.read_index(r"c:\Users\chiky\irworkspace\ai_ir\faiss_pages.index")
# with open(r"c:\Users\chiky\irworkspace\ai_ir\output_analysis\pdf_analysis_summary.json", "r", encoding="utf-8") as f:
#     pages = [page for page in json.load(f) if page["text"].strip()]

# texts = [page["text"] for page in pages]
# page_numbers = [page["page"] for page in pages]

from threading import Lock

model = SentenceTransformer("all-MiniLM-L6-v2")
app = Flask(__name__, static_folder='static')
index_cache = {}
pages_cache = {}
cache_lock = Lock()

def load_index_and_pages(client, category, year=None, report=None):
    import glob
    if year:
        index_path = fr"c:\Users\chiky\irworkspace\ai_ir\faiss_index\{client}\{category}\{year}\faiss_pages.index"
        if report:
            summary_path = fr"c:\Users\chiky\irworkspace\ai_ir\output_analysis\{client}\{category}\{year}\{report}\pdf_analysis_summary.json"
            if not os.path.exists(summary_path):
                print(f"Error: Summary file not found at {summary_path}")
                return None, None
            summary_files = [summary_path]
        else:
            summary_files = glob.glob(
                fr"c:\Users\chiky\irworkspace\ai_ir\output_analysis\{client}\{category}\{year}\*\pdf_analysis_summary.json"
            )
            if not summary_files:
                print(f"Error: No summary files found for {client}/{category}/{year}")
    else:
        index_path = fr"c:\Users\chiky\irworkspace\ai_ir\faiss_index\{client}\{category}\combined\faiss_pages.index"
        summary_files = glob.glob(
            fr"c:\Users\chiky\irworkspace\ai_ir\output_analysis\{client}\{category}\*\*\pdf_analysis_summary.json"
        )
        if not summary_files:
            print(f"Error: No summary files found for {client}/{category}")

    if not os.path.exists(index_path):
        print(f"Error: Index file not found at {index_path}")
        return None, None

    cache_key = f"{client}|{category}|{year}" if year else f"{client}|{category}|combined"
    with cache_lock:
        if cache_key in index_cache and cache_key in pages_cache:
            return index_cache[cache_key], pages_cache[cache_key]
        
        if not os.path.exists(index_path):
            return None, None
            
        if year and report:
            if not os.path.exists(summary_path):
                return None, None
            summary_files = [summary_path]
        else:
            if not summary_files:
                return None, None

        idx = faiss.read_index(index_path)
        pages = []
        for summary_path in summary_files:
            with open(summary_path, "r", encoding="utf-8") as f:
                pages.extend([page for page in json.load(f) if page["text"].strip()])
        
        for page in pages:
            page.setdefault("year", year)
            page.setdefault("filename", os.path.basename(summary_path))
        
        index_cache[cache_key] = idx
        pages_cache[cache_key] = pages
        return idx, pages

@app.route('/')
def serve_chat():
    return send_from_directory(app.static_folder, 'chat.html')

# @app.route('/chat', methods=['POST'])
# def chat():
#     data = request.json
#     question = data.get('question', '')
#     top_k = int(data.get('top_k', 3))
#     client = data.get('client')
#     category = data.get('category')
#     year = data.get('year')  # Get year parameter
#     if not question or not client or not category:
#         return jsonify({"error": "Missing question, client, or category"}), 400

#     index, pages = load_index_and_pages(client, category, year)
#     if index is None or pages is None:
#         return jsonify({"error": "Index or summary not found for the specified client/category/year"}), 404

#     texts = [page["text"] for page in pages]
#     page_numbers = [page["page"] for page in pages]

#     q_emb = model.encode([question], convert_to_numpy=True)
#     D, I = index.search(q_emb, k=10)

#     question_keywords = set(question.lower().split())
#     boosted_indices = []
#     other_indices = []
    
#     # Enhanced filtering with minimum text length and keyword density
#     for idx in I[0]:
#         if idx >= len(texts):  # Skip invalid indices
#             continue
            
#         page_text = texts[idx].lower()
#         text_length = len(page_text.split())
#         keyword_matches = sum(1 for kw in question_keywords if kw in page_text)
        
#         # Only boost if text has sufficient length and keyword density
#         if (text_length > 10 and keyword_matches >= min(2, len(question_keywords))): # Fixed missing parenthesis
#             boosted_indices.append(idx)
#         else:
#             other_indices.append(idx)
            
#     final_indices = (boosted_indices + other_indices)[:top_k]

#     grouped_text = ""
#     message_content = []
#     ranks = []
#     for rank, idx in enumerate(final_indices):
#         ranks.append({
#             "rank": rank + 1,
#             "page": page_numbers[idx],
#             "text": texts[idx][:1000]
#         })
#         grouped_text += f"\n---\nRank {rank+1}: Page {page_numbers[idx]}\n{texts[idx]}"
#         # Image handling (optional: update path if images are per client/category)
#         page_num = page_numbers[idx]
#         img_path = f"c:\\Users\\chiky\\irworkspace\\ai_ir\\images\\page_{page_num}.png"
#         if os.path.exists(img_path):
#             try:
#                 image_b64 = encode_image_to_base64(img_path)
#                 ext = os.path.splitext(img_path)[1].lower()
#                 mime = "jpeg" if ext in [".jpg", ".jpeg"] else "png"
#                 image_data_url = f"data:image/{mime};base64,{image_b64}"
#                 message_content.append({
#                     "type": "image_url",
#                     "image_url": {"url": image_data_url}
#                 })
#             except Exception as e:
#                 pass

#     message_content.insert(0, {
#         "type": "text",
#         "text": f"Question: {question}\n\nGrouped Results:\n{grouped_text}"
#     })

#     qwen_response = ask_qwen(message_content)
#     return jsonify({
#         "question": question,
#         "ranks": ranks,
#         "qwen_response": qwen_response
#     })

@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    data = request.json
    question = data.get('question', '')
    top_k = int(data.get('top_k', 3))
    max_images = int(data.get('max_images', 0))
    client = data.get('client')
    category = data.get('category')
    year = data.get('year')
    assistant_text = data.get('assistantText', 'You are a helpful assistant.')  # Default to original text if not provided

    if not question or not client or not category:
        return jsonify({"error": "Missing question, client, or category"}), 400

    index, pages = load_index_and_pages(client, category, year)
    if index is None or pages is None:
        return jsonify({"error": "Index or summary not found for the specified client/category/year"}), 404

    texts = [page["text"] for page in pages]
    page_numbers = [page["page"] for page in pages]

    q_emb = model.encode([question], convert_to_numpy=True)
    D, I = index.search(q_emb, k=100)

    question_keywords = set(question.lower().split())
    boosted_indices = []
    other_indices = []
    
    # Use the same enhanced filtering as in /chat endpoint
    for idx in I[0]:
        if idx >= len(texts):
            continue
        page_text = texts[idx].lower()
        text_length = len(page_text.split())
        keyword_matches = sum(1 for kw in question_keywords if kw in page_text)
        
        if (text_length > 10 and keyword_matches >= min(2, len(question_keywords))):
            boosted_indices.append(idx)
        else:
            other_indices.append(idx)
            
    final_indices = (boosted_indices + other_indices)[:top_k]

    def generate():
        # First send search results as a special message
        search_results = []
        for rank, idx in enumerate(final_indices):
            page_info = pages[idx]
            search_results.append({
                "rank": rank + 1,
                "page": page_numbers[idx],
                "text": texts[idx][:1000],
                "client": client,
                "category": category,
                "year": page_info.get("year", year),
                "filename": page_info.get("filename", os.path.basename(page_info.get("pdf_path", "N/A")))
            })
        yield f"SEARCH_RESULTS:{json.dumps(search_results)}\n\n"
        
        # Then stream the Qwen response
        grouped_text = ""
        message_content = []
        image_count = 0  # Initialize image count
        for rank, idx in enumerate(final_indices):
            page_info = pages[idx]
            grouped_text += f"\n---\nRank {rank+1}: Page {page_numbers[idx]}\n{texts[idx]}"
            
            # Get images from page_info if available
            if "images" in page_info and isinstance(page_info["images"], list):
                for img_path in page_info["images"]:
                    if image_count >= max_images:  # Check if image count has reached top_k
                        break
                    if os.path.exists(img_path):
                        try:
                            image_b64 = encode_image_to_base64(img_path)
                            ext = os.path.splitext(img_path)[1].lower()
                            mime = "jpeg" if ext in [".jpg", ".jpeg"] else "png"
                            image_data_url = f"data:image/{mime};base64,{image_b64}"
                            message_content.append({
                                "type": "image_url",
                                "image_url": {"url": image_data_url}
                            })
                            image_count += 1  # Increment image count
                        except Exception as e:
                            print(f"Image processing error: {e}")

        message_content.insert(0, {
            "type": "text",
            "text": f"Question: {question}\n\nGrouped Results:\n{grouped_text}"
        })

        for chunk in ask_qwen_stream(message_content, assistant_text):
            yield chunk

    return Response(stream_with_context(generate()), mimetype='text/plain')

import sys

@app.route('/api/directory/clients')
def get_clients():
    base_path = r"c:\Users\chiky\irworkspace\ai_ir\faiss_index"
    clients = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    return jsonify(clients)

@app.route('/api/directory/categories')
def get_categories():
    client = request.args.get('client')
    base_path = fr"c:\Users\chiky\irworkspace\ai_ir\faiss_index\{client}"
    categories = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    return jsonify(categories)

@app.route('/api/directory/years')
def get_years():
    client = request.args.get('client')
    category = request.args.get('category')
    base_path = fr"c:\Users\chiky\irworkspace\ai_ir\output_analysis\{client}\{category}"
    
    # Extract years from directory names or filenames
    years = set()
    for root, dirs, files in os.walk(base_path):
        for name in files:
            if name == 'pdf_analysis_summary.json':
                # Extract year from path or filename
                year_match = re.search(r'(\d{4})', root)
                if year_match:
                    years.add(year_match.group(1))
    return jsonify(sorted(list(years), reverse=True))

from werkzeug.utils import secure_filename
import shutil

@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    client = request.form.get('client')
    category = request.form.get('category')
    year = request.form.get('year')
    
    if not client or not category or not year:
        return jsonify({"error": "Missing client, category or year"}), 400

    def generate():
        # Stage 1: Saving file
        yield "STAGE:SAVING_FILE\n"
        upload_dir = fr"c:\Users\chiky\irworkspace\ai_ir\files\{client}\{category}\{year}"
        try:
            os.makedirs(upload_dir, exist_ok=True)
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            yield "STATUS:FILE_SAVED\n"
        except Exception as e:
            yield f"ERROR:Failed to save file: {str(e)}\n"
            return

        # Stage 2: Processing PDF
        yield "STAGE:PROCESSING_PDF\n"
        pdf_name = os.path.splitext(filename)[0]
        output_folder = fr"c:\Users\chiky\irworkspace\ai_ir\output_analysis\{client}\{category}\{year}\{pdf_name}"
        try:
            process = subprocess.Popen([
                sys.executable,
                r"c:\Users\chiky\irworkspace\ai_ir\export_pdf_full_analysis.py",
                filepath
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    yield f"PROCESS:{output.strip()}\n"
            
            if process.returncode != 0:
                yield "ERROR:PDF processing failed\n"
                return
            yield "STATUS:PDF_PROCESSED\n"
        except Exception as e:
            yield f"ERROR:PDF processing error: {str(e)}\n"
            return

        # Stage 3: Rebuilding index
        yield "STAGE:REBUILDING_INDEX\n"
        try:
            process = subprocess.Popen([
                sys.executable,
                r"c:\Users\chiky\irworkspace\ai_ir\build_faiss_index.py",
                client,
                category,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    yield f"INDEX:{output.strip()}\n"
            
            if process.returncode != 0:
                yield "ERROR:Index rebuild failed\n"
                return
            yield "STATUS:INDEX_REBUILT\n"
        except Exception as e:
            yield f"ERROR:Index rebuild error: {str(e)}\n"
            return

        yield "COMPLETE:Upload and processing successful\n"

    return Response(stream_with_context(generate()), mimetype='text/plain')

if __name__ == '__main__':
    # Default values
    port = 5000
    debug = False

    # Parse command-line arguments
    args = sys.argv[1:]
    if '--dev' in args:
        debug = True
    if '--port' in args:
        try:
            port_index = args.index('--port') + 1
            port = int(args[port_index])
        except (IndexError, ValueError):
            print("Invalid port specified. Using default port 5000.")

    app.run(port=port, debug=debug)