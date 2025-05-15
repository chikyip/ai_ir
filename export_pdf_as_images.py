from pdf2image import convert_from_path
import os

def export_pdf_as_images(pdf_path, output_folder, max_pages=None, timeout=60):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    try:
        images = convert_from_path(
            pdf_path,
            dpi=100,
            first_page=1,
            last_page=max_pages if max_pages else None
            # threaded and timeout removed for compatibility
        )
        for i, image in enumerate(images, start=1):
            img_path = os.path.join(output_folder, f"page_{i}.png")
            image.save(img_path, "PNG")
            print(f"Saved: {img_path}")
    except Exception as e:
        print(f"Error during PDF conversion: {e}")

if __name__ == "__main__":
    pdf_path = input("Enter the path to your PDF file: ")
    output_folder = input("Enter the output folder for images: ")
    # Example: process only the first 5 pages, with a 60-second timeout
    export_pdf_as_images(pdf_path, output_folder, max_pages=200, timeout=60)