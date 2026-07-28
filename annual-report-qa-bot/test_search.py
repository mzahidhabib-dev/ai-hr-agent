import os
from dotenv import load_dotenv
from src.db.database import SessionLocal
from src.retrieval.searcher import hybrid_search

load_dotenv()

def run_interactive_search():
    db = SessionLocal()
    print("==================================================")
    print("   WELCOME TO THE HYBRID SEARCH TESTER   ")
    print("==================================================")
    print("This script will search your Supabase database using")
    print("Reciprocal Rank Fusion (AI Semantic + Exact Keyword).")
    print("Type 'exit' to quit.\n")
    
    try:
        while True:
            query = input("Enter a search query: ")
            if query.lower() in ['exit', 'quit']:
                break
                
            print("\n🔍 Scanning database...\n")
            
            try:
                results = hybrid_search(query, db, top_k=3)
                
                if not results:
                    print("No chunks found in database. Did you run the pipeline?\n")
                    continue
                    
                for i, result in enumerate(results, 1):
                    print(f"--- MATCH {i} [Type: {result.chunk_type.value.upper()}, Page: {result.page_number}] ---")
                    # We print up to 500 characters of the matched chunk so it doesn't flood the terminal
                    snippet = result.content.strip()
                    if len(snippet) > 500:
                        snippet = snippet[:500] + "...\n[CHUNK TRUNCATED FOR READABILITY]"
                    print(snippet)
                    print("-" * 65 + "\n")
            except Exception as e:
                print(f"Error during search: {e}\n")
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        db.close()

if __name__ == "__main__":
    run_interactive_search()
