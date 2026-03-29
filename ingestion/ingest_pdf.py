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
            
            # Store with caption info
            image_paths.append({
                "path": image_path,
                "page": page_num,
                "index": img_index
            })
    doc.close()
    return {"text": text, "images": image_paths}

def chunk_text(text, chunk_size=300):
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

    result = extract_text_and_images_from_pdf(pdf_path)
    text = result["text"]
    image_info_list = result["images"]
    source_name = os.path.basename(pdf_path)
    
    text_collection = get_text_collection()
    image_collection = get_image_collection()
    
    # Ingest text chunks
    text_chunks = chunk_text(text)
    if text_chunks:
        ids = [str(uuid.uuid4()) for _ in text_chunks]
        embeddings = []
        for chunk in text_chunks:
            try:
                embeddings.append(embed_text(chunk))
            except Exception as e:
                print(f"Text embedding failed for chunk: {str(e)[:100]}")
        if not embeddings:
            print("No text embeddings generated")
            return
        metadatas = [{"source": source_name, "session_id": session_id} for _ in text_chunks]
        text_collection.add(ids=ids, embeddings=embeddings, documents=text_chunks, metadatas=metadatas)
        print(f"[+] Ingested {len(text_chunks)} text chunks for session {session_id}")
    # Ingest images with captions
    if image_info_list:
        ids = [str(uuid.uuid4()) for _ in image_info_list]
        embeddings = []
        for info in image_info_list:
            try:
                embeddings.append(embed_image(info["path"]))
            except Exception as e:
                print(f"Image embedding failed for {info['path']}: {str(e)[:100]}")
        if not embeddings:
            print("No image embeddings generated")
        documents = []
        metadatas = []
        for info in image_info_list:
            caption = f"Figure from page {info['page'] + 1} in {source_name}"
            doc_str = f"{info['path']} | {caption}"
            documents.append(doc_str)
            metadatas.append({
                "source": source_name, 
                "session_id": session_id,
                "page": info['page'],
                "caption": caption
            })
        if embeddings:
            image_collection.add(ids=ids, embeddings=embeddings, documents=[d.replace("\\", "/") for d in documents], metadatas=metadatas)
            print(f"[+] Ingested {len(image_info_list)} images for session {session_id}")
    
    from session_store import session_store
    session_store.update_stats(session_id)
    print("[+] Updated session stats from Chroma")
