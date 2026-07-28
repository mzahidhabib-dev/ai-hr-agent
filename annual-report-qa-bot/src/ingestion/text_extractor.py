import pdfplumber
from src.utils.logger import get_logger

logger = get_logger(__name__)

def extract_text_by_page(pdf_path: str) -> list[dict]:
    """
    Extracts text from a PDF page by page.
    Returns a list of dicts: {"page_number": int, "text": str}.
    Skips pages with no extractable text.
    """
    extracted_pages = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if text is None or text.strip() == "":
                    logger.warning(f"Page {page_number} has no extractable text, may be scanned/image-only.")
                    continue
                
                extracted_pages.append({
                    "page_number": page_number,
                    "text": text.strip()
                })
    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")
        raise
        
    return extracted_pages
