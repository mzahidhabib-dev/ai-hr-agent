import os
import uuid
from src.ingestion.pipeline import ingest_images

def run_db_test():
    pdf_path = os.path.join("sample_docs", "Northbridge_Dynamics_2025_Annual_Report.pdf")
    # Generate a dummy document ID for this isolated test
    document_id = str(uuid.uuid4())
    print(f"Testing ingest_images with Document ID: {document_id}")
    ingest_images(pdf_path, document_id)

if __name__ == "__main__":
    run_db_test()
