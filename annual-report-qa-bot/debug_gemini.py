import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client()

print("Testing available embedding models...")
for m in client.models.list():
    if "embed" in m.name:
        print(f"- {m.name}")

print("\nTesting gemini-embedding-2 with 768 dimensions...")
try:
    res = client.models.embed_content(
        model="gemini-embedding-2", 
        contents="Hello world",
        config={"output_dimensionality": 768, "task_type": "RETRIEVAL_DOCUMENT"}
    )
    print("Success! Dimensions:", len(res.embeddings[0].values))
except Exception as e:
    print("Error with gemini-embedding-2:", e)
