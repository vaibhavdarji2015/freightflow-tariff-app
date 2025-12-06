import requests
import pdfplumber
import io
from fastapi import HTTPException

def download_pdf(url: str) -> bytes:
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {str(e)}")

def extract_text_from_pdf(pdf_content: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            text = ""
            for page in pdf.pages:
                # Extract text
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                
                # Optionally extract tables if needed, but for now we'll rely on LLM to parse the text/structure
                # tables = page.extract_tables()
            return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from PDF: {str(e)}")
