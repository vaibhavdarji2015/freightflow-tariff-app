from app.services import pdf_service

url = "https://www.ups.com/assets/resources/webcontent/en_GB/tariff-guide-in.pdf"
print(f"Downloading PDF from {url}...")
pdf_content = pdf_service.download_pdf(url)

print("Extracting text...")
text = pdf_service.extract_text_from_pdf(pdf_content)

output_file = "debug_pdf_text.txt"
with open(output_file, "w") as f:
    f.write(text)

print(f"Text saved to {output_file}. Total characters: {len(text)}")
