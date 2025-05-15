import os
import base64
import json
import time
import requests
try:
    import msvcrt  # Windows file locking
except ImportError:
    try:
        import fcntl  # Unix file locking
    except ImportError:
        # Fallback for systems without either module
        fcntl = None
        print("Warning: No file locking available on this system")
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_URL, API_KEY, MODEL_NAME, QWEN_PROMPT
from typing import Dict, Optional

def analyze_image_with_qwen(image_path: str, file_info: Dict, request_semaphore) -> Optional[Dict]:
    """Send image to Qwen API for analysis and categorization."""
    print(f"\nStarting analysis for image: {image_path}")
    with request_semaphore:
        try:
            print(f"Attempting to acquire semaphore for image: {image_path}")
            # Cross-platform file locking
            file_handle = None
            try:
                print(f"Attempting file lock for: {image_path}")
                if os.name == 'nt':  # Windows
                    file_handle = os.open(image_path, os.O_RDWR | os.O_BINARY)
                    msvcrt.locking(file_handle, msvcrt.LK_NBLCK, 1)
                else:  # Linux/Unix
                    file_handle = open(image_path, 'rb')
                    fcntl.flock(file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                print(f"File lock acquired for: {image_path}")
                    
                # Check if file exists and is accessible
                if not os.path.exists(image_path):
                    print(f"Error: Image file not found: {image_path}")
                    return None
                    
                # Read file content directly from the locked handle
                print(f"Reading image data from: {image_path}")
                if os.name == 'nt':
                    os.lseek(file_handle, 0, os.SEEK_SET)
                    image_data = os.read(file_handle, os.path.getsize(image_path))
                else:
                    file_handle.seek(0)
                    image_data = file_handle.read()
                
                image_b64 = base64.b64encode(image_data).decode('utf-8')
                print(f"Image data encoded (size: {len(image_b64)} bytes)")
            
            except Exception as e:
                print(f"Error during file locking/reading: {str(e)}")
                return None
            finally:
                if file_handle:
                    if os.name == 'nt':
                        os.close(file_handle)
                    else:
                        file_handle.close()
                    print(f"File lock released for: {image_path}")

            # Get image extension for mime type
            ext = os.path.splitext(image_path)[1].lower()
            mime = "jpeg" if ext in [".jpg", ".jpeg"] else "png"
            image_data_url = f"data:image/{mime};base64,{image_b64}"
    
            # Get report type from file_info
            report_type = file_info['report_type'].lower()
            document_type = "annual" if "annual" in report_type else "quarterly"
            print(f"Processing as {document_type} report type")
            
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }

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
            
            print(f"Sending request to Qwen API for image: {image_path}")
            response = requests.post(API_URL, json=payload, headers=headers)
            response.raise_for_status()
            print(f"Received response from Qwen API (status: {response.status_code})")
            
            # Add rate limiting between requests
            time.sleep(1)  # Add 1 second delay between API calls
            
            result = response.json()
            print(f"API response parsed successfully")
            
            # Create directory structure using dynamic parameters
            json_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'backend',
                'jsons', 
                file_info['client'], 
                file_info['report_type'], 
                file_info['year'],
                os.path.splitext(file_info['filename'])[0]  # Add filename subdirectory
            )
            print(f"Creating JSON output directory: {json_dir}")
            os.makedirs(json_dir, exist_ok=True)
            
            # Get filename from image_path and create JSON filename
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            json_path = os.path.join(json_dir, f"{base_name}.json")
            print(f"Saving analysis results to: {json_path}")
            
            with open(json_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Results saved successfully")
                
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {str(e)}")
            time.sleep(5)  # Add delay after failure
        except json.JSONDecodeError as e:
            print(f"Invalid API response: {str(e)}")
        except IOError as e:
            print(f"File operation failed: {str(e)}")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
        return None