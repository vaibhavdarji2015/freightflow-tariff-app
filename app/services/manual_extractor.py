"""
Manual extraction of UPS tariff data using regex patterns.
This bypasses AI quota limits by using direct text parsing.
"""
import re
from typing import Dict, List, Any

def extract_rate_table(text: str, service_name: str, start_marker: str, has_envelope: bool = True) -> Dict[str, Any]:
    """Extract rates for a service using regex patterns"""
    
    # Find the rate table section
    section_start = text.find(start_marker)
    if section_start == -1:
        print(f"  ✗ Could not find rate table for {service_name}")
        return {"envelopes": [], "documents": [], "non_documents": []}
    
    # Get section (next 20000 chars to capture full table)
    section = text[section_start:section_start+20000]
    
    result = {
        "envelopes": [],
        "documents": [],
        "non_documents": []
    }
    
    # Determine if this is a 9-zone or 10-zone table
    zone_header = re.search(r'Zone\s+1\s+2\s+3\s+4\s+5\s+6\s+7\s+8\s+9(?:\s+10)?', section)
    num_zones = 10 if (zone_header and '10' in zone_header.group()) else 9
    print(f"  {service_name}: {num_zones} zones detected")
    
    # Extract envelope row (only if service has envelopes)
    if has_envelope:
        if num_zones == 9:
            envelope_pattern = r'Envelopes?\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
        else:
            envelope_pattern = r'Envelopes?\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
        
        env_match = re.search(envelope_pattern, section)
        if env_match:
            prices = [int(env_match.group(i).replace(',', '')) for i in range(1, num_zones + 1)]
            zones_dict = {f"zone_{i}": prices[i-1] for i in range(1, num_zones + 1)}
            result["envelopes"] = [{
                "weight": "Envelope",
                "zones": zones_dict
            }]
    
    # Pattern for weight rows - handles both 9 and 10 zones
    if num_zones == 9:
        weight_pattern = r'([\d.]+)\s*kg\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
    else:
        weight_pattern = r'([\d.]+)\s*kg\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
    
    # Find Documents section
    doc_section_start = section.find('Documents')
    non_doc_section_start = section.find('Non-Documents')
    
    if doc_section_start != -1:
        # Extract from Documents section until Non-Documents
        if non_doc_section_start != -1:
            doc_text = section[doc_section_start:non_doc_section_start]
        else:
            doc_text = section[doc_section_start:doc_section_start+8000]
        
        for match in re.finditer(weight_pattern, doc_text):
            weight = match.group(1)
            prices = [int(match.group(i).replace(',', '')) for i in range(2, num_zones + 2)]
            zones_dict = {f"zone_{i}": prices[i-1] for i in range(1, num_zones + 1)}
            result["documents"].append({
                "weight": f"{weight} kg",
                "zones": zones_dict
            })
    
    # Extract non-document rates
    if non_doc_section_start != -1:
        non_doc_text = section[non_doc_section_start:non_doc_section_start+12000]
        
        # First, extract weight ranges to know which individual weights to skip
        weight_ranges = []
        if num_zones == 9:
            range_pattern = r'([\d]+)\s*-\s*([\d]+)\s*kg\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
        else:
            range_pattern = r'([\d]+)\s*-\s*([\d]+)\s*kg\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
        
        for match in re.finditer(range_pattern, non_doc_text):
            weight_start = match.group(1)
            weight_end = match.group(2)
            prices = [int(match.group(i).replace(',', '')) for i in range(3, num_zones + 3)]
            zones_dict = {f"zone_{i}": prices[i-1] for i in range(1, num_zones + 1)}
            weight_ranges.append({
                "weight": f"{weight_start}-{weight_end} kg",
                "pricing_type": "per_kg",
                "zones": zones_dict,
                "start_val": int(weight_start),
                "end_val": int(weight_end)
            })
        
        # Pattern for single weights (e.g., "1.0 kg")
        # Skip weights that are endpoints of ranges
        range_endpoints = set()
        for wr in weight_ranges:
            range_endpoints.add(wr["end_val"])
        
        for match in re.finditer(weight_pattern, non_doc_text):
            weight = match.group(1)
            weight_val = float(weight)
            
            # Skip if this weight is an endpoint of a range
            if int(weight_val) in range_endpoints:
                continue
            
            prices = [int(match.group(i).replace(',', '')) for i in range(2, num_zones + 2)]
            zones_dict = {f"zone_{i}": prices[i-1] for i in range(1, num_zones + 1)}
            
            entry = {
                "weight": f"{weight} kg",
                "zones": zones_dict,
                "weight_val": weight_val
            }
            # Individual weights >= 21 are typically per_kg in the "For shipment weight above 20 kg" section
            # But we should skip these if we have ranges covering them
            if weight_val <= 20:
                result["non_documents"].append(entry)
        
        # Add weight ranges
        for wr in weight_ranges:
            wr.pop("start_val")  # Remove sorting helper
            wr.pop("end_val")
            result["non_documents"].append(wr)
        
        # Look for "Above 1000 kg" or similar
        above_match = re.search(r'Above\s+(\d+)\s*kg', non_doc_text)
        if above_match:
            weight_val = above_match.group(1)
            # Find the prices on the same line
            line_start = non_doc_text.find(above_match.group(0))
            line_end = non_doc_text.find('\n', line_start)
            if line_end == -1:
                line_end = len(non_doc_text)
            line = non_doc_text[line_start:line_end]
            
            price_matches = re.findall(r'([\d,]+)', line)
            if len(price_matches) >= num_zones:
                prices = [int(price_matches[i].replace(',', '')) for i in range(len(price_matches) - num_zones, len(price_matches))]
                if len(prices) == num_zones:
                    zones_dict = {f"zone_{i}": prices[i-1] for i in range(1, num_zones + 1)}
                    result["non_documents"].append({
                        "weight": f"Above {weight_val} kg",
                        "pricing_type": "per_kg",
                        "zones": zones_dict,
                        "weight_val": float(weight_val) + 1  # For sorting
                    })
    
    # Sort non-documents by weight value and deduplicate
    def get_sort_key(item):
        weight_str = item["weight"]
        # Extract numeric value for sorting
        if "-" in weight_str:
            # Range like "21-44 kg"
            return float(weight_str.split("-")[0])
        elif "Above" in weight_str:
            return 10000  # Put "Above X kg" at the end
        else:
            # Single weight like "1.5 kg"
            return float(weight_str.replace(" kg", ""))
    
    result["non_documents"].sort(key=get_sort_key)
    
    # Deduplicate non-documents by normalized weight (keep first occurrence)
    def normalize_weight(weight_str):
        """Normalize weight string for comparison (e.g., '1.0 kg' -> '1 kg')"""
        if "-" in weight_str or "Above" in weight_str:
            return weight_str  # Keep ranges and "Above X kg" as-is
        # Remove " kg", convert to float, then back to minimal string
        try:
            val = float(weight_str.replace(" kg", ""))
            # Format without unnecessary decimals (1.0 -> 1, 1.5 -> 1.5)
            if val == int(val):
                return f"{int(val)} kg"
            else:
                return f"{val} kg"
        except:
            return weight_str
    
    seen_weights = set()
    deduplicated_non_docs = []
    for item in result["non_documents"]:
        normalized = normalize_weight(item["weight"])
        if normalized not in seen_weights:
            seen_weights.add(normalized)
            # Remove sorting helper if present
            if "weight_val" in item:
                item.pop("weight_val")
            # Update weight to normalized form
            item["weight"] = normalized
            deduplicated_non_docs.append(item)
    result["non_documents"] = deduplicated_non_docs
    
    return result

def extract_freight_rates(text: str, service_name: str, start_marker: str) -> Dict[str, Any]:
    """Extract freight service rates (no documents/envelopes, only weight-based pricing)"""
    
    section_start = text.find(start_marker)
    if section_start == -1:
        print(f"  ✗ Could not find rate table for {service_name}")
        return {"envelopes": [], "documents": [], "non_documents": []}
    
    # Find the end of this service's section (next service or end of text)
    # Look for the next "UPS Worldwide" service marker
    next_service_start = text.find("UPS Worldwide", section_start + len(start_marker))
    if next_service_start != -1:
        section = text[section_start:next_service_start]
    else:
        section = text[section_start:section_start+3000]
    
    result = {
        "envelopes": [],
        "documents": [],
        "non_documents": []
    }
    
    # Freight services have: Min rate, then weight ranges
    # Format in PDF:
    # Min rate 55,309 61,060 ...
    # 71 - 99 kg
    # Price per kg 779 860 ...
    
    # Min rate pattern (all on one line)
    min_rate_pattern = r'Min\s+rate\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
    min_match = re.search(min_rate_pattern, section)
    if min_match:
        prices = [int(min_match.group(i).replace(',', '')) for i in range(1, 10)]
        result["non_documents"].append({
            "weight": "Min rate",
            "pricing_type": "per_kg",
            "zones": {f"zone_{i}": prices[i-1] for i in range(1, 10)}
        })
    
    # Weight ranges - they appear on separate lines:
    # "71 - 99 kg" on one line
    # "Price per kg 779 860 ..." on the next line
    
    # Find all weight range headers
    weight_range_pattern = r'([\d]+)\s*-\s*([\d]+)\s*kg'
    price_per_kg_pattern = r'Price\s+per\s+kg\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
    
    # Split section into lines
    lines = section.split('\n')
    
    for i, line in enumerate(lines):
        # Check if this line has a weight range
        range_match = re.search(weight_range_pattern, line)
        if range_match:
            weight_start = range_match.group(1)
            weight_end = range_match.group(2)
            
            # Look for "Price per kg" in the next few lines
            for j in range(i+1, min(i+3, len(lines))):
                price_match = re.search(price_per_kg_pattern, lines[j])
                if price_match:
                    prices = [int(price_match.group(k).replace(',', '')) for k in range(1, 10)]
                    result["non_documents"].append({
                        "weight": f"{weight_start}-{weight_end} kg",
                        "pricing_type": "per_kg",
                        "zones": {f"zone_{i}": prices[i-1] for i in range(1, 10)}
                    })
                    break
    
    # "1000 kg or more" pattern (also multi-line)
    for i, line in enumerate(lines):
        if re.search(r'(\d+)\s*kg\s+or\s+more', line):
            weight_match = re.search(r'(\d+)\s*kg\s+or\s+more', line)
            weight = weight_match.group(1)
            
            # Look for "Price per kg" in the next few lines
            for j in range(i+1, min(i+3, len(lines))):
                price_match = re.search(price_per_kg_pattern, lines[j])
                if price_match:
                    prices = [int(price_match.group(k).replace(',', '')) for k in range(1, 10)]
                    result["non_documents"].append({
                        "weight": f"{weight} kg or more",
                        "pricing_type": "per_kg",
                        "zones": {f"zone_{i}": prices[i-1] for i in range(1, 10)}
                    })
                    break
    
    return result

    """Extract freight service rates (no documents/envelopes, only weight-based pricing)"""
    
    section_start = text.find(start_marker)
    if section_start == -1:
        print(f"  ✗ Could not find rate table for {service_name}")
        return {"envelopes": [], "documents": [], "non_documents": []}
    
    section = text[section_start:section_start+3000]
    
    result = {
        "envelopes": [],
        "documents": [],
        "non_documents": []
    }
    
    # Freight services have: Min rate, then weight ranges
    # Pattern: "71 - 99 kg" or "100 - 299 kg" followed by 9 prices
    
    # Min rate pattern
    min_rate_pattern = r'Min\s+rate\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
    min_match = re.search(min_rate_pattern, section)
    if min_match:
        prices = [int(min_match.group(i).replace(',', '')) for i in range(1, 10)]
        result["non_documents"].append({
            "weight": "Min rate",
            "pricing_type": "per_kg",
            "zones": {f"zone_{i}": prices[i-1] for i in range(1, 10)}
        })
    
    # Weight range pattern
    range_pattern = r'([\d]+)\s*-\s*([\d]+)\s*kg\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
    for match in re.finditer(range_pattern, section):
        weight_start = match.group(1)
        weight_end = match.group(2)
        prices = [int(match.group(i).replace(',', '')) for i in range(3, 12)]
        result["non_documents"].append({
            "weight": f"{weight_start}-{weight_end} kg",
            "pricing_type": "per_kg",
            "zones": {f"zone_{i}": prices[i-1] for i in range(1, 10)}
        })
    
    # "1000 kg or more" pattern
    kg_or_more_pattern = r'([\d]+)\s*kg\s+or\s+more\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
    match = re.search(kg_or_more_pattern, section)
    if match:
        weight = match.group(1)
        prices = [int(match.group(i).replace(',', '')) for i in range(2, 11)]
        result["non_documents"].append({
            "weight": f"{weight} kg or more",
            "pricing_type": "per_kg",
            "zones": {f"zone_{i}": prices[i-1] for i in range(1, 10)}
        })
    
    return result

def extract_all_services_manual(text: str) -> Dict[str, Any]:
    """Extract all services using manual regex patterns"""
    
    print("Starting manual extraction (no AI quota needed)...")
    
    services = {
        "express": extract_rate_table(
            text, 
            "Express", 
            "Export - UPS Worldwide Express® and UPS Worldwide Express Plus®",
            has_envelope=True
        ),
        "express_plus": extract_rate_table(
            text,
            "Express Plus",
            "Export - UPS Worldwide Express® and UPS Worldwide Express Plus®",
            has_envelope=True
        ),
        "express_saver": extract_rate_table(
            text,
            "Express Saver",
            "Export - UPS Worldwide Express Saver™",
            has_envelope=True
        ),
        "expedited": extract_rate_table(
            text,
            "Expedited",
            "UPS Worldwide Expedited®",
            has_envelope=False  # Expedited has NO envelopes
        ),
        "express_freight": extract_freight_rates(
            text,
            "Express Freight",
            "Export - UPS Worldwide Express Freight™"
        ),
        "express_freight_midday": extract_freight_rates(
            text,
            "Express Freight Midday",
            "Export - UPS Worldwide Express Freight™ Midday"
        )
    }
    
    # Print summary
    print("\nExtraction summary:")
    for service, data in services.items():
        env = len(data["envelopes"])
        doc = len(data["documents"])
        non_doc = len(data["non_documents"])
        print(f"  {service}: {env} env, {doc} docs, {non_doc} non-docs")
    
    return services
