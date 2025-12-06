import os
import json
import google.generativeai as genai
from fastapi import HTTPException
from dotenv import load_dotenv
import time
import re

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def extract_countries_batch(text: str, letter_range: str) -> list:
    """Extract countries starting with specific letters"""
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt = f"""
    Extract ONLY countries starting with letters {letter_range} from the UPS Zone Table.
    
    Return JSON array:
    [
        {{
            "name": "Afghanistan",
            "code": "AF",
            "export_zone": 8,
            "import_zone": 9
        }}
    ]
    
    Rules:
    1. Extract from Zone Table (pages 6-9)
    2. Use export_zone for "Express" service column
    3. Use import_zone for "Express" service column  
    4. If no zone number, use null
    5. ONLY include countries starting with {letter_range}
    
    Text:
    {text[:40000]}
    """

    retries = 3
    for attempt in range(retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    max_output_tokens=4096
                )
            )
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                print(f"429 Error. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            print(f"AI Parsing Error for {letter_range}: {e}")
            return []

def extract_service_prices(text: str, service: str) -> dict:
    """Extract prices for a single service with regex fallback for envelopes"""
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    model = genai.GenerativeModel('gemini-2.0-flash')

    service_map = {
        "expedited": "UPS Worldwide Expedited",
        "express": "UPS Worldwide Express",
        "express_saver": "UPS Worldwide Express Saver",
        "express_plus": "UPS Worldwide Express Plus",
        "express_freight": "UPS Worldwide Express Freight",
        "express_freight_midday": "UPS Worldwide Express Freight Midday"
    }
    
    service_name = service_map.get(service, service)
    
    # Try to extract envelope row manually using regex as fallback
    envelope_data = None
    
    # Freight services don't have envelope pricing, skip for them
    is_freight_service = 'freight' in service.lower()
    
    if not is_freight_service:
        # Look for envelope row in the RATE TABLE section (not service description)
        # Some services share rate tables, so we need multiple search patterns
        search_patterns = [
            f"Export - {service_name}",  # Standard pattern
            f"Export - UPS Worldwide Express® and UPS Worldwide Express Plus®",  # Shared table for Express/Express Plus
        ]
        
        service_section = -1
        for pattern in search_patterns:
            service_section = text.find(pattern)
            if service_section != -1:
                break
        
        if service_section != -1:
            # Get text around the rate table section (next 2000 chars)
            section_text = text[service_section:service_section+2000]
            
            # Look for "Envelopes" followed by numbers
            envelope_pattern = r'Envelopes?\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
            match = re.search(envelope_pattern, section_text)
            
            if match:
                # Extract the 9 zone prices
                prices = [int(match.group(i).replace(',', '')) for i in range(1, 10)]
                envelope_data = {
                    "weight": "Envelope",
                    "zones": {
                        f"zone_{i}": prices[i-1] for i in range(1, 10)
                    }
                }
                print(f"    Found envelope row for {service} via regex")

    prompt = f"""
    Extract ALL prices for "{service_name}" service from the rate tables.
    
    Return JSON with this structure:
    {{
        "envelopes": [],
        "documents": [
            {{
                "weight": "0.5 kg",
                "zones": {{
                    "zone_1": 4169,
                    "zone_2": 4360,
                    "zone_3": 5178,
                    "zone_4": 4784,
                    "zone_5": 4856,
                    "zone_6": 5933,
                    "zone_7": 6261,
                    "zone_8": 6705,
                    "zone_9": 4976
                }}
            }}
        ],
        "non_documents": [
            {{
                "weight": "1 kg",
                "zones": {{
                    "zone_1": 4169,
                    "zone_2": 4360,
                    "zone_3": 5178,
                    "zone_4": 4784,
                    "zone_5": 4856,
                    "zone_6": 5933,
                    "zone_7": 6261,
                    "zone_8": 6705,
                    "zone_9": 4976
                }}
            }}
        ]
    }}
    
    CRITICAL RULES:
    1. Find the rate table for "{service_name}" in the SENDING RATES section
    
    2. FOR FREIGHT SERVICES (Express Freight, Express Freight Midday):
       - These services do NOT have Documents/Non-Documents categories
       - Extract ALL weight ranges (Min rate, 71-99 kg, 100-299 kg, 300-499 kg, 500-999 kg, 1000 kg or more)
       - Put ALL rates in the "non_documents" array
       - Add "pricing_type": "per_kg" for all weight ranges
       - Leave "documents" and "envelopes" as empty arrays
       - Example weight format: "Min rate", "71-99 kg", "100-299 kg", etc.
    
    3. FOR NON-FREIGHT SERVICES (Express, Express Plus, Express Saver, Expedited):
       - Extract DOCUMENTS section: ALL weights from 0.5 kg to 20 kg
       - Extract NON-DOCUMENTS section: ALL weights from 1 kg to 20 kg, PLUS weight ranges
       - For weight ranges like "21-44 kg", add "pricing_type": "per_kg"
    
    4. Each row must have ALL 9 zones (zone_1 through zone_9)
    5. Keep prices as integers (no commas)
    6. Skip envelopes - they will be added separately
    
    Text (full PDF text):
    {text}
    """

    retries = 3
    for attempt in range(retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    max_output_tokens=8192
                )
            )
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            result = json.loads(cleaned_text)
            
            # Add regex-extracted envelope data
            if envelope_data:
                result['envelopes'] = [envelope_data]
                print(f"    Added regex-extracted envelope data for {service}")
            else:
                result['envelopes'] = result.get('envelopes', [])
            
            # Log extraction results
            env_count = len(result.get('envelopes', []))
            doc_count = len(result.get('documents', []))
            non_doc_count = len(result.get('non_documents', []))
            print(f"    {service}: {env_count} envelopes, {doc_count} docs, {non_doc_count} non-docs")
            
            return result
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                print(f"429 Error. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            print(f"AI Parsing Error for {service}: {e}")
            # Return structure with regex envelope data if available
            result = {"envelopes": [], "documents": [], "non_documents": []}
            if envelope_data:
                result['envelopes'] = [envelope_data]
            return result

def extract_full_tariff_chunked(text: str) -> dict:
    """Extract complete tariff data using chunked approach with parallel processing"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    print("Extracting countries in parallel...")
    all_countries = []
    
    # Extract countries in parallel
    batches = ["A-C", "D-F", "G-I", "J-L", "M-O", "P-R", "S-U", "V-Z"]
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all country batch jobs
        future_to_batch = {
            executor.submit(extract_countries_batch, text, batch): batch 
            for batch in batches
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            try:
                countries = future.result()
                all_countries.extend(countries)
                print(f"  ✓ Extracted countries {batch}: {len(countries)} countries")
            except Exception as e:
                print(f"  ✗ Error extracting {batch}: {e}")
    
    print(f"Total countries extracted: {len(all_countries)}")
    
    print("\nExtracting prices for all services in parallel...")
    prices = {}
    services = ["expedited", "express", "express_saver", "express_plus", "express_freight", "express_freight_midday"]
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all service jobs
        future_to_service = {
            executor.submit(extract_service_prices, text, service): service 
            for service in services
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_service):
            service = future_to_service[future]
            try:
                prices[service] = future.result()
                env_count = len(prices[service].get('envelopes', []))
                doc_count = len(prices[service].get('documents', []))
                non_doc_count = len(prices[service].get('non_documents', []))
                print(f"  ✓ {service}: {env_count} env, {doc_count} docs, {non_doc_count} non-docs")
            except Exception as e:
                print(f"  ✗ Error extracting {service}: {e}")
                prices[service] = {"envelopes": [], "documents": [], "non_documents": []}
    
    return {
        "countries": all_countries,
        "prices": prices
    }
