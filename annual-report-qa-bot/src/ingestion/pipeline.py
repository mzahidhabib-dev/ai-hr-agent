import os
import time
from dotenv import load_dotenv
from google import genai
from src.db.database import SessionLocal
from src.db.models import DocumentChunk, ExtractedImage, ExtractedTable
from src.ingestion.image_extractor import extract_images, describe_image
from src.ingestion.text_extractor import extract_text_by_page
from src.embeddings.chunker import chunk_text
from src.embeddings.embedder import embed_text
from src.ingestion.table_extractor import extract_all_tables
from src.utils.logger import get_logger
from src.utils.retry import retry_with_backoff

load_dotenv()
logger = get_logger(__name__)

# Cache client
_client = None
def get_genai_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _client

def ingest_text(pdf_path: str, document_id: str):
    logger.info(f"Starting text ingestion for {pdf_path} (Doc ID: {document_id})")
    
    pages = extract_text_by_page(pdf_path)
    if not pages:
        logger.warning(f"No extractable text found in {pdf_path}")
        return
        
    chunks = chunk_text(pages, chunk_size=800, overlap=150)
    
    db_session = SessionLocal()
    saved_count = 0
    
    try:
        for chunk in chunks:
            text = chunk["chunk_text"]
            page_num = chunk["page_number"]
            
            try:
                embedding = embed_text(text)
                if embedding is None:
                    continue
                    
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    content=text,
                    chunk_type="text",
                    page_number=page_num,
                    embedding=embedding
                )
                db_session.add(db_chunk)
                saved_count += 1
                time.sleep(4.0) 
                
            except Exception as e:
                logger.error(f"Failed to embed/save text chunk on page {page_num}: {e}")
                
        db_session.commit()
        logger.info(f"Ingested {saved_count} text chunks from {pdf_path}")
        
    except Exception as e:
        logger.error(f"Fatal error during text ingestion: {e}")
        db_session.rollback()
    finally:
        db_session.close()

@retry_with_backoff(retries=5, initial_backoff=30)
def summarize_table(rows: list[list[str]]) -> str:
    """Uses Gemini to summarize raw table rows into plain text."""
    client = get_genai_client()
    
    is_truncated = False
    if len(rows) > 30:
        rows_to_process = rows[:30]
        is_truncated = True
    else:
        rows_to_process = rows
        
    table_str = "\n".join([" | ".join([str(cell).strip() for cell in row]) for row in rows_to_process])
    if is_truncated:
        table_str += f"\n[table continues for {len(rows) - 30} more rows]"
        
    prompt = (
        "--- SYSTEM ---\n"
        "You are converting a table from a financial/annual report into a clear text description. "
        "Describe what the table shows, including specific numbers and labels. Write 2-4 sentences. "
        "Do not use markdown. Plain text only.\n"
        "--- USER ---\n"
        "Table data (first row is likely headers):\n"
        f"{table_str}\n---"
    )
    
    response = client.models.generate_content(
        model='gemini-flash-lite-latest',
        contents=prompt
    )
    return response.text.strip()

def ingest_tables(pdf_path: str, document_id: str):
    logger.info(f"Starting table ingestion for {pdf_path} (Doc ID: {document_id})")
    
    tables = extract_all_tables(pdf_path)
    if not tables:
        logger.warning(f"No tables found in {pdf_path}")
        return
        
    db_session = SessionLocal()
    saved_count = 0
    
    try:
        for table_dict in tables:
            rows = table_dict["rows"]
            page_num = table_dict["page_number"]
            
            try:
                summary = summarize_table(rows)
                
                db_table = ExtractedTable(
                    document_id=document_id,
                    page_number=page_num,
                    table_data=rows,
                    table_summary=summary
                )
                db_session.add(db_table)
                
                embedding = embed_text(summary)
                
                if embedding is not None:
                    db_chunk = DocumentChunk(
                        document_id=document_id,
                        content=summary,
                        chunk_type="table",
                        page_number=page_num,
                        embedding=embedding
                    )
                    db_session.add(db_chunk)
                    saved_count += 1
                    
                time.sleep(4.0) 
                
            except Exception as e:
                logger.error(f"Failed to process table on page {page_num}: {e}")
                
        db_session.commit()
        logger.info(f"Ingested {saved_count} tables from {pdf_path}")
        
    except Exception as e:
        logger.error(f"Fatal error during table ingestion: {e}")
        db_session.rollback()
    finally:
        db_session.close()

def ingest_images(pdf_path: str, document_id: str):
    logger.info(f"Starting image ingestion for {pdf_path} (Doc ID: {document_id})")
    output_dir = "temp_images"
    
    images = extract_images(pdf_path, output_dir)
    if not images:
        logger.warning(f"No images found to extract.")
        return
        
    db_session = SessionLocal()
    saved_count = 0
    
    try:
        for img_data in images:
            page_num = img_data["page_number"]
            image_path = img_data["image_path"]
            
            try:
                description = describe_image(image_path)
                if description in ["NO_CHART_FOUND", "DESCRIPTION_FAILED"]:
                    continue
                    
                db_image = ExtractedImage(
                    document_id=document_id,
                    page_number=page_num,
                    image_description=description
                )
                db_session.add(db_image)
                
                embedding = embed_text(description)
                
                if embedding is not None:
                    db_chunk = DocumentChunk(
                        document_id=document_id,
                        content=description,
                        chunk_type="image_caption",
                        page_number=page_num,
                        embedding=embedding
                    )
                    db_session.add(db_chunk)
                    saved_count += 1
                    
                time.sleep(4.0)
                
            except Exception as e:
                logger.error(f"Failed to process image on page {page_num}: {e}")
                
        db_session.commit()
        logger.info(f"Found {saved_count} charts/images out of {len(images)} pages checked")
        
    except Exception as e:
        logger.error(f"Fatal error during image ingestion: {e}")
        db_session.rollback()
    finally:
        db_session.close()
