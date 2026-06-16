import psycopg2
import os
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from pypdf import PdfReader
from openai import OpenAI

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Step 1: Extract chunks from PDF
reader = PdfReader("Profile.pdf")
chunks = []

for page in reader.pages:
    text = page.extract_text()
    for i in range(0, len(text), 400):
        chunk = text[i : i+500]
        res = client.embeddings.create(
            model="text-embedding-3-small",
            input=[chunk]
        )
        embedding = res.data[0].embedding
        chunks.append({"text": chunk, "embedding": embedding})

print(f"Total chunks: {len(chunks)}")

# Step 2: Store in pgvector
conn = psycopg2.connect(DATABASE_URL)
register_vector(conn)
cur = conn.cursor()

for chunk in chunks:
    cur.execute("""
        INSERT INTO rag_docs (user_id, doc_name, chunk, embedding)
        VALUES (%s, %s, %s, %s)
    """, (1, "Profile.pdf", chunk["text"], chunk["embedding"]))

conn.commit()
conn.close()

print("All chunks inserted successfully")