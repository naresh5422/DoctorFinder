import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RAG_SOURCE_FILE = os.path.join(ROOT_DIR, "Careslotly_RAG_Reference.txt")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
LLM_MODEL_NAME = os.getenv("RAG_LLM_MODEL_NAME", "google/flan-t5-small")

CHUNK_SIZE = 140
CHUNK_OVERLAP = 30
RERANK_SEMANTIC_WEIGHT = 0.75
RERANK_LEXICAL_WEIGHT = 0.25
MAX_RETRIEVAL_POOL = 20

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from", "how", "i",
    "in", "is", "it", "me", "my", "need", "of", "on", "or", "the", "to", "what", "when", "where",
    "which", "who", "with", "you",
}

QUERY_EXPANSIONS = {
    "appointment": ["booking", "slot", "schedule", "consultation"],
    "book": ["appointment", "slot", "schedule"],
    "cause": ["causes", "caused", "reason", "risk factors"],
    "doctor": ["specialist", "consult", "physician"],
    "emergency": ["urgent", "helpline", "ambulance", "112"],
    "helpline": ["emergency", "number", "support", "112"],
    "pet": ["animal", "veterinary", "vet"],
    "remedy": ["remedies", "self-care", "first aid", "treatment"],
    "service": ["services", "features", "website", "portal"],
    "symptom": ["symptoms", "disease", "condition"],
    "vet": ["veterinary", "animal", "pet"],
}
