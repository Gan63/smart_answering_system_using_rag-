import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from config import CHROMA_PATH, TEXT_MODEL_NAME


def get_chroma_client():

    client = chromadb.Client(
        Settings(
            persist_directory=CHROMA_PATH,
            is_persistent=True,
        )
    )

    return client


def get_text_collection():

    client = get_chroma_client()

    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=TEXT_MODEL_NAME
    )

    collection = client.get_or_create_collection(
        name="text_collection", embedding_function=embedding_function
    )

    return collection


def get_image_collection():

    client = get_chroma_client()

    collection = client.get_or_create_collection(name="image_collection")

    return collection