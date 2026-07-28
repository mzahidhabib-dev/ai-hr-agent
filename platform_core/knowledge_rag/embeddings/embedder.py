import time
import os
from google import genai
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

_client = None
def get_genai_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "dummy_key_for_testing")
        _client = genai.Client(api_key=api_key)
    return _client

def embed_text(text: str) -> list:
    """Generates an embedding for a single text chunk."""
    client = get_genai_client()
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=text,
        config={"task_type": "RETRIEVAL_DOCUMENT", "output_dimensionality": 768}
    )
    return result.embeddings[0].values

def embed_batch(texts: list) -> list:
    """Generates embeddings for a batch of text chunks with rate limit padding."""
    embeddings = []
    for i, text in enumerate(texts):
        try:
            emb = embed_text(text)
            embeddings.append(emb)
        except Exception as e:
            logger.error(f"Failed to embed text index {i}: {e}")
            embeddings.append(None)
            
        if i < len(texts) - 1:
            time.sleep(4.0)
            
    return embeddings
