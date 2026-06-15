import os
import re

import numpy as np

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")

from sentence_transformers import SentenceTransformer, util

from app.services.rag_pipeline.answering import format_short_rag_answer, format_user_rag_response
from app.services.rag_pipeline.config import EMBEDDING_MODEL_NAME, RAG_SOURCE_FILE
from app.services.rag_pipeline.retrieval import combine_scores, lexical_score, rerank_candidates
from app.services.rag_pipeline.text_processing import build_rag_chunks, expand_query, tokenize

RAG_MODEL = None
RAG_DATA = {
    "chunks": [],
    "metadata": [],
    "embeddings": None,
    "source_path": RAG_SOURCE_FILE,
}


def load_rag_data(model=None, source_file: str = None):
    global RAG_MODEL, RAG_DATA
    source_file = source_file or RAG_SOURCE_FILE

    if not os.path.exists(source_file):
        raise FileNotFoundError(f"RAG source file not found: {source_file}")

    if model is not None:
        RAG_MODEL = model
    elif RAG_MODEL is None:
        RAG_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)

    with open(source_file, "r", encoding="utf-8") as source:
        document_text = source.read()

    chunk_records = build_rag_chunks(document_text)
    if not chunk_records:
        raise ValueError("RAG source file contains no text to index.")

    chunks = [record["text"] for record in chunk_records]
    embeddings = RAG_MODEL.encode(chunks, convert_to_tensor=True, show_progress_bar=False)
    RAG_DATA = {
        "chunks": chunks,
        "metadata": chunk_records,
        "embeddings": embeddings,
        "source_path": source_file,
    }
    return RAG_DATA


def query_rag(question: str, top_k: int = 4):
    if not question or not question.strip():
        return []

    if not RAG_DATA["chunks"] or RAG_DATA["embeddings"] is None:
        load_rag_data()

    expanded_question = expand_query(question)
    query_embedding = RAG_MODEL.encode(expanded_question, convert_to_tensor=True)
    cosine_scores = util.cos_sim(query_embedding, RAG_DATA["embeddings"])[0]
    scores = cosine_scores.detach().cpu().numpy()
    query_tokens = tokenize(expanded_question)
    pool_size = min(max(top_k * 5, top_k), len(RAG_DATA["chunks"]))
    top_indices = np.argsort(scores)[::-1][:pool_size]

    candidates = []
    for idx in top_indices:
        idx = int(idx)
        metadata = RAG_DATA.get("metadata", [{}] * len(RAG_DATA["chunks"]))[idx]
        semantic_score = float(scores[idx])
        keyword_score = lexical_score(query_tokens, RAG_DATA["chunks"][idx], metadata)
        candidates.append({
            "score": combine_scores(semantic_score, keyword_score),
            "semantic_score": semantic_score,
            "lexical_score": keyword_score,
            "text": RAG_DATA["chunks"][idx],
            "source": os.path.basename(RAG_DATA["source_path"]),
            "metadata": {
                "title": metadata.get("title"),
                "section_index": metadata.get("section_index"),
                "chunk_index": metadata.get("chunk_index"),
            },
        })

    return rerank_candidates(candidates, top_k)


def generate_local_rag_answer(question: str, top_k: int = 4, min_score: float = 0.25):
    matches = [
        match for match in query_rag(question, top_k=top_k)
        if match.get("score", 0) >= min_score
    ]

    if not matches:
        return {
            "answer": "I could not find enough relevant information.",
            "matches": [],
            "provider": "local",
        }

    normalized_question = re.sub(r"[^a-z0-9\s]", "", question.lower()).strip()
    if "doctor" in normalized_question and any(
        term in normalized_question for term in ["connect", "consult", "message", "chat"]
    ):
        matches.sort(
            key=lambda match: (
                "how to consult with doctors" not in match.get("text", "").lower(),
                "patient workflows" not in match.get("text", "").lower(),
                -match.get("score", 0),
            )
        )

    return {
        "answer": format_user_rag_response(format_short_rag_answer(question, matches), question=question),
        "matches": matches,
        "provider": "local",
    }
