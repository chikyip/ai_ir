import os
import json
import requests
import re  # Add this import for regular expressions
from typing import List, Dict
import base64
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # Remove decompression bomb protection
from io import BytesIO

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_URL, API_KEY, MODEL_NAME, FINANCIAL_HIGHLIGHTS_PROMPT, QUARTERLY_PERFORMANCE_PROMPT

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

def get_categories(client: str, report_type: str, years: List[str]) -> List[Dict]:
    """Get all categories for given client, report type and years"""
    jsons_dir = os.path.join(os.path.dirname(__file__), 'jsons')
    categories = []
    
    for year in years:
        year_dir = os.path.join(jsons_dir, client, report_type, year)
        if not os.path.exists(year_dir):
            continue
            
        for root, _, files in os.walk(year_dir):
            for file in files:
                if file.endswith('.json'):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            # Initialize variables
                            content_json = None
                            
                            # Parse content_json if available (choices format)
                            if 'choices' in data:
                                try:
                                    content = data['choices'][0]['message']['content']
                                    if content.startswith('```json') and content.endswith('```'):
                                        content = content[7:-3].strip()
                                    content_json = json.loads(content) if isinstance(content, str) else content
                                except Exception as e:
                                    print(f"Error parsing content_json: {str(e)}")
                            
                            # Extract categories from both formats
                            if 'categories' in data:  # Direct format
                                categories.extend(data['categories'])
                            elif content_json and 'categories' in content_json:  # Choices format
                                categories.extend(content_json['categories'])
                                
                    except Exception as e:
                        print(f"Error reading {os.path.join(root, file)}: {str(e)}")
                        continue
                        
    return categories

def process_with_qwen(content: str, prompt: str, image_paths: List[str] = None) -> Dict:
    """Send content to Qwen API for processing with optional images"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    }
    
    # Build message content
    message_content = [
        # {"type": "text", "text": content}
    ]

    # Add all images if provided
    if image_paths:
        for image_path in image_paths:
            if os.path.exists(image_path):
                # Compose the data URL for the image
                image_b64 = encode_image_to_base64(image_path)
                ext = os.path.splitext(image_path)[1].lower()
                mime = "jpeg" if ext in [".jpg", ".jpeg"] else "png"
                image_data_url = f"data:image/{mime};base64,{image_b64}"          
                message_content.append({
                    "type": "image_url",
                    "image_url": image_data_url
                })
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system", 
                "content": [{"type": "text", "text": prompt}]
            },
            {
                "role": "user",
                "content": message_content
            }
        ],
        # "temperature": 0.7,
        # "max_tokens": 4000  # Increased for handling multiple images
    }
    
    print(payload)

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error calling Qwen API: {str(e)}")
        raise

def process_client_data(client: str, report_type: str, year: str, pdf_dir: str = None):
    """Main processing function - groups content by category before processing"""
    jsons_dir = os.path.join(os.path.dirname(__file__), 'jsons')
    
    # Dictionary to store grouped content by category
    category_content = {}
    
    # First pass: collect all content grouped by category
    year_dir = os.path.join(jsons_dir, client, report_type, year)
    if not os.path.exists(year_dir):
        print(f"Year directory not found: {year_dir}")
        return
            
    # If pdf_dir is specified, only process that directory
    target_dirs = [os.path.join(year_dir, pdf_dir)] if pdf_dir else [os.path.join(year_dir, d) for d in os.listdir(year_dir) if os.path.isdir(os.path.join(year_dir, d))]
    
    for target_dir in target_dirs:
        if not os.path.isdir(target_dir):
            continue
            
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.endswith('.json'):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            # Get content from choices if available
                            content_json = None
                            if 'choices' in data:
                                try:
                                    content = data['choices'][0]['message']['content']
                                    if content.startswith('```json') and content.endswith('```'):
                                        content = content[7:-3].strip()
                                    content_json = json.loads(content) if isinstance(content, str) else content
                                except Exception as e:
                                    print(f"Error parsing content_json: {str(e)}")
                            
                            # Get categories from either format
                            categories = []
                            if 'categories' in data:
                                categories = data['categories']
                            elif content_json and 'categories' in content_json:
                                categories = content_json['categories']
                            
                            # Group content by category
                            for category in categories:
                                cat_name = category.get('name', 'unknown').replace(' ', '_').lower()
                                if not cat_name:
                                    continue
                                    
                                if cat_name not in category_content:
                                    category_content[cat_name] = []
                                    
                                # Store both category info and source file reference
                                category_content[cat_name].append({
                                    'category_data': category,
                                    'source_file': os.path.join(root, file)
                                })
                                    
                    except Exception as e:
                        print(f"Error reading {os.path.join(root, file)}: {str(e)}")
    
    if not category_content:
        print(f"No categories found for {client}/{report_type}/{years}")
        return
    
    # Create output directory - changed to use single year
    output_dir = os.path.join(os.path.dirname(__file__), 'processed', client, report_type, year, pdf_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each category's grouped content
    for category_name, contents in category_content.items():
        try:
            print(f"Processing report_type: {report_type}, category: {category_name} with {len(contents)} items")
            
            # Get appropriate prompt for this category
            prompt = get_prompt_by_category(category_name, report_type)
            if not prompt:
                continue
                
            # Collect all image paths for this category
            image_paths = []
            for content in contents:
                if 'source_file' in content:
                    json_path = content['source_file']
                    print(f"Processing source file: {json_path}")  # Debug print
                    
                    # Extract page number from JSON filename
                    page_match = re.search(r'_page_(\d+)\.json', json_path)
                    if page_match:
                        page_num = page_match.group(1)
                        print(f"Found page number: {page_num}")  # Debug print
                        
                        # Build image path
                        base_name = os.path.splitext(os.path.basename(json_path))[0]
                        print(f"Base filename: {base_name}")  # Debug print
                        
                        image_path = os.path.join(
                            os.path.dirname(__file__), 
                            'extracts', 
                            client, 
                            report_type, 
                            year,
                            pdf_dir if pdf_dir else '',
                            f"{base_name}.jpg"
                        )
                        print(f"Constructed image path: {image_path}")  # Debug print
                        
                        if os.path.exists(image_path):
                            print(f"Image found at path: {image_path}")  # Debug print
                            image_paths.append(image_path)
                            if len(image_paths) >= 10:  # Limit to 5 images
                                break
                        else:
                            print(f"Warning: Image not found at path: {image_path}")  # Debug print
                    else:
                        print(f"Warning: Could not extract page number from filename: {json_path}")  # Debug print
            
            # Prepare payload with all content for this category
            payload = {
                'category': category_name,
                'contents': contents,
                'image_paths': image_paths  # Include all image paths
            }

            print(payload)
            
            # Process with Qwen API - modified to handle multiple images
            result = process_with_qwen(
                json.dumps(payload, indent=2),
                prompt,
                image_paths=image_paths  # Pass all images
            )
            
            output_file = os.path.join(output_dir, f"{category_name}.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            print(f"Saved processed category to {output_file}")
            
        except Exception as e:
            print(f"Error processing category {category_name}: {str(e)}")

def process_all_client_data():
    """Process all JSON files found in the jsons directory structure"""
    jsons_dir = os.path.join(os.path.dirname(__file__), 'jsons')
    
    # Walk through all client directories
    for client in os.listdir(jsons_dir):
        client_path = os.path.join(jsons_dir, client)
        if not os.path.isdir(client_path):
            continue
            
        # Process each report type for this client
        for report_type in os.listdir(client_path):
            report_path = os.path.join(client_path, report_type)
            if not os.path.isdir(report_path):
                continue
                
            # Process each year for this report type
            for year in os.listdir(report_path):
                year_path = os.path.join(report_path, year)
                if not os.path.isdir(year_path) or not year.isdigit():
                    continue
                
                # Process each PDF directory under the year (like 'ar2024')
                for pdf_dir in os.listdir(year_path):
                    pdf_dir_path = os.path.join(year_path, pdf_dir)
                    if not os.path.isdir(pdf_dir_path):
                        continue
                    
                    # Check if there are any JSON files in this PDF directory
                    has_json_files = any(f.endswith('.json') for f in os.listdir(pdf_dir_path))
                    
                    if has_json_files:
                        print(f"Processing {client}/{report_type}/{year}/{pdf_dir}")
                        try:
                            process_client_data(client, report_type, year, pdf_dir)  # Changed to pass single year
                        except Exception as e:
                            print(f"Error processing {client}/{report_type}/{year}/{pdf_dir}: {str(e)}")

def get_prompt_by_category(category_name: str, report_type: str) -> str:
    """Get the appropriate prompt based on category name and report type"""
    category_name = category_name.lower()
    report_type = report_type.lower()
    
    # Financial highlights only for annual reports
    if 'financial_highlights' in category_name and report_type == 'annual':
        return FINANCIAL_HIGHLIGHTS_PROMPT
    
    # Quarterly performance only for quarterly reports
    if 'financial_statements' in category_name and report_type == 'quarterly':
        return QUARTERLY_PERFORMANCE_PROMPT
    
    return None  # Return None if no matching prompt

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Process financial data categories')
    parser.add_argument('client', help='Client name')
    parser.add_argument('report_type', help='Report type (annual/quarterly)')
    parser.add_argument('year', help='Year to process')
    parser.add_argument('pdf_dir', nargs='?', default=None, help='Optional PDF directory name')
    
    args = parser.parse_args()
    process_client_data(args.client, args.report_type, args.year, args.pdf_dir)  # Now this will work