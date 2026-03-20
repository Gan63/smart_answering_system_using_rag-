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

def chunk_text(text, chunk_size=500):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def ingest_pdf(pdf_path: str, session_id: str):
    """
    Extracts text and images from a PDF, chunks them, generates embeddings,
    and stores them in ChromaDB with a session_id.
    """
    if not session_id:
        raise ValueError("A session_id is required for ingestion.")

    text, image_paths = extract_text_and_images_from_pdf(pdf_path)
    source_name = os.path.basename(pdf_path)
    
    # Ingest text chunks
    text_chunks = chunk_text(text)
    text_collection = get_text_collection()
    if text_chunks:
        ids = [str(uuid.uuid4()) for _ in text_chunks]
        embeddings = [embed_text(chunk) for chunk in text_chunks]
        metadatas = [{"source": source_name, "session_id": session_id} for _ in text_chunks]
        text_collection.add(ids=ids, embeddings=embeddings, documents=text_chunks, metadatas=metadatas)
        print(f"DEBUG INGEST PDF - texts: {len(text_chunks)} session {session_id}")
        text_collection.add(ids=ids, embeddings=embeddings, documents=text_chunks, metadatas=metadatas)

    # Ingest images
    image_collection = get_image_collection()
    if image_paths:
        ids = [str(uuid.uuid4()) for _ in image_paths]
        embeddings = [embed_image(path) for path in image_paths]
        metadatas = [{"source": source_name, "session_id": session_id} for _ in image_paths]
        image_collection.add(ids=ids, embeddings=embeddings, documents=image_paths, metadatas=metadatas)
        print(f"DEBUG INGEST PDF - images: {len(image_paths)} session {session_id}")
