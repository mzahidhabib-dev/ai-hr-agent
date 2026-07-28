from sqlalchemy import text
from platform_core.knowledge_rag.embeddings.embedder import embed_text
from platform_core.db import get_connection

def vector_search(query: str, document_id: str, top_k: int = 10) -> list:
    """Pure semantic search using raw SQL for pgvector."""
    query_vector = embed_text(query)
    
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
    
    conn = get_connection()
    try:
        vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, content, page_number, chunk_type, 1 - (embedding <=> %s::vector) as score
            FROM document_chunks
            WHERE document_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vector_str, document_id, vector_str, top_k)
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            results.append({
                "chunk_id": str(r[0]),
                "content": r[1],
                "page_number": r[2],
                "chunk_type": r[3],
                "score": float(r[4])
            })
        return results
    finally:
        conn.close()
