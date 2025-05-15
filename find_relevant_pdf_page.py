import pdfplumber
from sentence_transformers import SentenceTransformer, util

def extract_pdf_pages(pdf_path, max_pages=None):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        last_page = max_pages if max_pages else total_pages
        for i, page in enumerate(pdf.pages[:last_page], start=1):
            text = page.extract_text() or ""
            pages.append({"page": i, "text": text.strip()})
    return pages

def find_most_relevant_page(pages, question):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    page_embeddings = [model.encode(page["text"], convert_to_tensor=True) for page in pages]
    question_embedding = model.encode(question, convert_to_tensor=True)
    similarities = [util.pytorch_cos_sim(question_embedding, emb).item() for emb in page_embeddings]
    best_idx = similarities.index(max(similarities))
    return pages[best_idx], similarities[best_idx]

if __name__ == "__main__":
    pdf_path = r"c:\Users\chiky\irworkspace\ai_ir\files\fr2023.pdf"
    pages = extract_pdf_pages(pdf_path, max_pages=50)  # Adjust max_pages as needed

    while True:
        question = input("Enter your question (or type 'exit' to quit): ")
        if question.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        best_page, score = find_most_relevant_page(pages, question)
        print(f"Most relevant page: {best_page['page']} (score: {score:.3f})")
        print(best_page["text"][:1000])  # Print first 1000 chars of the page