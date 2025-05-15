import os
import fitz  # PyMuPDF for PDF processing
import time
from typing import Dict

def process_pdf_with_qwen(file_info: Dict):
    """Process PDF and extract images without analyzing them"""
    try:
        print(f"Starting PDF processing for: {file_info['path']}")
        
        # Check if file exists and is accessible
        if not os.path.exists(file_info['path']):
            print(f"Error: PDF file not found: {file_info['path']}")
            return
            
        # Check if file is empty
        if os.path.getsize(file_info['path']) == 0:
            print(f"Error: PDF file is empty: {file_info['path']}")
            return
            
        extracts_dir = os.path.join(
            os.path.dirname(__file__),
            'extracts',
            file_info['client'],
            file_info['report_type'],
            file_info['year'],
            os.path.splitext(file_info['filename'])[0]  # Add filename subdirectory
        )
        print(f"Creating extracts directory: {extracts_dir}")
        os.makedirs(extracts_dir, exist_ok=True)

        print(f"Opening PDF document: {file_info['path']}")
        pdf_document = fitz.open(file_info['path'])
        
        # If PDF has 0 pages, return early but don't block future processing
        if len(pdf_document) == 0:
            print(f"PDF has 0 pages, skipping but allowing future processing: {file_info['path']}")
            pdf_document.close()
            return
        
        print(f"Processing {len(pdf_document)} pages...")
        for page_num in range(len(pdf_document)):
            print(f"Processing page {page_num+1}/{len(pdf_document)}")
            page = pdf_document.load_page(page_num)
            
            # Further optimized settings for smallest file size while maintaining OCR quality
            pix = page.get_pixmap(
                matrix=fitz.Matrix(0.8, 0.8),  # Reduced further from 1.0 to 0.8
                colorspace="gray",  # Keep grayscale
                dpi=120,  # Reduced from 150 to 120
                alpha=False  # Disable alpha channel
            )
            
            base_filename = os.path.splitext(file_info['filename'])[0]
            image_filename = f"{base_filename}_page_{page_num+1}.jpg"  # Fixed variable name
            image_path = os.path.join(extracts_dir, image_filename)
            
            # Modified save parameters - removed unsupported parameters
            pix.save(image_path, 
                   jpg_quality=60  # Only using supported parameter
            )
            
            print(f"Page {page_num+1} processed successfully (size: {os.path.getsize(image_path)/1024:.1f} KB)")
        
        pdf_document.close()
        print(f"Completed processing: {file_info['path']}")
        # The ExtractHandler will detect these new images and analyze them
    except Exception as e:
        print(f"Error processing PDF {file_info['path']}: {str(e)}")