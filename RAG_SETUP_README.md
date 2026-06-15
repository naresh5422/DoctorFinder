# RAG Pipeline Setup - Action Required

## Status: ⚠️ Waiting for Pinecone Index Creation

Your Pinecone account currently has **no pod quota** to create indexes. You need to manually create the index first.

## What You Need to Do

### Step 1: Create Pinecone Index
1. Go to: https://www.pinecone.io/console/
2. Click **"Create Index"**
3. Fill in these details:
   - **Name**: `careslotly-rag-index`
   - **Dimension**: `384`
   - **Metric**: `cosine`
   - **Pod Type**: Choose the option available to you
4. Click **Create**

### Step 2: Upload RAG Data
Once the index is created, run this command:

```powershell
cd d:\All_Projects\DoctorFinder
.venv\Scripts\python.exe build_rag_pipeline.py
```

Expected output:
```
Uploading RAG embeddings to Pinecone...
Uploaded <chunk_count> chunks to Pinecone index 'careslotly-rag-index' in namespace 'careslotly-rag-namespace'.
RAG pipeline build complete.
```

### Step 3: Start the Application
Once RAG data is uploaded, start your Flask app normally:

```powershell
python run.py
```

## Checking Status

To check if your Pinecone account is ready, run:

```powershell
.venv\Scripts\python.exe check_pinecone_status.py
```

## What Was Set Up

✅ **Pinecone RAG Service** (`app/services/pinecone_rag.py`)
- Embedding model: all-MiniLM-L6-v2 (384-dimensional)
- LLM: google/flan-t5-small by default, configurable with `RAG_LLM_MODEL_NAME`
- Text processing: heading-aware 140-word chunks with 30-word overlap
- Retrieval: expanded healthcare/service queries, semantic search, keyword/title reranking, and section-diverse results
- Metadata: section title, section index, chunk index, and keywords are stored for better retrieval ranking
- Integration: Automatic chatbot fallback

✅ **Modular RAG Pipeline** (`app/services/rag_pipeline/`)
- `config.py`: model names, source path, chunk settings, query expansion terms, rerank weights
- `text_processing.py`: section extraction, chunking, tokenization, query expansion
- `retrieval.py`: lexical scoring, semantic/keyword score blending, diverse result selection
- `answering.py`: concise point-wise answer formatting
- `local_store.py`: local SentenceTransformer index, retrieval, fallback answer generation
- `pinecone_store.py`: Pinecone upload, query, reranking, LLM answer generation
- `rag_service.py` and `pinecone_rag.py`: compatibility wrappers for existing imports

✅ **RAG Training Data** (`app/Careslotly_RAG_Reference.txt`)
- 220+ lines of CareSlotly documentation
- Covers 20+ health conditions
- Ready to upload

✅ **Build Script** (`build_rag_pipeline.py`)
- Loads Careslotly_RAG_Reference.txt
- Generates embeddings
- Uploads to Pinecone in batches

✅ **Chatbot Integration** (`app/routers.py`)
- RAG endpoint: `POST /rag/query`
- Chatbot fallback chain: FAQ → Health Advice → Search → **RAG**

## Troubleshooting

**Q: How do I check if the index was created?**
```powershell
.venv\Scripts\python.exe check_pinecone_status.py
```

**Q: Can I delete/recreate the index?**
Yes, go to Pinecone console and delete the index to free up quota, then create a new one.

**Q: What if I get "Module not found" errors?**
Run: `.venv\Scripts\pip.exe install pinecone-client==2.2.1`

**Q: How do I test the RAG endpoint after setup?**
```bash
curl -X POST http://localhost:5000/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question":"How do I book an appointment?"}'
```

## Files Modified

- `app/services/rag_pipeline/*` - Modular RAG pipeline
- `app/services/pinecone_rag.py` - Pinecone compatibility wrapper
- `app/services/rag_service.py` - Local RAG compatibility wrapper
- `app/routers.py` - RAG query endpoint + chatbot integration
- `app/main.py` - Removed old rag_service dependency
- `build_rag_pipeline.py` - Build script (UPDATED)
- `app/Careslotly_RAG_Reference.txt` - Training data (NEW)
- `check_pinecone_status.py` - Diagnostic tool (NEW)
- `requirements.txt` - Added pinecone-client

## Next Steps

1. ⬜ **CREATE INDEX** in Pinecone console (YOUR ACTION)
2. ⬜ Run `build_rag_pipeline.py` to upload embeddings
3. ⬜ Test `/rag/query` endpoint
4. ⬜ Start Flask app

---

Questions? Run `check_pinecone_status.py` to diagnose any issues.
