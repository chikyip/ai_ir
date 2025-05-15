import os
import math
import fitz  # PyMuPDF
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # Remove decompression bomb protection

def clear_output_dir(output_dir):
    if os.path.exists(output_dir):
        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

def pdf_pages_to_two_column_image(pdf_path, output_dir, target_width=2400, output_format='JPEG', quality=95, max_dim=65500):
    print(f"Starting PDF processing: {pdf_path}")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    print(f"PDF name: {pdf_name}")
    
    print(f"Opening PDF document...")
    doc = fitz.open(pdf_path)
    print(f"PDF has {len(doc)} pages")
    
    images = []
    for page_num in range(len(doc)):
        print(f"Processing page {page_num + 1}/{len(doc)}")
        page = doc.load_page(page_num)
        zoom = 6.0  # Increased zoom from 5.5 for better clarity
        print(f"Using zoom factor: {zoom}")
        mat = fitz.Matrix(zoom, zoom)
        print(f"Creating pixmap for page {page_num + 1}...")
        pix = page.get_pixmap(matrix=mat)
        print(f"Pixmap dimensions: {pix.width}x{pix.height} pixels")
        
        img_path = os.path.join(output_dir, f"{pdf_name}_page_{page_num + 1}.png")
        
        # Save with size check
        if pix.width * pix.height > 200000000:  # 200MP limit
            print(f"Image exceeds 200MP limit ({pix.width}x{pix.height}={pix.width * pix.height} pixels)")
            zoom_factor_for_limit = math.sqrt(200000000 / (pix.width * pix.height)) 
            print(f"Reducing zoom by factor of {zoom_factor_for_limit:.4f}")
            mat = fitz.Matrix(zoom * zoom_factor_for_limit, zoom * zoom_factor_for_limit) # Apply relative reduction
            pix = page.get_pixmap(matrix=mat)
            print(f"New pixmap dimensions: {pix.width}x{pix.height} pixels")
            
        print(f"Saving page to: {img_path}")
        pix.save(img_path)
        print(f"Loading image with PIL...")
        img = Image.open(img_path).convert("RGB")
        print(f"Image dimensions: {img.width}x{img.height} pixels")
        images.append(img)
        print(f"Saved: {img_path}")
    
    print(f"Closing PDF document")
    doc.close()

    if images:
        print(f"Creating combined image from {len(images)} pages")
        columns = 2 
        total_images = len(images)
        rows = math.ceil(total_images / columns)
        print(f"Using {columns} columns and {rows} rows")
        
        # Calculate max width per column and row heights
        col_widths = [0] * columns
        row_heights = [0] * rows
        
        for i, img in enumerate(images):
            row = i // columns
            col = i % columns
            col_widths[col] = max(col_widths[col], img.width)
            row_heights[row] = max(row_heights[row], img.height)
        
        print(f"Column widths: {col_widths}")
        print(f"Row heights: {row_heights}")
        
        total_width = sum(col_widths)
        total_height = sum(row_heights)
        print(f"Combined image dimensions will be: {total_width}x{total_height} pixels")
        
        # Create an RGB image with a white background
        print(f"Creating new image with white background...")
        combined = Image.new('RGB', (total_width, total_height), (255, 255, 255))
        
        print(f"Pasting individual images into combined image...")
        y_offset = 0
        for row in range(rows):
            x_offset = 0
            for col in range(columns):
                idx = row * columns + col
                if idx < total_images:
                    img = images[idx]
                    print(f"Pasting image {idx+1} at position ({x_offset}, {y_offset})")
                    combined.paste(img, (x_offset, y_offset))
                    x_offset += col_widths[col]
            y_offset += row_heights[row]
        
        # Only resize if the combined image exceeds max_dim
        if combined.width > max_dim or combined.height > max_dim:
            print(f"Combined image exceeds maximum dimension of {max_dim} pixels")
            scale_w = max_dim / combined.width
            scale_h = max_dim / combined.height
            scale = min(scale_w, scale_h, 1.0)
            new_size = (int(combined.width * scale), int(combined.height * scale))
            print(f"Resizing to {new_size[0]}x{new_size[1]} pixels (scale factor: {scale:.4f})")
            combined = combined.resize(new_size, Image.LANCZOS)

        # Single optimized save operation
        combined_path = os.path.join(output_dir, f"{pdf_name}_2col.jpg")
        print(f"Saving combined image to: {combined_path}")
        print(f"Save parameters: format=JPEG, quality={quality}, optimize=True, progressive=True, subsampling=0")
        combined.save(combined_path, 
                    format='JPEG',
                    quality=95,
                    optimize=True,
                    progressive=True,
                    subsampling=0,
                    )
        print(f"Combined 2-column image saved: {combined_path}")
        print(f"Final image size: {os.path.getsize(combined_path)/1024/1024:.2f} MB")

def process_all_pdfs(input_dir, output_dir, target_width=1000, output_format='JPEG', quality=70, max_dim=65000):
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(input_dir, filename)
            pdf_pages_to_auto_grid_single_image(pdf_path, output_dir, target_width, output_format, quality, max_dim)

if __name__ == "__main__":
    input_path = r"C:\Users\chiky\irworkspace\ai_ir\backend\uploads\mrcb\annual\2024\ar2024.pdf"  # Can be file or directory
    output_dir = r"c:\Users\chiky\irworkspace\ai_ir\pdf_images"
    clear_output_dir(output_dir)  # Clear the output directory before processing
    if os.path.isfile(input_path):
        pdf_pages_to_two_column_image(input_path, output_dir, target_width=2400, output_format='JPEG', quality=95, max_dim=65500)
    elif os.path.isdir(input_path):
        for filename in os.listdir(input_path):
            if filename.lower().endswith('.pdf'):
                pdf_path = os.path.join(input_path, filename)
                pdf_pages_to_two_column_image(pdf_path, output_dir, target_width=2400, output_format='JPEG', quality=95, max_dim=65500)
    else:
        print(f"Input path does not exist: {input_path}")