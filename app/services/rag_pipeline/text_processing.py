import re

from app.services.rag_pipeline.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    QUERY_EXPANSIONS,
    STOPWORDS,
)


def normalize_search_text(text: str) -> str:
    text = re.sub(r"[^a-z0-9\s-]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str):
    return [
        token for token in normalize_search_text(text).split()
        if len(token) > 2 and token not in STOPWORDS
    ]


def expand_query(question: str) -> str:
    tokens = tokenize(question)
    expanded_terms = []
    for token in tokens:
        expanded_terms.append(token)
        expanded_terms.extend(QUERY_EXPANSIONS.get(token, []))
    return " ".join(dict.fromkeys(expanded_terms)) or question


def extract_sections(text: str):
    lines = text.splitlines()
    sections = []
    current_title = "General"
    current_lines = []
    index = 0

    while index < len(lines):
        line = lines[index].rstrip()
        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
        is_heading = line.strip() and len(next_line) >= 3 and set(next_line) <= {"-", "="}

        if is_heading:
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line.strip()
            current_lines = []
            index += 2
            continue

        current_lines.append(line)
        index += 1

    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))

    return [(title, body) for title, body in sections if body]


def split_section_text(title: str, body: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    chunks = []

    for paragraph in paragraphs:
        words = paragraph.split()
        if len(words) <= chunk_size:
            chunks.append(paragraph)
            continue

        start = 0
        while start < len(words):
            chunk_words = words[start:start + chunk_size]
            chunks.append(" ".join(chunk_words).strip())
            start += chunk_size - overlap

    return chunks


def build_rag_chunks(text: str):
    chunks = []
    for section_index, (title, body) in enumerate(extract_sections(text)):
        for chunk_index, chunk in enumerate(split_section_text(title, body)):
            chunk_text = f"Section: {title}\n{chunk}"
            tokens = tokenize(f"{title} {chunk}")
            chunks.append({
                "text": chunk_text,
                "title": title,
                "section_index": section_index,
                "chunk_index": chunk_index,
                "keywords": sorted(set(tokens))[:40],
            })
    return chunks


def split_text_into_chunks(text: str):
    return [chunk["text"] for chunk in build_rag_chunks(text)]
