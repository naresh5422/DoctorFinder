from dotenv import load_dotenv
from app.services.pinecone_rag import upload_rag_to_pinecone

if __name__ == "__main__":
    load_dotenv()
    print("Uploading RAG embeddings to Pinecone...")
    try:
        result = upload_rag_to_pinecone()
        print(f"Uploaded {result['uploaded_chunks']} chunks to Pinecone index '{result['index']}' in namespace '{result['namespace']}'.")
        print("RAG pipeline build complete.")
    except Exception as exc:
        print(f"ERROR: {exc}")
        print("\nIf this is due to Pinecone quota limits, create the configured index manually in the Pinecone console and rerun the script.")
        raise
