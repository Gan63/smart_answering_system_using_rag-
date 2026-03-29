import traceback
from ingestion.ingest_image import ingest_image
import os

try:
    image_files = [f for f in os.listdir('data/') if f.endswith(('.jpg', '.jpeg', '.png'))]
    if image_files:
        print(f"Testing {image_files[0]}")
        ingest_image(os.path.join('data', image_files[0]), 'test_session_img')
except Exception as e:
    traceback.print_exc()

from ingestion.ingest_pdf import ingest_pdf
try:
    pdf_files = [f for f in os.listdir('data/') if f.endswith('.pdf')]
    if pdf_files:
        print(f"Testing {pdf_files[0]}")
        ingest_pdf(os.path.join('data', pdf_files[0]), 'test_session_pdf')
except Exception as e:
    traceback.print_exc()
