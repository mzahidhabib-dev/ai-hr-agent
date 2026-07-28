import os
from fastapi.testclient import TestClient
from src.api.main import app

os.environ["API_KEY"] = "dev-secret-key"
client = TestClient(app)
HEADERS = {"x-api-key": "dev-secret-key"}

def run_tests():
    print("==================================================")
    print("PHASE 6: FastAPI Backend Integration Test")
    print("==================================================")
    
    print("\n[TEST 1] GET /documents")
    res1 = client.get("/documents", headers=HEADERS)
    print(f"Status: {res1.status_code}")
    print(res1.json())
    
    from src.db.database import SessionLocal
    from src.db.models import DocumentChunk
    db = SessionLocal()
    latest_chunk = db.query(DocumentChunk).order_by(DocumentChunk.created_at.desc()).first()
    if not latest_chunk:
        print("No documents in DB to test asking.")
        return
    document_id = str(latest_chunk.document_id)
    
    print(f"\n[TEST 2] GET /documents/{document_id}/status")
    res2 = client.get(f"/documents/{document_id}/status", headers=HEADERS)
    print(f"Status: {res2.status_code}")
    print(res2.json())
    
    print(f"\n[TEST 3] POST /documents/{document_id}/ask")
    payload = {"question": "what is the total revenue?"}
    res3 = client.post(f"/documents/{document_id}/ask", headers=HEADERS, json=payload)
    print(f"Status: {res3.status_code}")
    data = res3.json()
    print(data)
    
    print(f"\n[TEST 4] GET /sessions")
    res4 = client.get("/sessions", headers=HEADERS)
    print(f"Status: {res4.status_code}")
    print(res4.json())
    
    print("\n==================================================")
    print("ALL API TESTS EXECUTED")

if __name__ == "__main__":
    run_tests()
