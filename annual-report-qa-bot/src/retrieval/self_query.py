import os
import json
from google import genai
from src.utils.logger import get_logger
from src.utils.retry import retry_with_backoff

# Cache client
_client = None
def get_genai_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _client

@retry_with_backoff(retries=5, initial_backoff=30)
def rewrite_query(user_question: str) -> dict:
    """
    Rewrites user questions into better search queries and extracts preferred chunk types.
    """
    client = get_genai_client()
    
    prompt = f"""--- SYSTEM ---
You rewrite user questions into better search queries for a document retrieval system over an annual report. Respond ONLY with valid JSON, no markdown, no explanation.
Return exactly:
{{
  "search_query": string (a clear, specific rewrite of the question, expanding vague terms — e.g. "last year" should be left as-is since you don't know the actual year, but vague pronouns should be clarified),
  "preferred_chunk_type": "text" | "table" | "image_caption" | "any" (guess which type of content likely contains the answer — numbers/financials suggest "table", trends/visuals suggest "image_caption", general questions suggest "any")
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
        # Handle markdown blocks if Gemini stubbornly includes them
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
            
        return json.loads(raw_text)
    except Exception as e:
        print(f"[WARNING] Query rewrite failed, falling back to original query: {e}")
        return {"search_query": user_question, "preferred_chunk_type": "any"}
