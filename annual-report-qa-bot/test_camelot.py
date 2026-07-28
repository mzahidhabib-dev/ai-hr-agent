import camelot
import os

pdf_path = os.path.join("sample_docs", "Northbridge_Dynamics_2025_Annual_Report.pdf")
try:
    print("Testing Camelot table extraction...")
    tables = camelot.read_pdf(pdf_path, pages='1-3')
    print(f"Success! Found {tables.n} tables.")
except Exception as e:
    print(f"Camelot error: {e}")
    
import pdfplumber
try:
    print("\nTesting PDFPlumber table extraction...")
    with pdfplumber.open(pdf_path) as pdf:
        count = 0
        for i in range(3):
            tables = pdf.pages[i].extract_tables()
            count += len(tables)
    print(f"Success! Found {count} tables.")
except Exception as e:
    print(f"PDFPlumber error: {e}")
