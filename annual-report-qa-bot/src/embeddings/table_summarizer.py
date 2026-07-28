import time
from google import genai

def summarize_tables(tables: list[dict], client: genai.Client) -> list[dict]:
    """
    Uses Gemini 2.5 Flash to summarize the content of each extracted Markdown table.
    Returns the updated list with a 'summary' key added to each dictionary.
    Includes a 4-second delay for free-tier rate limits.
    """
    prompt_template = (
        "You are an expert financial analyst reading an annual report. "
        "I will provide you with a raw markdown table extracted from the report. "
        "Your task is to thoroughly describe the table. What does the data show? "
        "What are the most important trends, figures, or totals? "
        "Do not hallucinate data not found in the table. \n\n"
        "Here is the raw table:\n\n{table}\n\n"
        "Please output your textual summary first, and then underneath it, output the exact raw markdown table I provided you so it can be viewed by the user."
    )
    
    summarized_tables = []
    
    for i, table_dict in enumerate(tables):
        markdown_table = table_dict["markdown_table"]
        page_num = table_dict["page_number"]
        
        prompt = prompt_template.format(table=markdown_table)
        
        try:
            response = client.models.generate_content(
                model='gemini-flash-lite-latest',
                contents=prompt,
            )
            
            summary = response.text
            
            summarized_tables.append({
                "page_number": page_num,
                "markdown_table": markdown_table,
                "summary": summary
            })
            
            print(f"[SUCCESS] Summarized table {i+1}/{len(tables)} from page {page_num}")
            
            # Rate limit protection (15 RPM -> 4 seconds per request)
            if i < len(tables) - 1:
                time.sleep(4.0)
                
        except Exception as e:
            print(f"[ERROR] Failed to summarize table on page {page_num}: {e}")
            
    return summarized_tables
