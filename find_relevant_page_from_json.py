import json
from sentence_transformers import SentenceTransformer, util

def load_pdf_summary(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def find_most_relevant_page(pages, question):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    page_embeddings = [model.encode(page["text"], convert_to_tensor=True) for page in pages]
    question_embedding = model.encode(question, convert_to_tensor=True)
    similarities = [util.pytorch_cos_sim(question_embedding, emb).item() for emb in page_embeddings]
    best_idx = similarities.index(max(similarities))
    return pages[best_idx], similarities[best_idx]

if __name__ == "__main__":
    json_path = r"c:\Users\chiky\irworkspace\ai_ir\output_analysis\pdf_analysis_summary.json"
    pages = load_pdf_summary(json_path)

    while True:
        question = input("Enter your question (or type 'exit' to quit): ")
        if question.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        best_page, score = find_most_relevant_page(pages, question)
        print(f"Most relevant page: {best_page['page']} (score: {score:.3f})")
        print(best_page["text"][:1000])  # Print first 1000 chars of the page