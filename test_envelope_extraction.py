#!/usr/bin/env python3
"""Quick test to verify envelope extraction works"""
import re

# Sample text from the PDF
test_text = """
UPS Worldwide Express® and UPS Worldwide Express Plus®*
NEXT MORNING DELIVERY AND TIME-DEFINITE DELIVERY WORLDWIDE
Export - UPS Worldwide Express® and UPS Worldwide Express Plus®*
Zone 1 2 3 4 5 6 7 8 9
Envelopes 3,489 3,657 4,373 4,092 4,187 4,823 5,071 5,913 4,121
Documents
weight
0.5 kg 3,489 3,657 4,373 4,092 4,187 4,823 5,071 5,913 4,121
"""

# Test regex pattern
envelope_pattern = r'Envelopes?\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)'
match = re.search(envelope_pattern, test_text)

if match:
    prices = [int(match.group(i).replace(',', '')) for i in range(1, 10)]
    print("✓ Regex extraction works!")
    print(f"  Extracted prices: {prices}")
    print(f"  Zone 1: {prices[0]}, Zone 9: {prices[8]}")
else:
    print("✗ Regex pattern didn't match")
