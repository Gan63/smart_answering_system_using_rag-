import uuid
import fitz
import os
from database.chroma_client import get_text_collection, get_image_collection
from models.embedding_model import embed_text, embed_image



def extract_text_and_images_from_pdf(pdf_path):
    text = ""
    image_paths = []
    
    # Create a directory to store extracted images
    image_output_dir = "data/extracted_images"
    os.makedirs(image_output_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    
    for page_num, page in enumerate(doc):
        text += page.get_text()
        
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            
            # Save the image
            image_filename = f"image_{page_num}_{img_index}.png"
            image_path = os.path.join(image_output_dir, image_filename)
            with open(image_path, "wb") as image_file:
                image_file.write(image_bytes)
            image_paths.append(image_path)
            
    return text, image_paths


# split text into chunks
def chunk_text(text, chunk_size=500):

    words = text.split()

    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks


def ingest_pdf(pdf_path):
    text, image_paths = extract_text_and_images_from_pdf(pdf_path)
    
    # Ingest text chunks
    chunks = chunk_text(text)
    text_collection = get_text_collection()
    for chunk in chunks:
        embedding = embed_text(chunk)
        text_collection.add(
            ids=[str(uuid.uuid4())],
            embeddings=[embedding],
            documents=[chunk]
        )
    print("Text chunks stored in ChromaDB")
    
    # Ingest images
    image_collection = get_image_collection()
    for image_path in image_paths:
        embedding = embed_image(image_path)
        image_collection.add(
            ids=[str(uuid.uuid4())],
            embeddings=[embedding],
            documents=[image_path]
        )
    print("Images stored in ChromaDB")