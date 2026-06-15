import re

HEADING_PHRASES = {
    "project overview",
    "core features",
    "key content and features provided",
    "common conditions and advice",
    "patient workflows",
    "doctor workflows",
    "system features",
    "how to consult with doctors",
    "website services provided",
    "how users access these services",
}

METADATA_PATTERNS = [
    r"^\s*(source|sources|metadata|matches?|chunk(?:_|\s*)index|score|rank|provider)\s*[:=]",
    r"^\s*-\s*(source|sources|metadata|matches?|chunk(?:_|\s*)index|score|rank|provider)\s*[:=]",
    r"^\s*(retrieved\s+from|context\s*:|source\s+file\s*:)",
]


def _is_metadata_line(line: str) -> bool:
    if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in METADATA_PATTERNS):
        return True
    return bool(
        re.search(
            r"\b(Careslotly_RAG_Reference\.txt|chunk_index|provider\s*=|score\s*=|semantic_score|lexical_score)\b",
            line,
            flags=re.IGNORECASE,
        )
    )


def _clean_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" -\t\r\n")
    text = re.sub(r"\bCareSlotly\s+helps\s+users\s+", "Users can ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(source|sources|metadata|matches?|chunk(?:_|\s*)index|score|rank|provider)\s*[:=].*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" -\t\r\n")
    text = re.sub(
        r"^(services summary|booking appointments|online consultation|find the right specialist|connect with doctors|message doctor|patient login and registration|patient dashboard|doctor portal|hospital finder|contact support|emergency guidance|account verification|prescription access)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bCareSlotly\s+(helps|provides|supports|connects|allows|offers)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bCareSlotly\b\s*", "", text, flags=re.IGNORECASE).strip(" -\t\r\n")
    return text[:1].upper() + text[1:] if text else ""


def _clip_text(text: str, max_length: int = 190) -> str:
    text = _clean_sentence(text)
    if len(text) <= max_length:
        return text
    clipped = text[:max_length].rsplit(" ", 1)[0].rstrip(" ,;:")
    clipped = re.sub(r"\b(to|for|with|and|or|the|a|an|of|in|on)$", "", clipped, flags=re.IGNORECASE).rstrip(" ,;:")
    return f"{clipped}."


def _needs_points(question: str = "") -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", " ", (question or "").lower())
    return any(
        term in normalized
        for term in [
            "list", "steps", "services", "features", "causes", "remedies", "treatments",
            "what are", "how to", "how do i", "what can i do",
        ]
    )


def _max_points_for_question(question: str = "", default_points: int = 3) -> int:
    normalized = re.sub(r"[^a-z0-9\s]", " ", (question or "").lower())
    if any(term in normalized for term in ["list", "services", "features", "steps"]):
        return min(default_points, 3)
    if any(term in normalized for term in ["what are", "causes", "remedies", "treatments", "what can i do"]):
        return min(default_points, 3)
    return 1


def format_user_rag_response(answer, question: str = "", max_points: int = 3, max_chars: int = 420) -> str:
    if not answer:
        return ""

    cleaned_lines = []
    for raw_line in str(answer).splitlines():
        line = raw_line.strip()
        if not line or _is_metadata_line(line):
            continue
        cleaned_lines.append(line)

    cleaned = " ".join(cleaned_lines).strip()
    if not cleaned:
        return "I could not find enough relevant information."

    bullet_candidates = re.findall(r"(?:^|\s)(?:[-*]|\d+\.)\s+(.+?)(?=\s+(?:[-*]|\d+\.)\s+|$)", cleaned)
    point_limit = _max_points_for_question(question, max_points)
    if bullet_candidates:
        points = [_clip_text(point) for point in bullet_candidates if _clean_sentence(point)]
        points = [point for point in points if point]
        if not points:
            return "I could not find enough relevant information."
        if len(points) == 1:
            return points[0]
        if point_limit == 1 and not _needs_points(question):
            return points[0]
        return "\n".join(f"- {point}" for point in points[:point_limit])

    sentences = [_clean_sentence(sentence) for sentence in re.split(r"(?<=[.!?])\s+", cleaned) if sentence.strip()]
    if len(sentences) == 1 and len(sentences[0]) <= 180:
        return sentences[0]

    if len(sentences) <= 1:
        sentences = [_clean_sentence(part) for part in re.split(r";\s*|,\s+(?=[a-zA-Z])", cleaned) if part.strip()]

    points = [_clip_text(sentence) for sentence in sentences if sentence]
    if not points:
        return "I could not find enough relevant information."
    if len(points) == 1:
        return points[0]
    if point_limit == 1 and not _needs_points(question):
        return points[0]
    response = "\n".join(f"- {point}" for point in points[:point_limit])
    return response[:max_chars].rstrip(" ,;:-")


def extract_short_points(text: str, max_points: int = 3):
    points = []

    for raw_line in text.splitlines():
        inline_bullets = re.findall(r"(?:^|\s)-\s+(.+?)(?=\s+-\s+|$)", raw_line)
        candidate_lines = inline_bullets or [raw_line]

        for candidate_line in candidate_lines:
            line = candidate_line.strip()
            if not line or set(line) <= {"-", "="}:
                continue
            line = re.sub(r"^\d+\.\s+", "", line)
            line = re.sub(r"^[-*]\s+", "", line).strip()
            normalized_line = line.lower().strip(":- ")
            if (
                not line
                or line.endswith(":")
                or normalized_line.startswith("section ")
                or normalized_line.startswith("section:")
                or normalized_line.startswith("use this section")
                or normalized_line in HEADING_PHRASES
                or any(normalized_line.startswith(f"{heading} ") for heading in HEADING_PHRASES)
                or normalized_line.startswith("careslotly rag reference")
            ):
                continue
            if line not in points:
                points.append(line)
            if len(points) >= max_points:
                return points

    return points


def format_short_rag_answer(question: str, matches):
    normalized_question = re.sub(r"[^a-z0-9\s]", "", question.lower()).strip()
    quick_matches = [
        match for match in matches
        if "quick answer" in ((match.get("metadata", {}).get("title") or "").lower())
    ]
    intent_matches = [
        match for match in matches
        if (match.get("metadata", {}).get("title") or "").lower() == "chatbot intent knowledge"
    ]
    context_matches = quick_matches or intent_matches or matches[:3]
    combined_context = "\n".join(match.get("text", "") for match in context_matches[:3])

    if "consult" in normalized_question or "which doctor" in normalized_question or "who should" in normalized_question:
        consult_lines = []
        for line in combined_context.splitlines():
            if re.search(r"\bconsult\s*:", line, flags=re.IGNORECASE):
                consult_lines.append(_clean_sentence(re.sub(r"^.*?\bConsult\s*:\s*", "", line, flags=re.IGNORECASE)))
        consult_lines = [line for line in consult_lines if line]
        if consult_lines:
            return consult_lines[0]

    points = extract_short_points(combined_context)
    if not points:
        return "I could not find enough relevant information."

    return "\n".join(f"- {point}" for point in points[:3])
