import os
import json
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import openai
import PyPDF2
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi.responses import JSONResponse
from typing import List, Dict

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔑 Initialize OpenAI client
openai.api_key = "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"

app = FastAPI()

# Add CORS middleware with more specific configuration
origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")
    try:
        body = await request.json()
        logger.info(f"Request body: {body}")
    except:
        logger.info("No request body")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

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

class ContractTypeScore(BaseModel):
    type: str
    confidence: float
    description: str

class DetectionResponse(BaseModel):
    scores: List[ContractTypeScore]
    primary_type: str

# 🔍 FAS Query Endpoint
@app.post("/fas-agent")
async def fas_agent_endpoint(request: Request, query_request: QueryRequest):
    try:
        contract_type = query_request.contract_type.lower()
        query = query_request.query

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
        response = openai.ChatCompletion.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return JSONResponse(
            content={"response": response.choices[0].message.content.strip()},
            headers={
                "Access-Control-Allow-Origin": request.headers.get("origin", "http://localhost:8080"),
                "Access-Control-Allow-Credentials": "true",
            }
        )
    except Exception as e:
        logger.error(f"Error in fas_agent_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 🤖 Contract Type Detection and Delegation
@app.post("/detect-contract-type")
async def detect_and_delegate(request: Request, detect_request: DetectRequest):
    try:
        query = detect_request.query
        logger.info(f"Processing query: {query}")

        detection_prompt = f"""
You are an AI trained on AAOIFI Financial Accounting Standards. Analyze the following query and determine the relevance of each contract type.
For each contract type, provide:
1. A confidence score (0-100) indicating how relevant it is
2. A brief explanation of why it is relevant or not

Contract types to analyze:
- Musharaka
- Murabaha
- Istisna
- Salam
- Ijara

Query: {query}

Return your analysis in the following format:
[
    {{
        "type": "contract_type_name",
        "confidence": number between 0 and 100,
        "description": "brief explanation"
    }}
]

Sort the results by confidence score in descending order. Make sure to return valid JSON.
The sum of all confidence scores should be 100.
"""
        detection_response = openai.ChatCompletion.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": detection_prompt}],
            temperature=0,
        )
        
        try:
            # Extract the JSON string from the response
            response_text = detection_response.choices[0].message.content.strip()
            # Find the first [ and last ] to extract the JSON array
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON array found in response")
            
            json_str = response_text[start_idx:end_idx]
            scores_data = json.loads(json_str)
            
            # Normalize confidence scores to sum up to 100
            total_confidence = sum(score["confidence"] for score in scores_data)
            if total_confidence > 0:  # Avoid division by zero
                for score in scores_data:
                    score["confidence"] = round((score["confidence"] / total_confidence) * 100, 1)
            
            scores = [ContractTypeScore(**score) for score in scores_data]
            
            # Get the primary type (highest confidence)
            primary_type = scores[0].type.lower()
            
            if primary_type not in FAS_CONTEXTS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not classify query into a valid contract type. Got: {primary_type}",
                )

            # Get the detailed analysis for the primary type
            analysis = await fas_agent_endpoint(request, QueryRequest(contract_type=primary_type, query=query))
            
            return JSONResponse(
                content={
                    "scores": [score.dict() for score in scores],
                    "primary_type": primary_type,
                    "analysis": analysis.body.decode()
                },
                headers={
                    "Access-Control-Allow-Origin": request.headers.get("origin", "http://localhost:8080"),
                    "Access-Control-Allow-Credentials": "true",
                }
            )
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing detection response: {str(e)}")
            logger.error(f"Raw response: {detection_response.choices[0].message.content}")
            raise HTTPException(status_code=500, detail="Error parsing AI response")
            
    except Exception as e:
        logger.error(f"Error in detect_and_delegate: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 🧪 Local testing (optional)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
