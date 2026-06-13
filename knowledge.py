"""
ORION Knowledge Base — RAG system for company context
Loads knowledge/*.md files and retrieves relevant sections for AI context.
"""

import os, re, json
from pathlib import Path

ROOT = Path(__file__).parent
KNOWLEDGE_DIR = ROOT / "knowledge"
_cached_knowledge = None


def load_knowledge():
    """Load all knowledge files into memory."""
    global _cached_knowledge
    if _cached_knowledge:
        return _cached_knowledge

    docs = {}
    if KNOWLEDGE_DIR.exists():
        for f in sorted(KNOWLEDGE_DIR.glob("*.md")):
            name = f.stem
            docs[name] = f.read_text(encoding="utf-8")
    _cached_knowledge = docs
    return docs


def search_knowledge(query, max_chars=2000):
    """Search knowledge base for context relevant to a query.
    Returns matched sections as plain text.
    """
    docs = load_knowledge()
    if not docs:
        return ""

    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))

    scored_sections = []

    for name, text in docs.items():
        lines = text.split("\n")
        current_section = {"name": name, "heading": "", "text": "", "score": 0}

        for line in lines:
            if line.startswith("#"):
                if current_section["text"].strip():
                    scored_sections.append(current_section)
                heading = line.strip("# ")
                current_section = {"name": name, "heading": heading, "text": line + "\n", "score": 0}
            else:
                current_section["text"] += line + "\n"

            # Score this section
            line_lower = line.lower()
            for word in query_words:
                if word in line_lower:
                    current_section["score"] += 1

        if current_section["text"].strip():
            scored_sections.append(current_section)

    # Sort by relevance score
    scored_sections.sort(key=lambda x: x["score"], reverse=True)

    # Build context string from top sections
    result = []
    char_count = 0
    for sec in scored_sections:
        if sec["score"] == 0:
            continue
        text = f"[{sec['name']}] {sec['heading']}\n{sec['text'].strip()}\n\n"
        if char_count + len(text) > max_chars:
            break
        result.append(text)
        char_count += len(text)

    # If no relevant sections found, return summaries
    if not result:
        for name, text in docs.items():
            first_line = text.split("\n")[0].strip("# ")
            result.append(f"[{name}] {first_line}")

    return "\n".join(result)


def get_context_for_intent(intent, query):
    """Get tailored knowledge context based on intent type."""
    docs = load_knowledge()
    if intent == "sales_inquiry":
        return docs.get("services", "") + "\n" + docs.get("pricing", "")
    elif intent == "support_request":
        return docs.get("faq", "") + "\n" + docs.get("company", "")
    elif intent == "project_discussion":
        return docs.get("services", "") + "\n" + docs.get("company", "")
    else:
        return search_knowledge(query)
