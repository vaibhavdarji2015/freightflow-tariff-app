import os
import json
import google.generativeai as genai
from fastapi import HTTPException
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def parse_tariff_data(text: str, zone: Optional[str] = None) -> dict:
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    model = genai.GenerativeModel('gemini-2.0-flash')

    # Determine which zones to extract rates for
    if zone and zone != "all":
        rate_zone_instruction = f"""For zone_rates, extract rates for ALL services for Zone {zone} ONLY:
        - "Express Plus"
        - "Express"
        - "Express Saver"
        - "Expedited"
        Extract ALL weight ranges (0.5kg to 20kg), both Documents and Non-Documents for each service."""
    else:
        rate_zone_instruction = 'For zone_rates, extract rates for "Express" service ONLY, zones 1-3, weights 0.5kg-5.0kg (to keep response manageable)'
    
    zone_instruction = ""
    if zone and zone != "all":
        zone_instruction = f"IMPORTANT: Extract ONLY countries that have Export Zone = {zone} OR Import Zone = {zone} for ANY service. Skip all other countries."
    else:
        zone_instruction = "Extract FIRST 10 countries from Zone Table (to keep response size manageable)."
    
    prompt = f"""
    Extract data from UPS Tariff PDF.
    
    Return JSON with this EXACT structure:
    {{
        "provider": "UPS",
        "countries": [
            {{
                "country_name": "Afghanistan",
                "country_code": "AF",
                "service_zones": [
                    {{
                        "service_name": "Express Plus",
                        "export_zone": "8",
                        "import_zone": "9"
                    }},
                    {{
                        "service_name": "Express",
                        "export_zone": "8",
                        "import_zone": "9"
                    }},
                    {{
                        "service_name": "Express Saver",
                        "export_zone": "9",
                        "import_zone": null
                    }},
                    {{
                        "service_name": "Expedited",
                        "export_zone": "9",
                        "import_zone": null
                    }},
                    {{
                        "service_name": "Express Freight",
                        "export_zone": null,
                        "import_zone": "9"
                    }},
                    {{
                        "service_name": "Express Freight Midday",
                        "export_zone": null,
                        "import_zone": "9"
                    }}
                ]
            }}
        ],
        "zone_rates": {{
            "Express Plus": [
                {{
                    "zone_id": "1",
                    "rates": [
                        {{
                            "weight": "0.5 kg",
                            "price": 3489.0,
                            "currency": "INR",
                            "item_type": "Documents"
                        }}
                    ]
                }}
            ],
            "Express": [
                {{
                    "zone_id": "1",
                    "rates": [
                        {{
                            "weight": "0.5 kg",
                            "price": 3489.0,
                            "currency": "INR",
                            "item_type": "Documents"
                        }}
                    ]
                }}
            ],
            "Express Saver": [
                {{
                    "zone_id": "1",
                    "rates": [
                        {{
                            "weight": "0.5 kg",
                            "price": 3295.0,
                            "currency": "INR",
                            "item_type": "Documents"
                        }}
                    ]
                }}
            ],
            "Expedited": [
                {{
                    "zone_id": "1",
                    "rates": [
                        {{
                            "weight": "0.5 kg",
                            "price": 2500.0,
                            "currency": "INR",
                            "item_type": "Documents"
                        }}
                    ]
                }}
            ]
        }}
    }}
    
    Rules:
    1. {zone_instruction}
    2. For service_zones, extract ALL 6 services from the Zone Table:
       - "Express Plus" (UPS Worldwide Express Plus)
       - "Express" (UPS Worldwide Express)
       - "Express Saver" (UPS Worldwide Express Saver)
       - "Expedited" (UPS Worldwide Expedited)
       - "Express Freight" (UPS Worldwide Express Freight)
       - "Express Freight Midday" (UPS Worldwide Express Freight Midday)
    3. Use shortened service names to save tokens
    4. If a service doesn't have a zone number for a country, use null
    5. {rate_zone_instruction}
    6. Separate Documents and Non-Documents with item_type field
    7. Skip Express Freight services for zone_rates (focus on Express Plus, Express, Express Saver, Expedited)
    
    Text:
    {text[:40000]}
    """


    import time

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
            # Clean up response if it contains markdown code blocks (though JSON mode usually avoids this)
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                print(f"429 Error (Resource Exhausted). Retrying in 5 seconds... (Attempt {attempt + 1}/{retries})")
                time.sleep(5)
                continue
            print(f"AI Parsing Error: {e}")
            raise HTTPException(status_code=500, detail=f"AI Parsing failed: {str(e)}")
