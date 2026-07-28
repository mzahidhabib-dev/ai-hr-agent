import unittest
import os
from src.ingestion.text_extractor import extract_text_by_page

class TestTextExtractor(unittest.TestCase):
    def test_extract_text_by_page(self):
        pdf_path = os.path.join("sample_docs", "Northbridge_Dynamics_2025_Annual_Report.pdf")
        
        self.assertTrue(os.path.exists(pdf_path), f"Test PDF not found at {pdf_path}")
        
        results = extract_text_by_page(pdf_path)
        
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0, "Expected non-empty list of extracted pages.")
        
        self.assertIn("page_number", results[0])
        self.assertIn("text", results[0])

if __name__ == "__main__":
    unittest.main()
