import os
import json
from typing import Dict
from app import analyze_image_with_qwen  # Import from your main app
from watchdog.events import FileSystemEvent

def find_missing_jsons():
    """Find all image files that don't have corresponding JSON results"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    extracts_dir = os.path.join(base_dir, 'extracts')
    jsons_dir = os.path.join(base_dir, 'jsons')
    
    missing_images = []
    
    # Walk through all extracted images
    for root, _, files in os.walk(extracts_dir):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_path = os.path.join(root, file)
                
                # Calculate corresponding JSON path
                rel_path = os.path.relpath(image_path, extracts_dir)
                json_path = os.path.join(jsons_dir, os.path.splitext(rel_path)[0] + '.json')
                
                if not os.path.exists(json_path):
                    missing_images.append(image_path)
    
    return missing_images

def process_missing_images():
    """Process all images that don't have JSON results"""
    missing_images = find_missing_jsons()
    
    if not missing_images:
        print("No missing JSON files found")
        return
    
    print(f"Found {len(missing_images)} images without JSON results")
    
    for image_path in missing_images:
        print(f"\nProcessing missing image: {image_path}")
        
        try:
            # Extract file info from path
            rel_path = os.path.relpath(image_path, os.path.join(os.path.dirname(__file__), 'extracts'))
            path_parts = rel_path.split(os.sep)
            
            if len(path_parts) >= 4:
                client = path_parts[0]
                report_type = path_parts[1]
                year = path_parts[2]
                
                file_info = {
                    'filename': path_parts[3],
                    'path': image_path,
                    'client': client,
                    'report_type': report_type,
                    'year': year
                }
                
                # Create a fake event object
                class FakeEvent:
                    def __init__(self, src_path):
                        self.src_path = src_path
                        self.is_directory = False
                
                event = FakeEvent(image_path)
                
                # Process using existing handler logic
                analyze_image_with_qwen(image_path, file_info)
                
            else:
                print(f"Skipping image with unexpected path structure: {image_path}")
                
        except Exception as e:
            print(f"Error processing {image_path}: {str(e)}")

def process_specific_image(image_path: str):
    """Process a specific image file"""
    if not os.path.exists(image_path):
        print(f"Error: Image file not found at {image_path}")
        return
    
    print(f"\nProcessing specific image: {image_path}")
    
    try:
        # Extract file info from path
        extracts_dir = os.path.join(os.path.dirname(__file__), 'extracts')
        rel_path = os.path.relpath(image_path, extracts_dir)
        path_parts = rel_path.split(os.sep)
        
        if len(path_parts) >= 4:
            client = path_parts[0]
            report_type = path_parts[1]
            year = path_parts[2]
            
            file_info = {
                'filename': path_parts[3],
                'path': image_path,
                'client': client,
                'report_type': report_type,
                'year': year
            }
            
            # Create a semaphore for rate limiting
            from threading import Semaphore
            request_semaphore = Semaphore(3)  # Same as MAX_CONCURRENT_REQUESTS in app.py
            
            # Process using existing handler logic
            analyze_image_with_qwen(image_path, file_info, request_semaphore)
            
        else:
            print(f"Skipping image with unexpected path structure: {image_path}")
            
    except Exception as e:
        print(f"Error processing {image_path}: {str(e)}")

def process_directory(directory_path: str, reprocess_all: bool = False):
    """Process all images in a directory, with option to reprocess all or continue"""
    extracts_dir = os.path.join(os.path.dirname(__file__), 'extracts')
    jsons_dir = os.path.join(os.path.dirname(__file__), 'jsons')
    
    # Get relative path from extracts directory
    rel_path = os.path.relpath(directory_path, extracts_dir)
    json_dir_path = os.path.join(jsons_dir, rel_path)
    
    if not os.path.exists(directory_path):
        print(f"Error: Directory not found - {directory_path}")
        return
    
    print(f"Processing images in {directory_path}")
    print(f"Reprocess all: {'Yes' if reprocess_all else 'No (only missing)'}")
    
    # Create semaphore for rate limiting
    from threading import Semaphore
    request_semaphore = Semaphore(3)
    
    # Process all images in the directory
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_path = os.path.join(root, file)
                
                # Check if we should skip existing JSONs
                if not reprocess_all:
                    rel_image_path = os.path.relpath(image_path, extracts_dir)
                    json_path = os.path.join(jsons_dir, os.path.splitext(rel_image_path)[0] + '.json')
                    if os.path.exists(json_path):
                        continue
                
                process_specific_image(image_path)

if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Process images for AI analysis')
    parser.add_argument('path', nargs='?', help='Path to image file or directory')
    parser.add_argument('--reprocess', action='store_true', help='Reprocess all images, even those with existing JSON')
    args = parser.parse_args()
    
    if args.path:
        if os.path.isdir(args.path):
            process_directory(args.path, args.reprocess)
        else:
            process_specific_image(args.path)
    else:
        process_missing_images()