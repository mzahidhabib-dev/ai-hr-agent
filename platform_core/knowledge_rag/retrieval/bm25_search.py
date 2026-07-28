from rank_bm25 import BM25Okapi
from platform_core.db import get_connection

class BM25Index:
    def __init__(self, document_id: str):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content, page_number, chunk_type FROM document_chunks WHERE document_id = %s",
                (document_id,)
            )
            rows = cursor.fetchall()
            self.all_chunks = rows
            
            corpus = [r[1].lower().split() for r in self.all_chunks]
            if not corpus:
                self.bm25 = None
            else:
                self.bm25 = BM25Okapi(corpus)
                
            self.chunk_map = {i: r for i, r in enumerate(self.all_chunks)}
        finally:
            conn.close()
            
    def search(self, query: str, top_k: int = 10) -> list:
        if not self.bm25:
            return []
            
        tokenized_query = query.lower().split()
        doc_scores = self.bm25.get_scores(tokenized_query)
        
        scored_chunks = [(i, score) for i, score in enumerate(doc_scores) if score > 0]
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for i, score in scored_chunks[:top_k]:
            r = self.chunk_map[i]
            results.append({
                "chunk_id": str(r[0]),
                "content": r[1],
                "page_number": r[2],
                "chunk_type": str(r[3]),
                "score": float(score)
            })
            
        return results
