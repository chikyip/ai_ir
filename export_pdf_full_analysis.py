import pdfplumber
import os
import json
import csv
import glob
import sys

def export_pdf_for_ai(pdf_path, output_folder, max_pages=None):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    summary = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        last_page = max_pages if max_pages else total_pages
        for i, page in enumerate(pdf.pages[:last_page], start=1):
            page_info = {"page": i, "text": "", "tables": [], "images": []}

            # Extract text
            text = page.extract_text() or ""
            page_info["text"] = text.strip()

            # Extract tables
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables, start=1):
                table_path = os.path.join(output_folder, f"page_{i}_table_{t_idx}.csv")
                with open(table_path, "w", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    for row in table:
                        writer.writerow(row)
                page_info["tables"].append(table_path)

            # --- Export full page as image only ---
            try:
                full_img_path = os.path.join(output_folder, f"page_{i}_full.png")
                page.to_image(resolution=200).save(full_img_path, format="PNG")
                page_info["images"].append(full_img_path)
            except Exception as e:
                print(f"Failed to export full page image on page {i}: {e}")

            summary.append(page_info)

    # Save summary JSON
    summary_path = os.path.join(output_folder, "pdf_analysis_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Exported analysis summary to {summary_path}")

if __name__ == "__main__":
    pdfs_base_folder = r"c:\Users\chiky\irworkspace\ai_ir\files"
    output_base_folder = r"c:\Users\chiky\irworkspace\ai_ir\output_analysis"
    max_pages = 500

    # If a specific PDF path is provided, analyze only that PDF
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith('.pdf'):
        pdf_path = sys.argv[1]
        # Determine client, category, year and pdf_name for output path
        rel_path = os.path.relpath(pdf_path, pdfs_base_folder)
        parts = rel_path.split(os.sep)
        if len(parts) < 4:  # Changed from 3 to 4 to account for year
            print("PDF path must be under <client>/<category>/<year>/<pdf>.pdf")
            sys.exit(1)
        client, category, year = parts[0], parts[1], parts[2]
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_folder = os.path.join(output_base_folder, client, category, year, pdf_name)
        print(f"Processing {pdf_path} -> {output_folder}")
        export_pdf_for_ai(pdf_path, output_folder, max_pages=max_pages)
    else:
        # Support optional client or category argument
        if len(sys.argv) > 1:
            clients = [sys.argv[1]]
        else:
            clients = [d for d in os.listdir(pdfs_base_folder) if os.path.isdir(os.path.join(pdfs_base_folder, d))]

        for client in clients:
            client_path = os.path.join(pdfs_base_folder, client)
            if not os.path.isdir(client_path):
                continue
            categories = [c for c in os.listdir(client_path) if os.path.isdir(os.path.join(client_path, c))]
            for category in categories:
                category_path = os.path.join(client_path, category)
                years = [y for y in os.listdir(category_path) if os.path.isdir(os.path.join(category_path, y))]
                for year in years:
                    year_path = os.path.join(category_path, year)
                    pdf_files = glob.glob(os.path.join(year_path, "*.pdf"))
                    for pdf_path in pdf_files:
                        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
                        output_folder = os.path.join(output_base_folder, client, category, year, pdf_name)
                        print(f"Processing {pdf_path} -> {output_folder}")
                        export_pdf_for_ai(pdf_path, output_folder, max_pages=max_pages)