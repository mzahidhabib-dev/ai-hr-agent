import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from src.db.database import SessionLocal
from src.db.models import Document, ChatSession, DocumentChunk, ExtractedTable, ExtractedImage
from src.ingestion.pipeline import ingest_text, ingest_tables, ingest_images
from src.retrieval.hybrid_search import search_with_self_query
from src.retrieval.answer_generator import generate_answer
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Annual Report QA Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the temp_pdfs directory to allow browser access to raw PDFs
app.mount("/files", StaticFiles(directory="temp_pdfs"), name="files")

API_KEY = os.environ.get("API_KEY", "dev-secret-key")

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from fastapi import BackgroundTasks

def process_document_background(file_path: str, doc_id: str):
    db = SessionLocal()
    db_doc = db.query(Document).filter(Document.id == doc_id).first()
    try:
        ingest_text(file_path, doc_id)
        ingest_tables(file_path, doc_id)
        ingest_images(file_path, doc_id)
        
        if db_doc:
            db_doc.status = "ready"
            db.commit()
    except Exception as e:
        if db_doc:
            db_doc.status = "failed"
            db.commit()
    finally:
        db.close()

@app.post("/documents/upload", dependencies=[Depends(verify_api_key)])
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Roadmap 6.2: Uploads a PDF and strictly runs the Phase 1-3 ingestion pipeline sequentially in the background."""
    os.makedirs("temp_pdfs", exist_ok=True)
    file_path = os.path.join("temp_pdfs", file.filename)
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
        
    doc_id = str(uuid.uuid4())
    db_doc = Document(id=doc_id, filename=file.filename, status="ingesting")
    db.add(db_doc)
    db.commit()
    
    background_tasks.add_task(process_document_background, file_path, doc_id)
    
    return {
        "document_id": doc_id,
        "status": "processing",
        "message": "Upload complete. Extraction is running in the background."
    }

@app.get("/documents", dependencies=[Depends(verify_api_key)])
def list_documents(skip: int = 0, limit: int = 5, db: Session = Depends(get_db)):
    """Blueprint req: List available documents for the frontend with pagination."""
    docs = db.query(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    total = db.query(Document).count()
    return {
        "documents": [{"id": str(d.id), "filename": d.filename, "status": d.status} for d in docs],
        "total": total
    }

@app.get("/documents/{document_id}/status", dependencies=[Depends(verify_api_key)])
def get_status(document_id: str, db: Session = Depends(get_db)):
    """Roadmap 6.2: Returns statistics about the processed document."""
    counts = db.query(DocumentChunk.chunk_type, func.count(DocumentChunk.id)).filter(
        DocumentChunk.document_id == document_id
    ).group_by(DocumentChunk.chunk_type).all()
    
    result = {str(c[0].value): c[1] for c in counts}
    return result

class AskRequest(BaseModel):
    question: str
    session_id: str = None

@app.post("/documents/{document_id}/ask", dependencies=[Depends(verify_api_key)])
def ask_question(document_id: str, req: AskRequest, db: Session = Depends(get_db)):
    """Roadmap 6.2: Accepts a question, self-queries the document, and returns a cited answer."""
    try:
        session_id = req.session_id
        if not session_id:
            # Blueprint req: Auto-name sessions based on first question
            session_id = str(uuid.uuid4())
            session_name = req.question[:50] + "..." if len(req.question) > 50 else req.question
            new_session = ChatSession(id=session_id, session_name=session_name)
            db.add(new_session)
            db.commit()
            
        retrieved_chunks = search_with_self_query(req.question, document_id, top_k=5)
        
        if not retrieved_chunks:
            return {
                "answer": "I don't know. The document does not contain enough information to answer this question.",
                "sources": [],
                "session_id": session_id,
                "tokens_used": 0
            }
            
        result = generate_answer(req.question, retrieved_chunks, session_id, document_id, db)
        result["session_id"] = session_id
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

@app.get("/sessions", dependencies=[Depends(verify_api_key)])
def list_sessions(skip: int = 0, limit: int = 5, db: Session = Depends(get_db)):
    """Blueprint req: Sidebar displays 5 most recent sessions with pagination."""
    sessions = db.query(ChatSession).order_by(ChatSession.created_at.desc()).offset(skip).limit(limit).all()
    total = db.query(ChatSession).count()
    return {
        "sessions": [{"id": str(s.id), "name": s.session_name, "created_at": s.created_at} for s in sessions],
        "total": total
    }

@app.get("/sessions/{session_id}/messages", dependencies=[Depends(verify_api_key)])
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    """Blueprint req: Load historical messages for a chat session."""
    from src.db.models import QueryLog
    logs = db.query(QueryLog).filter(QueryLog.session_id == session_id).order_by(QueryLog.created_at.asc()).all()
    
    messages = []
    for log in logs:
        # User message
        messages.append({"role": "user", "content": log.question})
        # Bot message
        # Convert JSONB UUIDs back if needed, but since we fix serialization they are strings.
        # But wait, answer generation doesn't store explicit page numbers in QueryLog...
        # Let's just return the answer text without citations to keep it simple, or empty sources.
        messages.append({
            "role": "bot",
            "content": log.answer,
            "sources": [] 
        })
    return messages

@app.get("/analytics", dependencies=[Depends(verify_api_key)])
def get_analytics(db: Session = Depends(get_db)):
    """Blueprint req: Admin analytics for total tokens and chunks."""
    from src.db.models import QueryLog
    total_docs = db.query(Document).count()
    total_sessions = db.query(ChatSession).count()
    total_tokens_used = db.query(func.sum(QueryLog.tokens_used)).scalar() or 0
    estimated_cost = (total_tokens_used / 1_000_000) * 0.15
    avg_confidence = db.query(func.avg(QueryLog.confidence_score)).scalar()
    
    return {
        "total_documents": total_docs,
        "total_sessions": total_sessions,
        "estimated_cost": estimated_cost,
        "average_confidence": round(float(avg_confidence), 1) if avg_confidence is not None else 0.0
    }

@app.delete("/documents/{document_id}", dependencies=[Depends(verify_api_key)])
def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Deletes a document and all its associated extraction data."""
    try:
        logger.info(f"Initiating deletion for document_id: {document_id}")
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.warning(f"Deletion failed: Document {document_id} not found.")
            raise HTTPException(status_code=404, detail="Document not found")
            
        # Delete associated data manually since we don't have cascade="all, delete" on foreign keys
        chunks_deleted = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        tables_deleted = db.query(ExtractedTable).filter(ExtractedTable.document_id == document_id).delete()
        images_deleted = db.query(ExtractedImage).filter(ExtractedImage.document_id == document_id).delete()
        
        logger.info(f"Deleted associated data for {document_id}: {chunks_deleted} chunks, {tables_deleted} tables, {images_deleted} images.")
        
        # Delete the document itself
        db.delete(doc)
        db.commit()
        logger.info(f"Successfully deleted Document record for {document_id} from database.")
        
        # Delete the physical file
        file_path = os.path.join("temp_pdfs", doc.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Successfully deleted physical file: {file_path}")
        else:
            logger.info(f"Physical file not found (already deleted or missing): {file_path}")
            
        return {"status": "success", "message": "Document deleted"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete document {document_id}. Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
