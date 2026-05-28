import chromadb
from config import settings

_client = None

def get_client():
    global _client
    if _client is None:
        _client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    return _client

def get_or_create_collection(name: str):
    client = get_client()
    try:
        return client.get_collection(name)
    except Exception:
        return client.create_collection(name)

def upsert_document(collection, doc_id: str, embedding, metadata: dict, document: str = None):
    collection.upsert(ids=[doc_id], embeddings=[embedding], metadatas=[metadata],
                      documents=[document] if document else None)

def query_collection(collection, query_embedding, n_results=10):
    return collection.query(query_embeddings=[query_embedding], n_results=n_results)