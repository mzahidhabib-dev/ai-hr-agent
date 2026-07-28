from sqlalchemy import text
from src.embeddings.embedder import embed_text
from src.db.database import SessionLocal

def vector_search(query: str, document_id: str, top_k: int = 10) -> list[dict]:
    """Pure semantic search using raw SQL for pgvector."""
    # 1. Embed query
    query_vector = embed_text(query)
    
    # 2. Run SQL query using pgvector operator <=>. Raw SQL required by roadmap.
    sql = text("""
        SELECT 
            id as chunk_id, 
            content, 
            page_number, 
            chunk_type, 
            1 - (embedding <=> :vector) as score 
        FROM document_chunks
        WHERE document_id = :doc_id
        ORDER BY embedding <=> :vector
        LIMIT :top_k
    """)
    
    db = SessionLocal()
    try:
        # Pass the vector properly as a string representation of the float array
        vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"
        
        result = db.execute(sql, {
            "vector": vector_str,
            "doc_id": document_id,
            "top_k": top_k
        }).mappings().all()
        
        # 3. Return results as list of dicts
        return [dict(row) for row in result]
    finally:
        db.close()
