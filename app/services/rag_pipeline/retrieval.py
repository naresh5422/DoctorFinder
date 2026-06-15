from app.services.rag_pipeline.config import RERANK_LEXICAL_WEIGHT, RERANK_SEMANTIC_WEIGHT
from app.services.rag_pipeline.text_processing import tokenize


def lexical_score(query_tokens, text, metadata=None):
    if not query_tokens:
        return 0.0

    metadata = metadata or {}
    text_tokens = set(tokenize(text))
    metadata_tokens = set(metadata.get("keywords", []))
    title_tokens = set(tokenize(metadata.get("title", "")))

    matched = set(query_tokens) & (text_tokens | metadata_tokens)
    title_matches = set(query_tokens) & title_tokens
    section_position = metadata.get("chunk_index", 0) or 0
    early_section_boost = 0.5 / (section_position + 1) if title_matches else 0.0
    intent_boost = 0.0
    title = (metadata.get("title") or "").lower()
    if title == "chatbot intent knowledge":
        intent_terms = {"service", "services", "book", "booking", "appointment", "login", "register", "dashboard", "profile", "hospital", "message", "emergency", "contact", "support"}
        if set(query_tokens) & intent_terms:
            intent_boost = 0.35
    if "quick answer" in title and (set(query_tokens) & {"service", "services", "website", "provide"}):
        intent_boost += 0.5

    return (
        len(matched) / max(len(set(query_tokens)), 1)
        + (0.15 * len(title_matches))
        + early_section_boost
        + intent_boost
    )


def combine_scores(semantic_score: float, keyword_score: float) -> float:
    return (RERANK_SEMANTIC_WEIGHT * semantic_score) + (RERANK_LEXICAL_WEIGHT * keyword_score)


def select_diverse_results(candidates, top_k):
    selected = []
    selected_sections = set()

    for candidate in candidates:
        section_index = candidate.get("metadata", {}).get("section_index")
        if section_index not in selected_sections:
            selected.append(candidate)
            selected_sections.add(section_index)
        if len(selected) >= top_k:
            return selected

    for candidate in candidates:
        if candidate not in selected:
            selected.append(candidate)
        if len(selected) >= top_k:
            break

    return selected


def rerank_candidates(candidates, top_k):
    candidates.sort(key=lambda result: result["score"], reverse=True)
    results = select_diverse_results(candidates, min(top_k, len(candidates)))
    for rank, result in enumerate(results, start=1):
        result["rank"] = rank
    return results
