import os
import uuid
import time
from dotenv import load_dotenv
from src.ingestion.pipeline import ingest_text, ingest_tables, ingest_images

load_dotenv()

def run_pipeline():
    pdf_path = os.path.join("sample_docs", "Northbridge_Dynamics_2025_Annual_Report.pdf")
    document_id = str(uuid.uuid4())
    
    print(f"==========================================")
    print(f"PHASE 1-3: FULL INGESTION PIPELINE")
    print(f"==========================================")
    print(f"Assigned Document ID: {document_id}\n")
    
    print("\n[1] Starting Text Ingestion...")
    ingest_text(pdf_path, document_id)
    
    print("\n[2] Starting Table Ingestion...")
    ingest_tables(pdf_path, document_id)
    
    print("\n[3] Starting Image Ingestion...")
    ingest_images(pdf_path, document_id)
        
    print(f"\n==========================================")
    print(f"PIPELINE COMPLETE!")
    print(f"==========================================")

if __name__ == "__main__":
    run_pipeline()
