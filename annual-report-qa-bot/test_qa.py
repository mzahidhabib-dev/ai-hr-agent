import os
from dotenv import load_dotenv
from src.db.database import SessionLocal
from src.generation.generator import generate_answer

load_dotenv()

def run_interactive_qa():
    db = SessionLocal()
    print("==================================================")
    print("     ANNUAL REPORT QA BOT - LIVE TESTER     ")
    print("==================================================")
    print("Ask any question about the company's financials.")
    print("Type 'exit' to quit.")
    
    try:
        from src.db.models import DocumentChunk
        latest_chunk = db.query(DocumentChunk).order_by(DocumentChunk.created_at.desc()).first()
        if not latest_chunk:
            print("No documents found in database. Run the pipeline first.")
            return
        document_id = str(latest_chunk.document_id)
        
        print(f"[INFO] Running search strictly against Document ID: {document_id}")
        
        while True:
            query = input("\n👤 YOU: ")
            if query.lower() in ['exit', 'quit']:
                break
                
            print("\n🤖 AI is thinking... (Retrieving chunks & generating answer)\n")
            
            try:
                answer = generate_answer(query, document_id, db)
                print(f"🤖 BOT:\n{answer}")
                print("\n" + "-" * 50)
            except Exception as e:
                print(f"Error during generation: {e}\n")
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        db.close()

if __name__ == "__main__":
    run_interactive_qa()
