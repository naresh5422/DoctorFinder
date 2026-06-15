import logging
import os
from typing import Dict, List, Optional

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

from app.services.rag_pipeline.answering import format_short_rag_answer, format_user_rag_response
from app.services.rag_pipeline.config import (
    EMBEDDING_MODEL_NAME,
    LLM_MODEL_NAME,
    MAX_RETRIEVAL_POOL,
    RAG_SOURCE_FILE,
)
from app.services.rag_pipeline.local_store import generate_local_rag_answer
from app.services.rag_pipeline.retrieval import combine_scores, lexical_score, rerank_candidates
from app.services.rag_pipeline.text_processing import build_rag_chunks, expand_query, tokenize

load_dotenv()

_embedding_model: Optional[SentenceTransformer] = None
_llm_pipeline = None
_pinecone_index = None


def get_pinecone_config():
    return {
        "api_key": os.getenv("PINECONE_API_KEY"),
        "index_name": os.getenv("PINECONE_INDEX_NAME", "careslotly-rag-index"),
        "namespace": os.getenv("PINECONE_NAMESPACE", "default"),
    }


def load_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def load_llm():
    global _llm_pipeline
    if _llm_pipeline is None:
        tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_NAME)
        model = AutoModelForSeq2SeqLM.from_pretrained(LLM_MODEL_NAME)
        _llm_pipeline = pipeline(
            "text2text-generation",
            model=model,
            tokenizer=tokenizer,
            device=-1,
            max_new_tokens=200,
            do_sample=False,
        )
    return _llm_pipeline


def init_pinecone():
    global _pinecone_index

    if _pinecone_index is not None:
        return _pinecone_index

    config = get_pinecone_config()
    if not config["api_key"]:
        raise RuntimeError("Missing PINECONE_API_KEY")

    try:
        from pinecone import Pinecone
    except ImportError as exc:
        raise RuntimeError("Pinecone SDK not installed. Run: pip install pinecone") from exc

    try:
        pc = Pinecone(api_key=config["api_key"])
        indexes_response = pc.list_indexes()
        existing_indexes = []

        try:
            if hasattr(indexes_response, "indexes"):
                existing_indexes = [idx.name for idx in indexes_response.indexes]
            else:
                existing_indexes = [
                    idx["name"] if isinstance(idx, dict) else idx.name
                    for idx in indexes_response
                ]
        except Exception:
            pass

        logging.info("Available Pinecone indexes: %s", existing_indexes)
        if config["index_name"] not in existing_indexes:
            raise RuntimeError(
                f"Pinecone index '{config['index_name']}' does not exist.\n"
                f"Available indexes: {existing_indexes}\n\n"
                "Create the index manually in Pinecone Console:\n"
                f"Name: {config['index_name']}\n"
                "Dimension: 384\n"
                "Metric: cosine"
            )

        _pinecone_index = pc.Index(config["index_name"])
        return _pinecone_index
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize Pinecone: {exc}")


def _pinecone_metadata(record, source_file: str, chunk_index: int):
    return {
        "source": os.path.basename(source_file),
        "chunk_index": chunk_index,
        "section_chunk_index": record.get("chunk_index"),
        "section_index": record.get("section_index"),
        "title": record.get("title"),
        "keywords": record.get("keywords", []),
        "text": record.get("text"),
    }


def upload_rag_to_pinecone(source_file: str = None, namespace: str = None) -> Dict:
    config = get_pinecone_config()
    if not config["api_key"]:
        raise RuntimeError("PINECONE_API_KEY is required.")

    index = init_pinecone()
    if index is None:
        raise RuntimeError("Pinecone index initialization failed.")

    source_file = source_file or RAG_SOURCE_FILE
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"RAG source file not found: {source_file}")

    with open(source_file, "r", encoding="utf-8") as source:
        text = source.read()

    chunk_records = build_rag_chunks(text)
    if not chunk_records:
        raise ValueError("No text chunks found in RAG source file.")

    chunks = [record["text"] for record in chunk_records]
    model = load_embedding_model()
    embeddings = model.encode(chunks, convert_to_tensor=False, show_progress_bar=True)

    namespace = namespace or config["namespace"]
    batch_size = 64
    for start in range(0, len(chunks), batch_size):
        end = start + batch_size
        ids = [f"rag-{idx}" for idx in range(start, min(end, len(chunks)))]
        vectors = [
            emb.tolist() if hasattr(emb, "tolist") else emb
            for emb in embeddings[start:end]
        ]
        metadata = [
            _pinecone_metadata(chunk_records[idx], source_file, idx)
            for idx in range(start, min(end, len(chunks)))
        ]
        index.upsert(vectors=list(zip(ids, vectors, metadata)), namespace=namespace)

    return {"uploaded_chunks": len(chunks), "namespace": namespace, "index": config["index_name"]}


def query_pinecone(question: str, top_k: int = 4, namespace: str = None) -> List[Dict]:
    if not question or not question.strip():
        return []

    index = init_pinecone()
    if index is None:
        raise RuntimeError("Pinecone index is not initialized.")

    model = load_embedding_model()
    expanded_question = expand_query(question)
    query_embedding = model.encode(expanded_question, convert_to_tensor=False)
    config = get_pinecone_config()
    namespace = namespace or config["namespace"]
    fetch_k = min(max(top_k * 5, top_k), MAX_RETRIEVAL_POOL)
    query_response = index.query(
        vector=query_embedding.tolist(),
        top_k=fetch_k,
        include_metadata=True,
        namespace=namespace,
    )

    candidates = []
    query_tokens = tokenize(expanded_question)
    for match in query_response.matches:
        metadata = match.metadata or {}
        text = metadata.get("text")
        semantic_score = float(match.score)
        keyword_score = lexical_score(query_tokens, text or "", metadata)
        candidates.append({
            "score": combine_scores(semantic_score, keyword_score),
            "semantic_score": semantic_score,
            "lexical_score": keyword_score,
            "text": text,
            "source": metadata.get("source"),
            "chunk_index": metadata.get("chunk_index"),
            "metadata": {
                "title": metadata.get("title"),
                "section_index": metadata.get("section_index"),
                "chunk_index": metadata.get("section_chunk_index"),
            },
        })

    return rerank_candidates(candidates, top_k)


def answer_with_schgen(question: str, contexts: List[str]) -> str:
    llm = load_llm()
    compact_contexts = [context[:900] for context in contexts[:2]]
    if not contexts:
        prompt = f"Answer this question using your knowledge: {question}"
    else:
        prompt = (
            "Use the following context to answer accurately. "
            "Keep the answer short, precise, and easy to read. "
            "Give one line when the question needs one direct answer. "
            "Use up to 3 bullets only when a list is useful. "
            "Do not include brand names, source names, scores, metadata, or long paragraphs. "
            "If the context does not contain the answer, say you cannot find it."
            f"\n\nContext:\n" + "\n\n".join(compact_contexts) + f"\n\nQuestion: {question}"
        )

    response = llm(prompt, max_new_tokens=120)
    if isinstance(response, list) and response:
        return response[0].get("generated_text", "").strip()
    return str(response)


def generate_rag_answer(question: str, top_k: int = 4, namespace: str = None) -> Dict:
    try:
        matches = query_pinecone(question, top_k=top_k, namespace=namespace)
    except Exception as exc:
        logging.warning("Pinecone RAG unavailable; using local RAG fallback: %s", exc)
        return generate_local_rag_answer(question, top_k=top_k)

    context_texts = [match.get("text") for match in matches if match.get("text")]
    if not context_texts:
        return generate_local_rag_answer(question, top_k=top_k)

    try:
        answer = answer_with_schgen(question, context_texts)
    except Exception as exc:
        logging.warning("RAG LLM unavailable; using retrieved context as answer: %s", exc)
        answer = format_short_rag_answer(question, matches)

    generated_answer = format_user_rag_response(answer, question=question)
    context_answer = format_user_rag_response(format_short_rag_answer(question, matches), question=question)
    normalized_question = question.lower()
    if any(term in normalized_question for term in ["who should", "which doctor", "consult for", "doctor for"]):
        generated_answer = context_answer
    elif "\n-" in context_answer and "\n-" not in generated_answer:
        generated_answer = context_answer

    return {"answer": generated_answer, "matches": matches, "provider": "pinecone"}
