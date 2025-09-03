import os
import json
import time
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


MEMORY_FILE = Path.home() / "OneDrive" / "Documents" / "ai_memory.json"
MAX_GENERAL_MEMORIES = 100
MAX_CONVERSATION_MEMORIES = 50  # A reasonable limit for conversation history
CONVERSATION_MEMORY_KEY = "conversation"
GENERAL_MEMORY_KEY = "general"

def load_memories():
    """Loads and sanitizes memories from the JSON file."""
    if not os.path.isfile(MEMORY_FILE):
        return {}

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}

            # Sanitize timestamp fields
            for section in ("general", "conversation"):
                if section in data:
                    valid = []
                    for m in data[section]:
                        ts = m.get("timestamp")
                        if isinstance(ts, (int, float)):
                            valid.append(m)
                        else:
                            # Auto-fix or skip invalid timestamps
                            m["timestamp"] = time.time()
                            valid.append(m)
                    data[section] = valid

            return data

    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_memories(memories):
    for section in ("general", "conversation"):
        if section in memories:
            memories[section] = sorted(
                memories[section], key=lambda m: -(m.get("timestamp") or 0)
            )
    MEMORY_FILE.write_text(json.dumps(memories, indent=2, ensure_ascii=False), encoding="utf-8")



def add_memory(entry: str):
    memories = load_memories()
    if GENERAL_MEMORY_KEY not in memories:
        memories[GENERAL_MEMORY_KEY] = []

    memories[GENERAL_MEMORY_KEY].append({
        "timestamp": time.time(),  # epoch float
        "entry": entry
    })

    memories[GENERAL_MEMORY_KEY] = memories[GENERAL_MEMORY_KEY][-MAX_GENERAL_MEMORIES:]
    save_memories(memories)


def add_conversation_memory(user_query: str, ai_response: str):
    memories = load_memories()
    if CONVERSATION_MEMORY_KEY not in memories:
        memories[CONVERSATION_MEMORY_KEY] = []

    memories[CONVERSATION_MEMORY_KEY].append({
        "timestamp": time.time(),
        "user": user_query,
        "ai": ai_response
    })

    # Keep only the most recent N
    memories[CONVERSATION_MEMORY_KEY] = memories[CONVERSATION_MEMORY_KEY][-MAX_CONVERSATION_MEMORIES:]

    save_memories(memories)

    memories[CONVERSATION_MEMORY_KEY] = memories[CONVERSATION_MEMORY_KEY][-MAX_CONVERSATION_MEMORIES:]
    save_memories(memories)
    print(f"[Memory] Added conversation: {user_query} → {ai_response[:30]}...")



def _retrieve_with_tfidf(documents, query, top_n):
    """
    Helper function to retrieve top_n document indices using TF-IDF and cosine similarity.
    `documents` is a list of strings.
    """
    if not documents or not query.strip():
        return []

    try:
        vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
        tfidf_matrix = vectorizer.fit_transform(documents)
        query_vector = vectorizer.transform([query])
        cosine_similarities = cosine_similarity(query_vector, tfidf_matrix).flatten()
        
        # Get indices of top_n most similar documents, sorted by similarity
        relevant_indices = cosine_similarities.argsort()[-top_n:][::-1]
        
        # Filter out results with a similarity of 0 to avoid irrelevant matches
        return [idx for idx in relevant_indices if cosine_similarities[idx] > 0]

    except Exception:
        # Fallback to simple keyword matching in case of any TF-IDF error (e.g., empty vocabulary)
        terms = set(query.lower().split())
        scored = []
        for i, doc in enumerate(documents):
            score = sum(1 for t in terms if t in doc.lower())
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [i for _, i in scored[:top_n]]

def retrieve_relevant(query: str, top_n: int = 3):
    """
    Retrieves relevant GENERAL memories using TF-IDF.
    Returns up to top_n memories with highest score.
    """
    memories = load_memories()
    general_mems = memories.get(GENERAL_MEMORY_KEY, [])
    
    if not general_mems:
        return []

    documents = [mem.get("entry", "") for mem in general_mems]
    relevant_indices = _retrieve_with_tfidf(documents, query, top_n)
    return [general_mems[i] for i in relevant_indices]

def retrieve_conversation_memory(query: str, top_n: int = 3):
    """
    Retrieves relevant CONVERSATION memories using TF-IDF.
    Returns up to top_n memories with highest score.
    """
    memories = load_memories()
    conversation_mems = memories.get(CONVERSATION_MEMORY_KEY, [])

    if not conversation_mems:
        return []

    documents = [(mem.get("user", "") + " " + mem.get("ai", "")).strip() for mem in conversation_mems]
    relevant_indices = _retrieve_with_tfidf(documents, query, top_n)
    return [conversation_mems[i] for i in relevant_indices]

def get_all_conversation_history(limit=15):
    try:
        memories = load_memories()
        convos = memories.get(CONVERSATION_MEMORY_KEY, [])
        return convos if limit is None else convos[-limit:]
    except:
        return sorted(convos, key=lambda m: m.get("timestamp", 0), reverse=True)[:limit]


    