import unittest
from unittest.mock import patch, MagicMock
from src.embeddings.embedder import embed_and_save_chunks

class TestEmbedder(unittest.TestCase):
    
    @patch('src.embeddings.embedder.time.sleep')
    @patch('src.embeddings.embedder.client.models.embed_content')
    def test_embed_and_save_chunks(self, mock_embed, mock_sleep):
        # Mock the new API response structure so we don't use real tokens
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.values = [0.1, 0.2, 0.3] * 256 # 768 dimensions
        mock_response.embeddings = [mock_embedding]
        mock_embed.return_value = mock_response
        
        # Mock the database session
        mock_session = MagicMock()
        
        chunks = [
            {"chunk_text": "First chunk", "page_number": 1, "chunk_type": "text"},
            {"chunk_text": "Second chunk", "page_number": 1, "chunk_type": "text"}
        ]
        
        document_id = "test-doc-id-1234"
        
        # Run function
        saved_count = embed_and_save_chunks(chunks, document_id, mock_session)
        
        # Verify results
        self.assertEqual(saved_count, 2)
        
        # Verify API was called twice
        self.assertEqual(mock_embed.call_count, 2)
        
        # Verify time.sleep was called once (between the 2 chunks)
        self.assertEqual(mock_sleep.call_count, 1)
        mock_sleep.assert_called_with(4.0)
        
        # Verify db.add was called twice and commit at least once
        self.assertEqual(mock_session.add.call_count, 2)
        self.assertTrue(mock_session.commit.called)

if __name__ == "__main__":
    unittest.main()
