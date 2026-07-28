from rank_bm25 import BM25Okapi
from src.db.models import DocumentChunk
from src.db.database import SessionLocal

class BM25Index:
    def __init__(self, document_id: str):
        db = SessionLocal()
        try:
            # Load ALL DocumentChunk rows for this document
            self.all_chunks = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).all()
            
            # Tokenize and build index
            corpus = [chunk.content.lower().split() for chunk in self.all_chunks]
            
            if not corpus:
                self.bm25 = None
            else:
                self.bm25 = BM25Okapi(corpus)
                
            # Store chunk metadata in chunk_map keyed by index position
            self.chunk_map = {i: chunk for i, chunk in enumerate(self.all_chunks)}
        finally:
            db.close()
            
    def search(self, query: str, top_k: int = 10) -> list[dict]:
        if not self.bm25:
            return []
            
        tokenized_query = query.lower().split()
        doc_scores = self.bm25.get_scores(tokenized_query)
        
        scored_chunks = [(i, score) for i, score in enumerate(doc_scores) if score > 0]
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for i, score in scored_chunks[:top_k]:
            chunk = self.chunk_map[i]
            results.append({
                "chunk_id": str(chunk.id),
                "content": chunk.content,
                "page_number": chunk.page_number,
                "chunk_type": chunk.chunk_type.value,
                "score": float(score)
            })
            
        return results
