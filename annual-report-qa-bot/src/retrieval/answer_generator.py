import json
from sqlalchemy.orm import Session
from src.retrieval.hybrid_search import search_with_self_query
from src.retrieval.self_query import get_genai_client
from src.db.models import QueryLog, RetrievalMethod, Document
from src.utils.retry import retry_with_backoff
from google import genai
from pydantic import BaseModel

class AnswerResponse(BaseModel):
    answer: str
    confidence_score: int

@retry_with_backoff(retries=5, initial_backoff=30)
def generate_answer(question: str, retrieved_chunks: list[dict], session_id: str, document_id: str, db_session: Session) -> dict:
    """
    Generates an answer using the provided context, extracts native token costs,
    and returns structured JSON with specific page citations.
    """
    client = get_genai_client()
    
    # 1. Build the exact prompt specified by the roadmap
    context_blocks = []
    for chunk in retrieved_chunks:
        context_blocks.append(f"[Page {chunk['page_number']}] {chunk['content']}")
        
    context_str = "\n".join(context_blocks)
    
    system_prompt = (
        "Answer the question using ONLY the provided context from an annual report. "
        "After each claim, cite the page number in this format: [Page X]. "
        "If the context does not contain enough information to answer, say so clearly instead of guessing. "
        "Plain text, no markdown."
    )
    
    prompt = f"--- SYSTEM ---\n{system_prompt}\n--- USER ---\nContext:\n{context_str}\n\nQuestion: {question}\n---"
    
    # 2. Call Gemini
    response = client.models.generate_content(
        model='gemini-flash-lite-latest',
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AnswerResponse,
        )
    )
    
    # Parse the structured output
    result_data = json.loads(response.text)
    answer_text = result_data.get("answer", "")
    confidence_score = result_data.get("confidence_score", 0)
    
    tokens_used = response.usage_metadata.total_token_count if response.usage_metadata else 0
    
    # 3. Extract unique page numbers as sources and get filename
    pages = list(set([chunk["page_number"] for chunk in retrieved_chunks]))
    filename = None
    if document_id:
        doc = db_session.query(Document).filter(Document.id == document_id).first()
        if doc:
            filename = doc.filename

    sources = [{"page": p, "filename": filename} for p in pages]
    
    # 4. Save to QueryLog with token tracking and confidence score
    log = QueryLog(
        session_id=session_id if session_id else None,
        question=question,
        retrieved_chunk_ids=[str(chunk["chunk_id"]) for chunk in retrieved_chunks],
        answer=answer_text,
        retrieval_method=RetrievalMethod.hybrid,
        tokens_used=tokens_used,
        confidence_score=confidence_score
    )
    db_session.add(log)
    db_session.commit()
    
    # 5. Return structured dictionary
    return {
        "answer": answer_text,
        "sources": sources,
        "tokens_used": tokens_used
    }
