import requests
import json

def test_ingest():
    url = "http://localhost:8000/api/v1/ingest"
    payload = {
        "url": "https://www.ups.com/assets/resources/webcontent/en_GB/tariff-guide-in.pdf"
    }
    
    print(f"Sending request to {url}...")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        print("Success! Received parsed data:")
        print(json.dumps(data, indent=2))
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ingest()
