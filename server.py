import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import PyPDF2
import uvicorn

# 🔑 Initialize OpenAI client
client = OpenAI(
    api_key="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"
)

app = FastAPI()


# 📄 Extract PDF text
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        return "\n".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )


# 💾 Storage path
CACHE_FILE = "fas_contexts.json"
PDF_PATHS = {
    "musharaka": "./fas_documents/FAS4_Musharaka.pdf",
    "murabaha": "./fas_documents/FAS28_Murabaha.pdf",
    "istisna": "./fas_documents/FAS10_Istisna.pdf",
    "salam": "./fas_documents/FAS7_Salam.pdf",
    "ijara": "./fas_documents/FAS32_Ijarah.pdf",
}


# 🔁 Load or extract contexts
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


# 🧠 Load once
FAS_CONTEXTS = load_fas_contexts()


# Pydantic models
class QueryRequest(BaseModel):
    contract_type: str
    query: str


class DetectRequest(BaseModel):
    query: str


# 🔍 FAS Query Endpoint
@app.post("/fas-agent")
def fas_agent_endpoint(request: QueryRequest):
    contract_type = request.contract_type.lower()
    query = request.query

    if contract_type not in FAS_CONTEXTS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported contract type: {contract_type}"
        )

    context = FAS_CONTEXTS[contract_type]
    prompt = f"""
You are an expert in AAOIFI Financial Accounting Standards (FAS), specifically FAS related to {contract_type.title()}.

Here is the relevant FAS content:
{context[:10000]}  # Truncated for token limit

Question:
{query}

Your task:
1. Make sure to read all the FAS document and identify the applicable rules/articles for the query.
2. Apply them to the values provided, doing all required calculations step-by-step.
3. Show journal entries where applicable.
4. Explain why each step is done based on the standard.

Only use information from the FAS context, and clearly show your math steps.
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return {"response": response.choices[0].message.content.strip()}


# 🤖 Contract Type Detection and Delegation
@app.post("/detect-contract-type")
def detect_and_delegate(request: DetectRequest):
    query = request.query

    detection_prompt = f"""
You are an AI trained on AAOIFI Financial Accounting Standards. The following are contract types:
- Musharaka
- Murabaha
- Istisna
- Salam
- Ijara

Given the user query below, return only the most relevant contract type from the list above (in lowercase). Do not explain.

Query: {query}
"""
    detection_response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": detection_prompt}],
        temperature=0,
    )
    detected_type = detection_response.choices[0].message.content.strip().lower()

    if detected_type not in FAS_CONTEXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Could not classify query into a valid contract type. Got: {detected_type}",
        )

    return fas_agent_endpoint(QueryRequest(contract_type=detected_type, query=query))


# 🧪 Local testing (optional)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
