import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import glob
import os
import sys

# Print the command-line arguments for debugging
print(f"Command-line arguments: {sys.argv}")

output_analysis_dir = r"c:\Users\chiky\irworkspace\ai_ir\output_analysis"
faiss_index_dir = r"c:\Users\chiky\irworkspace\ai_ir\faiss_index"
if not os.path.exists(faiss_index_dir):
    os.makedirs(faiss_index_dir)
model = SentenceTransformer("all-MiniLM-L6-v2")

# Dynamically detect all report type folders
report_types = [d for d in os.listdir(output_analysis_dir) if os.path.isdir(os.path.join(output_analysis_dir, d))]
print(f"Detected report types: {report_types}")

if len(sys.argv) > 1:
    arg = sys.argv[1].lower()
    
    # First collect all possible clients across all report types
    all_clients = set()
    for rt in report_types:
        all_clients.update([c.lower() for c in os.listdir(os.path.join(output_analysis_dir, rt)) 
                          if os.path.isdir(os.path.join(output_analysis_dir, rt, c))])
    
    if arg in all_clients:
        # Argument is a client name - process across all report types that contain this client
        clients = [arg]
        report_types = [rt for rt in report_types 
                       if os.path.exists(os.path.join(output_analysis_dir, rt, arg))]
    elif arg in [rt.lower() for rt in report_types]:
        # Argument is a report type
        report_types = [rt for rt in report_types if rt.lower() == arg]
        if len(sys.argv) > 2:
            clients = [sys.argv[2].lower()]
        else:
            clients = None
    else:
        print(f"Error: '{arg}' is not a valid report type or client")
        sys.exit(1)
else:
    clients = None
    folders = None

for report_type in report_types:
    report_dir = os.path.join(output_analysis_dir, report_type)
    if clients:  # If specific clients were provided
        folders = [c for c in clients if os.path.isdir(os.path.join(report_dir, c))]
    else:  # If no clients specified, process all
        folders = [folder for folder in os.listdir(report_dir) if os.path.isdir(os.path.join(report_dir, folder))]
    print(f"Processing client folder: {report_type}")  # Debugging statement
    if clients:
        folders = [c for c in clients if os.path.isdir(os.path.join(report_dir, c))]
    else:
        folders = [folder for folder in os.listdir(report_dir) if os.path.isdir(os.path.join(report_dir, folder))]
    
    for folder in folders:
        print(f"Processing report type: {folder}")  # Debugging statement
        # Ensure only the specified client is processed
        if clients and folder not in clients:
            continue  # Skip any client that is not specified in the argument
        folder_path = os.path.join(report_dir, folder)
        years = [y for y in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, y))]
        
        # First collect all pages across years
        all_pages = []
        for year in years:
            year_path = os.path.join(folder_path, year)
            summary_files = glob.glob(os.path.join(year_path, "**", "pdf_analysis_summary.json"), recursive=True)
            if not summary_files:
                continue

            pages = []
            for file in summary_files:
                with open(file, "r", encoding="utf-8") as f:
                    year_pages = json.load(f)
                    # Add year info to each page
                    for page in year_pages:
                        page['year'] = year
                    pages.extend(year_pages)
                    all_pages.extend(year_pages)

            if not pages:
                continue

            # Create yearly index
            texts = [page["text"] for page in pages]
            embeddings = model.encode(texts, convert_to_numpy=True)
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            index.add(embeddings)

            group_faiss_dir = os.path.join(faiss_index_dir, report_type, folder, year)
            if not os.path.exists(group_faiss_dir):
                os.makedirs(group_faiss_dir)

            index_path = os.path.join(group_faiss_dir, "faiss_pages.index")
            summary_path = os.path.join(group_faiss_dir, "pdf_analysis_summary.json")
            faiss.write_index(index, index_path)
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(pages, f)

            print(f"Indexed {len(pages)} pages for '{report_type}/{folder}/{year}' -> {index_path}")

        # Create combined index after yearly indices
        all_pages = []
        for year in years:
            year_path = os.path.join(folder_path, year)
            summary_files = glob.glob(os.path.join(year_path, "**", "pdf_analysis_summary.json"), recursive=True)
            if not summary_files:
                continue

            pages = []
            for file in summary_files:
                with open(file, "r", encoding="utf-8") as f:
                    year_pages = json.load(f)
                    # Add year info to each page
                    for page in year_pages:
                        page['year'] = year
                    pages.extend(year_pages)
                    all_pages.extend(pages)

            if all_pages:
                # Create combined index
                texts = [p["text"] for p in all_pages]
                embeddings = model.encode(texts, convert_to_numpy=True)
                index = faiss.IndexFlatL2(embeddings.shape[1])
                index.add(embeddings)
                
                combined_dir = os.path.join(faiss_index_dir, report_type, folder, "combined")
                os.makedirs(combined_dir, exist_ok=True)
                
                faiss.write_index(index, os.path.join(combined_dir, "faiss_pages.index"))
                with open(os.path.join(combined_dir, "pages_meta.json"), "w") as f:
                    json.dump([{"text": p["text"], "page": p["page"], "year": year} 
                              for p in all_pages], f)