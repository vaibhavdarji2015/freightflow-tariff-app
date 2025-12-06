import os
import json
import google.generativeai as genai
from fastapi import HTTPException
from dotenv import load_dotenv
import time

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

def extract_countries_only(text: str) -> list:
    """Extract all countries in batches by letter (kept for backward compatibility)"""
    # This function is now replaced by parallel extraction in extract_full_tariff_chunked
    # but kept for potential future use
    print("Extracting countries in batches...")
    all_countries = []
    
    batches = ["A-C", "D-F", "G-I", "J-L", "M-O", "P-R", "S-U", "V-Z"]
    
    for batch in batches:
        print(f"  - Extracting countries {batch}...")
        countries = extract_countries_batch(text, batch)
        all_countries.extend(countries)
    
    print(f"Total countries extracted: {len(all_countries)}")
    return all_countries

def extract_service_prices(text: str, service: str) -> dict:
    """Extract prices for a single service"""
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
    import re
    envelope_data = None
    
    # Look for envelope row in the text near the service name
    service_section = text.find(service_name)
    if service_section != -1:
        # Get text around the service section (next 2000 chars)
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
    
    CRITICAL: Look for the section titled "{service_name}" or similar in the SENDING RATES section.
    
    Return JSON with this structure:
    {{
        "envelopes": [
            {{
                "weight": "Envelope",
                "zones": {{
                    "zone_1": 3295,
                    "zone_2": 3448,
                    "zone_3": 4125,
                    "zone_4": 3861,
                    "zone_5": 3955,
                    "zone_6": 4552,
                    "zone_7": 4783,
                    "zone_8": 5578,
                    "zone_9": 3890
                }}
            }}
        ],
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
            }},
            {{
                "weight": "21-44 kg",
                "pricing_type": "per_kg",
                "zones": {{
                    "zone_1": 835,
                    "zone_2": 855,
                    "zone_3": 1208,
                    "zone_4": 1225,
                    "zone_5": 1303,
                    "zone_6": 1463,
                    "zone_7": 1572,
                    "zone_8": 1758,
                    "zone_9": 1237
                }}
            }}
        ]
    }}
    
    CRITICAL RULES:
    1. Find the rate table for "{service_name}" in the SENDING RATES section (pages 12-15)
    2. ENVELOPES: Look for a row labeled "Envelopes" or "Envelope" at the TOP of the rate table (before Documents section)
       - This is a SINGLE row with 9 zone prices
       - Weight should be "Envelope" or "Envelopes"
       - Extract ALL 9 zone prices for this row
       - If no envelope row exists, return empty array []
    3. Extract DOCUMENTS section: ALL weights from 0.5 kg to 20 kg (should be ~40 rows)
    4. Extract NON-DOCUMENTS section: ALL weights from 1 kg to 20 kg, PLUS weight ranges like "21-44 kg", "45-69 kg", "70 kg" (should be ~45 rows total)
    5. For weight ranges like "21-44 kg", add "pricing_type": "per_kg"
    6. Each row must have ALL 9 zones (zone_1 through zone_9)
    7. Keep prices as integers (no commas, remove any commas from numbers)
    8. If you cannot find the rate table for this service, return empty arrays for all sections
    
    IMPORTANT: The table structure typically looks like:
    Zone        1      2      3      4      5      6      7      8      9
    Envelopes  3489   3657   4373   4092   4187   4823   5071   5913   4121
    Documents
    0.5 kg     3489   3657   4373   4092   4187   4823   5071   5913   4121
    ...
    
    Make sure to extract the Envelopes row if it exists!
    
    Text (full PDF text to ensure all rate tables are included):
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
            
            # If AI didn't find envelopes but we found them via regex, add them
            if envelope_data and (not result.get('envelopes') or len(result.get('envelopes', [])) == 0):
                result['envelopes'] = [envelope_data]
                print(f"    Added regex-extracted envelope data for {service}")
            
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
    
    Return JSON with this structure:
    {{
        "envelopes": [
            {{
                "weight": "Envelope",
                "zones": {{
                    "zone_1": 3295,
                    "zone_2": 3448,
                    "zone_3": 4125,
                    "zone_4": 3861,
                    "zone_5": 3955,
                    "zone_6": 4552,
                    "zone_7": 4783,
                    "zone_8": 5578,
                    "zone_9": 3890
                }}
            }}
        ],
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
            }},
            {{
                "weight": "21-44 kg",
                "pricing_type": "per_kg",
                "zones": {{
                    "zone_1": 835,
                    "zone_2": 855,
                    "zone_3": 1208,
                    "zone_4": 1225,
                    "zone_5": 1303,
                    "zone_6": 1463,
                    "zone_7": 1572,
                    "zone_8": 1758,
                    "zone_9": 1237
                }}
            }}
        ]
    }}
    
    CRITICAL RULES:
    1. Find the rate table for "{service_name}" in the SENDING RATES section (pages 12-15)
    2. ENVELOPES: Look for a row labeled "Envelopes" or "Envelope" at the TOP of the rate table (before Documents section)
       - This is a SINGLE row with 9 zone prices
       - Weight should be "Envelope" or "Envelopes"
       - Extract ALL 9 zone prices for this row
       - If no envelope row exists, return empty array []
    3. Extract DOCUMENTS section: ALL weights from 0.5 kg to 20 kg (should be ~40 rows)
    4. Extract NON-DOCUMENTS section: ALL weights from 1 kg to 20 kg, PLUS weight ranges like "21-44 kg", "45-69 kg", "70 kg" (should be ~45 rows total)
    5. For weight ranges like "21-44 kg", add "pricing_type": "per_kg"
    6. Each row must have ALL 9 zones (zone_1 through zone_9)
    7. Keep prices as integers (no commas, remove any commas from numbers)
    8. If you cannot find the rate table for this service, return empty arrays for all sections
    
    IMPORTANT: The table structure typically looks like:
    Zone        1      2      3      4      5      6      7      8      9
    Envelopes  3489   3657   4373   4092   4187   4823   5071   5913   4121
    Documents
    0.5 kg     3489   3657   4373   4092   4187   4823   5071   5913   4121
    ...
    
    Make sure to extract the Envelopes row if it exists!
    
    Text (full PDF text to ensure all rate tables are included):
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
            # Return empty structure on error
            return {"envelopes": [], "documents": [], "non_documents": []}

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
