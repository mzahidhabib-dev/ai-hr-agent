import pdfplumber

def extract_all_tables(pdf_path: str) -> list[dict]:
    """
    Extracts tables from a PDF using pdfplumber.
    Returns a list of dicts: {"page_number": int, "rows": list[list[str]]}
    """
    tables_data = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            extracted_tables = page.extract_tables()
            
            for table in extracted_tables:
                if not table:
                    continue
                    
                # Clean the table data (remove newlines from cells)
                cleaned_table = []
                for row in table:
                    cleaned_row = [" ".join(str(cell).replace('\n', ' ').split()) if cell else "" for cell in row]
                    cleaned_table.append(cleaned_row)
                    
                if not cleaned_table or len(cleaned_table) < 2 or not cleaned_table[0]:
                    continue
                    
                tables_data.append({
                    "page_number": page_num,
                    "rows": cleaned_table,
                    "method": "pdfplumber"
                })
                
    return tables_data
