import os
from openai import OpenAI
import PyPDF2
import json

CACHE_FILE = "fas_contexts.json"
PDF_PATHS = {
    "musharaka": "./fas_documents/FAS4_Musharaka.pdf",
    "murabaha": "./fas_documents/FAS28_Murabaha.pdf",
    "istisna": "./fas_documents/FAS10_Istisna.pdf",
    "salam": "./fas_documents/FAS7_Salam.pdf",
    "ijara": "./fas_documents/FAS32_Ijarah.pdf",
}


# 📄 Load and extract PDF text
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        return "\n".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )


# 🔁 Load or extract and cache
def load_fas_contexts():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        contexts = {
            name: extract_text_from_pdf(path) for name, path in PDF_PATHS.items()
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(contexts, f)
        return contexts


# 🧠 Load FAS contexts only once
FAS_CONTEXTS = load_fas_contexts()
