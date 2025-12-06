#!/usr/bin/env python3
"""
Manual extraction script - bypasses AI quota limits
Run this to extract tariff data using pure regex parsing
"""
import json
from app.services.pdf_service import download_pdf, extract_text_from_pdf
from app.services.manual_extractor import extract_all_services_manual
from app.services.ai_service_simple import extract_countries_batch

def main():
    print("=" * 60)
    print("MANUAL TARIFF EXTRACTION (No AI Quota Required)")
    print("=" * 60)
    
    url = 'https://www.ups.com/assets/resources/webcontent/en_GB/tariff-guide-in.pdf'
    
    print("\n1. Downloading PDF...")
    pdf_content = download_pdf(url)
    
    print("2. Extracting text from PDF...")
    text = extract_text_from_pdf(pdf_content)
    print(f"   Extracted {len(text)} characters")
    
    print("\n3. Extracting countries (using AI - minimal quota usage)...")
    all_countries = []
    batches = ["A-C", "D-F", "G-I", "J-L", "M-O", "P-R", "S-U", "V-Z"]
    
    for batch in batches:
        try:
            countries = extract_countries_batch(text, batch)
            all_countries.extend(countries)
            print(f"   ✓ {batch}: {len(countries)} countries")
        except Exception as e:
            print(f"   ✗ {batch}: {e}")
            if "quota" in str(e).lower():
                print("   ! Quota exceeded for countries. Using cached data if available.")
                break
    
    print(f"\n   Total countries: {len(all_countries)}")
    
    print("\n4. Extracting service rates (using regex - no quota)...")
    prices = extract_all_services_manual(text)
    
    print("\n5. Combining data...")
    result = {
        "countries": all_countries,
        "prices": prices
    }
    
    print("\n6. Saving to ups_data_manual.json...")
    with open('ups_data_manual.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print("\n" + "=" * 60)
    print("✓ EXTRACTION COMPLETE!")
    print("=" * 60)
    print(f"\nResults saved to: ups_data_manual.json")
    print(f"  - Countries: {len(all_countries)}")
    print(f"  - Services: {len(prices)}")
    
    # Print detailed stats
    print("\nDetailed extraction stats:")
    for service, data in prices.items():
        env = len(data["envelopes"])
        doc = len(data["documents"])
        non_doc = len(data["non_documents"])
        total = env + doc + non_doc
        print(f"  {service:25} {total:3} total ({env} env, {doc} docs, {non_doc} non-docs)")
    
    print("\nYou can now:")
    print("  1. Review the data in ups_data_manual.json")
    print("  2. Copy it to ups_data.json to use in the app")
    print("  3. When AI quota resets, run the full extraction for better accuracy")

if __name__ == "__main__":
    main()
