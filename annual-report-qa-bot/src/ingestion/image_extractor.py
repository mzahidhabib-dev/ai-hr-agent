import os
import time
import pdfplumber
from PIL import Image
from google import genai
from src.utils.retry import retry_with_backoff

def extract_images(pdf_path: str, output_dir: str) -> list[dict]:
    """
    Extracts pages with embedded images from a PDF, rendering the full page as a PNG.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    extracted_images = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            if page.images:
                # Render the full page as a PNG at 150 DPI
                image_path = os.path.join(output_dir, f"page_{i}.png")
                page_img = page.to_image(resolution=150)
                page_img.save(image_path, format="PNG")
                
                extracted_images.append({
                    "page_number": i,
                    "image_path": image_path
                })
                
    return extracted_images

# Cache client
_client = None
def get_genai_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _client

@retry_with_backoff(retries=5, initial_backoff=30)
def describe_image(image_path: str) -> str:
    """
    Uses Gemini Vision to describe charts, graphs, or diagrams on the page.
    Returns NO_CHART_FOUND if there are none.
    """
    client = get_genai_client()
    
    prompt = (
        "Look at this page from an annual report. If it contains a chart, graph, or diagram, "
        "describe what it shows in detail — axis labels, data trends, specific numbers visible, "
        "and what conclusion the chart supports. If the page has no chart or diagram, respond "
        "with exactly: NO_CHART_FOUND. Plain text only, no markdown."
    )
    
    try:
        image = Image.open(image_path)
    except Exception as e:
        print(f"[ERROR] Failed to open image {image_path}: {e}")
        return "DESCRIPTION_FAILED"
    
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model='gemini-flash-lite-latest',
                contents=[prompt, image]
            )
            return response.text.strip()
        except Exception as e:
            if attempt == 0:
                print(f"[WARNING] Gemini Vision failed for {image_path}, retrying in 2 seconds... ({e})")
                time.sleep(2.0)
            else:
                print(f"[ERROR] Gemini Vision failed twice for {image_path}: {e}")
                
    return "DESCRIPTION_FAILED"
