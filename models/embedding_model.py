from PIL import Image
from config import TEXT_MODEL_NAME, CLIP_MODEL_NAME

# Lazy loading
text_model = None
clip_model = None
clip_processor = None

def get_text_model():
    global text_model
    if text_model is None:
        from sentence_transformers import SentenceTransformer
        text_model = SentenceTransformer(TEXT_MODEL_NAME)
    return text_model

def get_clip_model():
    global clip_model, clip_processor
    if clip_model is None:
        from transformers import CLIPProcessor, CLIPModel
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using CLIP device: {device}")
        clip_model = CLIPModel.from_pretrained(CLIP_MODEL_NAME).to(device)
        clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL_NAME)
    return clip_model, clip_processor

# Text embedding
def embed_text(text):
    model = get_text_model()
    embedding = model.encode(text)
    return embedding.tolist()


# CLIP text embedding
def embed_clip_text(text):
    model, processor = get_clip_model()
    import torch
    inputs = processor(text=[text], return_tensors="pt", padding=True)

    with torch.no_grad():
        text_features = model.get_text_features(**inputs)

    embedding = text_features.pooler_output.flatten().tolist()
    return embedding


# Image embedding
def embed_image(image_path):
    model, processor = get_clip_model()
    import torch
    image = Image.open(image_path).convert('RGB')

    inputs = processor(images=image, return_tensors="pt")

    with torch.no_grad():
        image_features = model.get_image_features(**inputs)

    # Flatten the embedding and convert to list
    embedding = image_features.pooler_output.flatten().tolist()

    return embedding
