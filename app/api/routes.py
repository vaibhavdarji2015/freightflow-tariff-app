from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.models.schemas import TariffRequest, TariffResponse
from app.services import pdf_service, ai_service, db_service
from app.services import ai_service_simple
from pydantic import BaseModel

router = APIRouter()

class SimpleRequest(BaseModel):
    url: str
    force_refresh: bool = False  # Set to True to bypass cache

@router.post("/ingest", response_model=TariffResponse)
async def ingest_tariff(request: TariffRequest):
    """
    Ingest a Freight Tariff PDF URL, extract data, and return structured JSON.
    """
    try:
        # 1. Download PDF
        pdf_content = pdf_service.download_pdf(request.url)
        
        # 2. Extract Text
        text_content = pdf_service.extract_text_from_pdf(pdf_content)
        
        # 3. Parse with AI
        # Note: This requires GEMINI_API_KEY to be set
        parsed_data = ai_service.parse_tariff_data(text_content, request.zone)
        
        return parsed_data
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/extract_full")
async def extract_full_tariff(request: SimpleRequest):
    """
    Extract complete tariff data with database caching.
    Uses chunked extraction to avoid token limits.
    """
    try:
        # Check cache first (unless force_refresh is True)
        if not request.force_refresh:
            cached_data = db_service.get_cached_data(request.url, max_age_days=30)
            if cached_data:
                return {
                    "status": "success",
                    "source": "cache",
                    "data": cached_data,
                    "message": "Data loaded from cache (less than 30 days old)"
                }
        
        # Download and extract PDF
        pdf_content = pdf_service.download_pdf(request.url)
        text_content = pdf_service.extract_text_from_pdf(pdf_content)
        
        # Try AI extraction first, fall back to manual if quota exhausted
        try:
            extracted_data = ai_service_simple.extract_full_tariff_chunked(text_content)
            extraction_method = "AI"
        except Exception as e:
            # If AI fails (quota exhausted), use manual extraction
            if "429" in str(e) or "quota" in str(e).lower():
                print("AI quota exhausted, using manual extraction...")
                from app.services import manual_extractor
                extracted_data = manual_extractor.extract_full_tariff_manual(text_content)
                extraction_method = "Manual (AI quota exhausted)"
            else:
                raise e
        
        # Save to database
        db_service.save_to_database(request.url, extracted_data)
        
        # Export to JSON file
        json_file = db_service.export_to_json('ups_data.json')
        
        return {
            "status": "success",
            "source": "fresh_extraction",
            "extraction_method": extraction_method,
            "data": extracted_data,
            "json_file": json_file,
            "message": f"Data extracted successfully using {extraction_method}"
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download_json")
async def download_json():
    """Download the ups_data.json file"""
    try:
        return FileResponse(
            'ups_data.json',
            media_type='application/json',
            filename='ups_data.json'
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="JSON file not found. Please run /extract_full first.")
