from flask import Flask, request, jsonify, send_from_directory, Response
import os
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF for PDF processing
import time  # For simulating processing time
import json
import requests
from typing import Dict, List, Optional
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_URL, API_KEY, MODEL_NAME, QWEN_PROMPT  # Changed from relative to absolute import
import base64
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
from threading import Semaphore
try:
    import msvcrt  # Windows file locking
except ImportError:
    try:
        import fcntl  # Unix file locking
    except ImportError:
        # Fallback for systems without either module
        fcntl = None
        print("Warning: No file locking available on this system")
import functools
from datetime import datetime
import re
from pdf_processor import process_pdf_with_qwen
from image_analyzer import analyze_image_with_qwen
from extract_handler import ExtractHandler  # Import the ExtractHandler class
from upload_handler import UploadHandler  # Import the UploadHandler class

# Initialize Flask app with static folder configuration
app = Flask(__name__, 
            static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'),
            static_url_path='/static')

# Set up upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Define the root directory for frontend files
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))

@app.route('/')
def serve_main_frontend():
    # Serves index.html from the static directory
    return send_from_directory(STATIC_DIR, "index.html")

@app.route('/upload-and-process-pdfs', methods=['POST'])
def upload_files():
    if 'pdf_files' not in request.files:
        return jsonify({"message": "No PDF files part in the request"}), 400
    
    files = request.files.getlist('pdf_files')
    client = request.form.get('client')
    report_type = request.form.get('report_type')
    year = request.form.get('year')

    # Validate that client, report_type, and year are provided
    if not all([client, report_type, year]):
        missing_fields = []
        if not client: missing_fields.append("Client")
        if not report_type: missing_fields.append("Report Type")
        if not year: missing_fields.append("Year")
        return jsonify({"message": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    if not files or (files[0] and files[0].filename == ''):
        return jsonify({"message": "No selected files"}), 400

    saved_files_info = []
    errors = []

    # Save all files first
    for file in files:
        if file and file.filename:
            original_filename = file.filename
            filename = secure_filename(original_filename)

            if not filename:
                errors.append(f"Invalid or empty filename after sanitization for '{original_filename}'.")
                continue

            target_directory = os.path.join(app.config['UPLOAD_FOLDER'], client, report_type, year)
            
            try:
                os.makedirs(target_directory, exist_ok=True)
                save_path = os.path.join(target_directory, filename)
                
                file.save(save_path)
                saved_files_info.append({
                    "filename": filename,
                    "original_filename": original_filename,
                    "path": save_path,
                    "client": client,
                    "report_type": report_type,
                    "year": year
                })
                print(f"Saved file: {save_path}")
            except Exception as e:
                error_message = f"Error saving file '{original_filename}': {str(e)}"
                print(error_message)
                errors.append(error_message)
        elif file and not file.filename:
            errors.append("A file was provided without a filename.")

    if errors and not saved_files_info:
        return jsonify({"message": "All file uploads failed.", "errors": errors}), 500
    
    if not saved_files_info:
        return jsonify({"message": "No files were processed."}), 400

    return jsonify({
        "message": f"Successfully uploaded {len(saved_files_info)} files",
        "uploaded_files": saved_files_info,
        "errors": errors
    })

# Add this new route to serve extracted images
@app.route('/extracts/<path:filename>')
def serve_extract(filename):
    extracts_dir = os.path.join(os.path.dirname(__file__), 'extracts')
    return send_from_directory(extracts_dir, filename)

@app.route('/jsons/<path:filename>')
def serve_json(filename):
    jsons_dir = os.path.join(os.path.dirname(__file__), 'jsons')
    return send_from_directory(jsons_dir, filename)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    return send_from_directory(uploads_dir, filename)

# Add rate limiting semaphore (adjust max_workers as needed)
MAX_CONCURRENT_REQUESTS = 3  # Safe number of concurrent API calls
request_semaphore = Semaphore(MAX_CONCURRENT_REQUESTS)

# Setup extracts directory and ensure it exists
extracts_dir = os.path.join(os.path.dirname(__file__), 'extracts')
os.makedirs(extracts_dir, exist_ok=True)
print(f"Watching extracts directory: {extracts_dir}")

# Setup extracts observer with proper configuration
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    extracts_observer = Observer()
    # After initializing the ExtractHandler
    extract_handler = ExtractHandler(request_semaphore)
    extracts_observer.schedule(
        extract_handler,  # Changed from extracts_handler to extract_handler
        path=extracts_dir,
        recursive=True
    )
    print(f"Starting extracts observer with recursive=True")
    extracts_observer.start()

# Setup upload observer
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    upload_observer = Observer()
    upload_handler = UploadHandler(UPLOAD_FOLDER)
    upload_observer.schedule(upload_handler, path=UPLOAD_FOLDER, recursive=True)
    upload_observer.start()

# Add cache dictionary
RESULTS_CACHE = {}
CACHE_EXPIRY_SECONDS = 300  # 5 minutes cache duration

def cache_key(client: str, report_type: str, years: List[str], categories: List[str]) -> str:
    """Generate a unique cache key for the query parameters"""
    return f"{client}_{report_type}_{'_'.join(sorted(years))}_{'_'.join(sorted(categories))}"

@app.route('/query-results', methods=['GET', 'POST'])
def query_results():
    """Query processed results by client, report type, years and categories"""
    try:
        # Handle both GET and POST requests
        if request.method == 'POST':
            data = request.get_json()
            client = data.get('client')
            report_type = data.get('report_type')
            years = data.get('years', [])  # Expecting array of years
            categories = data.get('categories', [])  # Expecting array of categories
        else:  # GET
            client = request.args.get('client')
            report_type = request.args.get('report_type')
            years = request.args.getlist('year')  # Multiple years can be specified
            categories = request.args.getlist('category')  # Multiple categories can be specified
        
        # Validate required parameters
        if not all([client, report_type]):
            return jsonify({"error": "Missing required parameters (client, report_type)"}), 400
        if not years:
            return jsonify({"error": "At least one year must be specified"}), 400
            
        # Validate year format
        invalid_years = [y for y in years if not y.isdigit()]
        if invalid_years:
            return jsonify({"error": f"Invalid year format: {', '.join(invalid_years)}"}), 400
        
        # Check cache first
        key = cache_key(client, report_type, years, categories)
        cached = RESULTS_CACHE.get(key)
        
        if cached and (datetime.now() - cached['timestamp']).total_seconds() < CACHE_EXPIRY_SECONDS:
            print(f"Returning cached results for key: {key}")
            # return jsonify(cached['data'])
        
        # Build base directory path
        base_dir = os.path.join(os.path.dirname(__file__), 'jsons')
        results = []
        
        # Process each requested year
        for year in years:
            year_dir = os.path.join(base_dir, client, report_type, year)
            
            if not os.path.exists(year_dir):
                continue  # Skip if directory doesn't exist
                
            # Walk through all JSON files in the directory
            for root, _, files in os.walk(year_dir):
                for file in files:
                    if file.endswith('.json'):
                        json_path = os.path.join(root, file)
                        
                        try:
                            # Extract filename and page number from path
                            filename = os.path.basename(root)  # PDF filename without extension
                            page_match = re.search(r'_page_(\d+)', file)
                            page_num = int(page_match.group(1)) if page_match else 1
                            
                            # Check file modification time
                            file_mtime = os.path.getmtime(json_path)
                            
                            # If we have a cached version and file hasn't changed, use cached data
                            if cached and json_path in cached['file_times']:
                                if cached['file_times'][json_path] >= file_mtime:
                                    results.append(cached['file_data'][json_path])
                                    continue
                            
                            # Otherwise read from disk
                            with open(json_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                
                                # Initialize common variables
                                content_json = None
                                doc_category_names = []
                                
                                # Parse content_json if available
                                if 'choices' in data:
                                    try:
                                        content = data['choices'][0]['message']['content']
                                        if content.startswith('```json') and content.endswith('```'):
                                            content = content[7:-3].strip()
                                        content_json = json.loads(content) if isinstance(content, str) else content
                                    except Exception as e:
                                        print(f"Error parsing content_json: {str(e)}")
                                
                                # Extract categories from both direct format and choices format
                                if 'categories' in data:
                                    doc_category_names.extend([c['name'].lower() for c in data.get('categories', [])])
                                elif content_json and 'categories' in content_json:
                                    doc_category_names.extend([c['name'].lower() for c in content_json.get('categories', [])])
                                
                                # Create result item if no categories specified or if matches any category
                                if not categories or any(cat.lower() in doc_category_names for cat in categories):
                                    result_item = {
                                        'path': json_path,
                                        'client': client,
                                        'report_type': report_type,
                                        'year': year,
                                        'filename': filename,
                                        'page': page_num,
                                        'data': data,
                                        'content_json': content_json
                                    }
                                    results.append(result_item)
                                else:
                                    # Handle both direct format and choices format
                                    doc_category_names = []
                                    
                                    # Check if data is in direct format (your example)
                                    if 'categories' in data:
                                        doc_category_names.extend([c['name'].lower() for c in data.get('categories', [])])
                                    # Check if data contains choices array
                                    elif 'choices' in data:
                                        for choice in data.get('choices', []):
                                            content = choice.get('message', {}).get('content', '{}')

                                            if content.startswith('```json') and content.endswith('```'):
                                                content = content[7:-3].strip()  # Remove ```json and ```
                   
                                            try:
                                                if isinstance(content, str):
                                                    try:
                                                        content_json = json.loads(content)
                                                    except json.JSONDecodeError:
                                                        if isinstance(content, dict):
                                                            content_json = content
                                                        else:
                                                            raise
                                                    
                                                    # Check if content_json has categories
                                                    if 'categories' in content_json:
                                                        try:
                                                            categories_list = content_json.get('categories', [])
                                                            if not isinstance(categories_list, list):
                                                                print(f"Warning: Expected list but got {type(categories_list)} for categories in {json_path}")
                                                                continue
                                                            
                                                            # Extract and validate category names
                                                            valid_categories = []
                                                            for category in categories_list:
                                                                if not isinstance(category, dict):
                                                                    print(f"Warning: Invalid category format in {json_path}")
                                                                    continue
                                                                
                                                                category_name = category.get('name')
                                                                if not category_name or not isinstance(category_name, str):
                                                                    print(f"Warning: Missing or invalid category name in {json_path}")
                                                                    continue
                                                                
                                                                normalized_name = category_name.strip().lower()
                                                                if normalized_name:
                                                                    valid_categories.append(normalized_name)
                                                            
                                                            if valid_categories:
                                                                doc_category_names.extend(valid_categories)
                                                                print(f"Added {len(valid_categories)} valid categories from {json_path}")
                                                            else:
                                                                print(f"No valid categories found in {json_path}")
                                                        
                                                        except Exception as e:
                                                            print(f"Error processing categories in {json_path}: {str(e)}")
                                            except json.JSONDecodeError as e:
                                                print(f"Failed to decode JSON content: {str(e)}")
                                                print(f"Problematic content: {content}")
                                                continue
                                    
                                    if any(cat.lower() in doc_category_names for cat in categories):
                                        result_item = {
                                            'path': json_path,
                                            'client': client,
                                            'report_type': report_type,
                                            'year': year,
                                            'data': data,
                                            'content_json': content_json  # Add the parsed content_json
                                        }
                                        results.append(result_item)
                                
                        except Exception as e:
                            print(f"Error reading {json_path}: {str(e)}")
                            continue
        
        response_data = {
            'count': len(results),
            'results': results
        }
        
        # Update cache
        file_times = {}
        file_data = {}
        for result in results:
            json_path = result['path']
            file_times[json_path] = os.path.getmtime(json_path)
            file_data[json_path] = result
            
        RESULTS_CACHE[key] = {
            'timestamp': datetime.now(),
            'data': response_data,
            'file_times': file_times,
            'file_data': file_data
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({"error": f"Query failed: {str(e)}"}), 500

@app.route('/summary', methods=['GET'])
def get_processed_summary():
    """Generate summary of all processed files showing total pages and analyzed images"""
    try:
        jsons_dir = os.path.join(os.path.dirname(__file__), 'jsons')
        extracts_dir = os.path.join(os.path.dirname(__file__), 'extracts')
        
        if not os.path.exists(jsons_dir):
            return jsonify({"error": "No processed files found"}), 404
            
        summary = {
            "total_clients": 0,
            "clients": []
        }
        
        # Walk through all client directories
        for client in os.listdir(jsons_dir):
            client_path = os.path.join(jsons_dir, client)
            if not os.path.isdir(client_path):
                continue
                
            client_data = {
                "client_name": client,
                "report_types": {}
            }
            
            # Process each report type for this client
            for report_type in os.listdir(client_path):
                report_path = os.path.join(client_path, report_type)
                if not os.path.isdir(report_path):
                    continue
                    
                # Initialize report type data
                client_data["report_types"][report_type] = {
                    "years": {}
                }
                
                # Process each year for this report type
                for year in os.listdir(report_path):
                    year_path = os.path.join(report_path, year)
                    if not os.path.isdir(year_path) or not year.isdigit():
                        continue
                        
                    print(f"Processing year: {year} for {client}/{report_type}")  # Debug print
                    
                    # Initialize counters
                    file_data = {}
                    
                    # Get PDF count from extracts directory
                    extracts_year_path = os.path.join(extracts_dir, client, report_type, year)
                    print(f"Checking extracts path: {extracts_year_path}")  # Debug print
                    
                    if os.path.exists(extracts_year_path):
                        print(f"Found extracts directory for {year}")  # Debug print
                        # Walk through all PDF directories
                        for pdf_dir in os.listdir(extracts_year_path):
                            pdf_dir_path = os.path.join(extracts_year_path, pdf_dir)
                            print(f"Checking PDF directory: {pdf_dir_path}")  # Debug print
                            
                            if os.path.isdir(pdf_dir_path):
                                print(f"Processing PDF directory: {pdf_dir_path}")  # Debug print
                                # Count images for this PDF
                                total_pages = sum(1 for root, dirs, files in os.walk(pdf_dir_path) 
                                         for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png')))
                                print(f"Found {total_pages} pages in {pdf_dir_path}")  # Debug print
                                
                                # Count analyzed images from jsons
                                json_dir_path = os.path.join(year_path, pdf_dir)
                                print(f"Checking JSON directory: {json_dir_path}")  # Debug print
                                
                                analyzed_images = sum(1 for root, dirs, files in os.walk(json_dir_path) 
                                          for f in files if f.endswith('.json')) if os.path.exists(json_dir_path) else 0
                                print(f"Found {analyzed_images} analyzed images in {json_dir_path}")  # Debug print
                                
                                # Remove any conditions and always include the data
                                file_data[pdf_dir] = {
                                    "analyzed_images": analyzed_images,
                                    "total_pages": total_pages
                                }
                    else:
                        print(f"Warning: Extracts directory not found for {year}")  # New debug print
                        # Count analyzed images from jsons
                        json_dir_path = os.path.join(year_path, pdf_dir)
                        print(f"Checking JSON directory: {json_dir_path}")  # Debug print
                        
                        analyzed_images = sum(1 for root, dirs, files in os.walk(json_dir_path) 
                                    for f in files if f.endswith('.json')) if os.path.exists(json_dir_path) else 0
                        print(f"Found {analyzed_images} analyzed images in {json_dir_path}")  # Debug print
                        
                        # Remove any conditions and always include the data
                        file_data[pdf_dir] = {
                            "analyzed_images": analyzed_images,
                            "total_pages": total_pages
                        }
                    
                    if file_data:  # Only add if we found data
                        client_data["report_types"][report_type]["years"][year] = file_data
            
            if client_data["report_types"]:  # Only add if we found data
                summary["clients"].append(client_data)
        
        summary["total_clients"] = len(summary["clients"])
        return jsonify(summary)
        
    except Exception as e:
        return jsonify({"error": f"Failed to generate summary: {str(e)}"}), 500

@app.route('/metadata', methods=['GET'])
def get_metadata():
    """Return structured metadata with category counts"""
    try:
        jsons_dir = os.path.join(os.path.dirname(__file__), 'jsons')
        metadata = {
            "clients": []
        }

        # Walk through all client directories
        for client in os.listdir(jsons_dir):
            client_path = os.path.join(jsons_dir, client)
            if not os.path.isdir(client_path):
                continue
                
            client_data = {
                "client_name": client,
                "report_types": {}
            }
            
            # Process each report type for this client
            for report_type in os.listdir(client_path):
                report_path = os.path.join(client_path, report_type)
                if not os.path.isdir(report_path):
                    continue
                    
                report_data = {
                    "years": {}
                }
                
                # Process each year for this report type
                for year in os.listdir(report_path):
                    year_path = os.path.join(report_path, year)
                    if not os.path.isdir(year_path) or not year.isdigit():
                        continue
                        
                    year_data = {}
                    
                    # Walk through all PDF directories in this year
                    for pdf_dir in os.listdir(year_path):
                        pdf_dir_path = os.path.join(year_path, pdf_dir)
                        if not os.path.isdir(pdf_dir_path):
                            continue
                            
                        category_counts = {}
                        
                        # Count JSON files by category
                        for root, _, files in os.walk(pdf_dir_path):
                            for file in files:
                                if file.endswith('.json'):
                                    try:
                                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                                            data = json.load(f)
                                            
                                            # Extract categories from direct format
                                            if 'categories' in data:
                                                for cat in data.get('categories', []):
                                                    cat_name = cat.get('name')
                                                    if cat_name:
                                                        category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
                                            
                                            # Extract categories from choices format
                                            elif 'choices' in data:
                                                for choice in data.get('choices', []):
                                                    content = choice.get('message', {}).get('content', '{}')
                                                    if content.startswith('```json') and content.endswith('```'):
                                                        content = content[7:-3].strip()
                                                    
                                                    try:
                                                        content_json = json.loads(content) if isinstance(content, str) else content
                                                        if 'categories' in content_json:
                                                            for cat in content_json.get('categories', []):
                                                                cat_name = cat.get('name')
                                                                if cat_name:
                                                                    category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
                                                    except:
                                                        continue
                                    except Exception as e:
                                        print(f"Error reading {os.path.join(root, file)}: {str(e)}")
                                        continue
                        
                        if category_counts:
                            year_data[pdf_dir] = {
                                "category": category_counts
                            }
                    
                    if year_data:
                        report_data["years"][year] = year_data
                
                if report_data["years"]:
                    client_data["report_types"][report_type] = report_data
            
            if client_data["report_types"]:
                metadata["clients"].append(client_data)
        
        return jsonify(metadata)
        
    except Exception as e:
        return jsonify({"error": f"Failed to generate metadata: {str(e)}"}), 500

@app.route('/test')
def test_route():
    return "Server is running", 200

if __name__ == '__main__':
    # Process existing PDFs
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        threading.Thread(target=extract_handler.process_existing_pdfs, daemon=True).start()
    
    app.run(debug=True, port=5000)  # Runs on http://localhost:5000