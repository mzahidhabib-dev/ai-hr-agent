import zipfile
import xml.etree.ElementTree as ET
import os

docx_path = r"d:\My Porjects\AI HR Agent\Enterprise_AI_HR_Agent_Detailed_Requirements.docx"
output_path = r"d:\My Porjects\AI HR Agent\scratch\requirements.txt"

if os.path.exists(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        tree = ET.fromstring(z.read('word/document.xml'))
        paragraphs = []
        for node in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
            text = ''.join(node.itertext()).strip()
            if text:
                paragraphs.append(text)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(paragraphs))
    print(f"Successfully extracted {len(paragraphs)} paragraphs to {output_path}")
else:
    print(f"File not found: {docx_path}")
