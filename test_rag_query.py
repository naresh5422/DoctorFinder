from dotenv import load_dotenv

load_dotenv()

from app.services.pinecone_rag import query_pinecone

results = query_pinecone("how to connect with doctors?")

print(results)