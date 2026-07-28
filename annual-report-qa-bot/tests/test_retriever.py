import unittest
from dotenv import load_dotenv
from src.db.database import SessionLocal
from src.retrieval.searcher import semantic_search, bm25_search, hybrid_search
from src.db.models import DocumentChunk

load_dotenv()

class TestRetriever(unittest.TestCase):
    def setUp(self):
        # Connect to the real Supabase database for integration testing
        self.db = SessionLocal()
        
        # Automatically find the document_id we just populated in Phase 1 & 2
        latest_chunk = self.db.query(DocumentChunk).order_by(DocumentChunk.created_at.desc()).first()
        if latest_chunk:
            self.document_id = str(latest_chunk.document_id)
        else:
            self.document_id = None
            
    def tearDown(self):
        self.db.close()
        
    def test_searches(self):
        print("\n==================================================")
        print("1. Testing Semantic Search (AI Conceptual Match)")
        print("==================================================")
        query = "How is the company managing employee retention and culture?"
        semantic_results = semantic_search(query, self.db, top_k=2)
        self.assertTrue(len(semantic_results) > 0)
        print(f"Top semantic result type: {semantic_results[0].chunk_type.value}")
        print(f"Content snippet:\n{semantic_results[0].content[:200]}...\n")
        
        # 2. Test BM25 Search
        print("==================================================")
        print("2. Testing BM25 Search (Exact Keyword Match)")
        print("==================================================")
        query2 = "EBITDA margin percentage"
        bm25_results = bm25_search(query2, self.db, top_k=2)
        self.assertTrue(len(bm25_results) > 0)
        print(f"Top BM25 result type: {bm25_results[0].chunk_type.value}")
        print(f"Content snippet:\n{bm25_results[0].content[:200]}...\n")
        
        # 3. Test Hybrid Search
        print("==================================================")
        print("3. Testing Hybrid Search (Reciprocal Rank Fusion)")
        print("==================================================")
        query3 = "What are the exact figures for 2024 total revenue?"
        hybrid_results = hybrid_search(query3, self.db, top_k=2)
        self.assertTrue(len(hybrid_results) > 0)
        print(f"Top Hybrid result type: {hybrid_results[0].chunk_type.value}")
        print(f"Content snippet:\n{hybrid_results[0].content[:200]}...\n")

if __name__ == "__main__":
    unittest.main()
