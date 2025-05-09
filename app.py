import os
from openai import OpenAI
import PyPDF2

# 🔑 Set your OpenAI API key
client = OpenAI(
    api_key="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"
)


# 📄 Load and extract PDF text
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        return "\n".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )


# 🧠 Load FAS contexts once
FAS_CONTEXTS = {
    "musharaka": extract_text_from_pdf("./fas_documents/FAS4_Musharaka.pdf"),
    "murabaha": extract_text_from_pdf("./fas_documents/FAS28_Murabaha.pdf"),
    "istisna": extract_text_from_pdf("./fas_documents/FAS10_Istisna.pdf"),
    "salam": extract_text_from_pdf("./fas_documents/FAS7_Salam.pdf"),
    "ijara": extract_text_from_pdf("./fas_documents/FAS32_Ijarah.pdf"),
}


# 🧠 Agent Function
def fas_agent(contract_type: str, query: str) -> str:
    if contract_type not in FAS_CONTEXTS:
        return f"Unsupported contract type: {contract_type}"

    context = FAS_CONTEXTS[contract_type]
    prompt = f"""
You are an expert in AAOIFI Financial Accounting Standards (FAS), specifically FAS related to {contract_type.title()}.

Here is the relevant FAS content:
{context[:10000]}  # Truncate for token safety, or chunk and RAG for advanced use

Question:
{query}

Return only the applicable rules, articles or guidance and how to apply them.
"""

    response = client.chat.completions.create(
        model="gpt-4", messages=[{"role": "user", "content": prompt}], temperature=0.2
    )
    return response.choices[0].message.content.strip()


# 🧪 Example usage
if __name__ == "__main__":
    contract = "istisna"
    query = """Context: The client cancels the change order, reverting to the original contract terms.
Adjustments:
Revised Contract Value: Back to $5,000,000
Timeline Restored: 2 years
Accounting Treatment:
Adjustment of revenue and cost projections
Reversal of additional cost accruals
Journal Entry for Cost Reversal:
Dr. Accounts Payable $1,000,000
Cr. Work-in-Progress $1,000,000
This restores the original contract cost."""

    answer = fas_agent(contract, query)
    print(f"\n📘 Answer for '{contract}':\n{answer}")
