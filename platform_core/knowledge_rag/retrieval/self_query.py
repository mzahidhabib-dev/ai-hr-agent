import os
import json
from google import genai
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

_client = None
def get_genai_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _client

def rewrite_query(user_question: str) -> dict:
    """
    Rewrites user questions into refined search queries and extracts preferred chunk types.
    """
    client = get_genai_client()
    
    prompt = f"""--- SYSTEM ---
You rewrite user questions into better search queries for a document retrieval system over an annual report or knowledge base. Respond ONLY with valid JSON, no markdown, no explanation.
Return exactly:
{{
  "search_query": string,
  "preferred_chunk_type": "text" | "table" | "image_caption" | "any"
}}
--- USER ---
Question: {user_question}
---"""
    
    try:
        response = client.models.generate_content(
            model='gemini-flash-lite-latest',
            contents=prompt,
        )
        
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
            
        return json.loads(raw_text)
    except Exception as e:
        logger.warning(f"Query rewrite failed, falling back to original query: {e}")
        return {"search_query": user_question, "preferred_chunk_type": "any"}
