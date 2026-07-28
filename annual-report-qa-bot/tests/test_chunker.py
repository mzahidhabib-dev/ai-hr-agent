import unittest
from src.embeddings.chunker import chunk_text

class TestChunker(unittest.TestCase):
    def test_chunk_text_normal(self):
        pages = [
            {"page_number": 1, "text": "This is the first sentence. This is the second sentence. And here is a third."}
        ]
        # Extremely small chunk size for testing
        results = chunk_text(pages, chunk_size=30, overlap=10)
        
        self.assertTrue(len(results) > 1, "Should split into multiple chunks")
        for chunk in results:
            self.assertTrue(len(chunk["chunk_text"]) <= 30)
            self.assertEqual(chunk["chunk_type"], "text")
            self.assertEqual(chunk["page_number"], 1)

    def test_chunk_text_giant_sentence(self):
        giant_string = "A" * 1000
        pages = [{"page_number": 2, "text": giant_string}]
        
        results = chunk_text(pages, chunk_size=800, overlap=150)
        
        self.assertEqual(len(results), 2, "Giant string should be hard-sliced into 2 chunks")
        self.assertTrue(len(results[0]["chunk_text"]) <= 800)
        self.assertTrue(len(results[1]["chunk_text"]) <= 800)
        
    def test_empty_pages(self):
        results = chunk_text([], chunk_size=800, overlap=150)
        self.assertEqual(results, [])
        
if __name__ == "__main__":
    unittest.main()
