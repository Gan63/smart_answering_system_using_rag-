import os
from database.chroma_client import get_text_collection, get_image_collection
from ingestion.ingest_pdf import ingest_pdf
from ingestion.ingest_docx import ingest_docx
from ingestion.ingest_image import ingest_image

# Test session
session_id = "test_session"

# Test files exist?
pdf_files = [f for f in os.listdir('data/') if f.endswith('.pdf')]
docx_files = [f for f in os.listdir('data/') if f.endswith('.docx')]
image_files = [f for f in os.listdir('data/') if f.endswith(('.jpg', '.jpeg', '.png'))]
print(f"PDFs: {pdf_files}")
print(f"DOCXs: {docx_files}")
print(f"Images: {image_files}")

# Clear test data
get_text_collection().delete(where={"session_id": session_id})
get_image_collection().delete(where={"session_id": session_id})

print("[*] Testing PDF ingestion...")
if pdf_files:
    pdf_path = os.path.join('data', pdf_files[0])
    ingest_pdf(pdf_path, session_id)
else:
    print("No PDF for test")

print("[*] Testing DOCX ingestion...")
if docx_files:
    docx_path = os.path.join('data', docx_files[0])
    ingest_docx(docx_path, session_id)
else:
    print("No DOCX for test")

print("[*] Testing Image ingestion...")
if image_files:
    image_path = os.path.join('data', image_files[0])
    ingest_image(image_path, session_id)
else:
    print("No Image for test")

print("[*] Count data...")
text_count = len(get_text_collection().get(where={"session_id": session_id})['ids'])
image_count = len(get_image_collection().get(where={"session_id": session_id})['ids'])
print(f"[+] Text chunks: {text_count}, Images: {image_count}")

print("Test complete! Check logs for errors.")
