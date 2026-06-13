"""
ORION Intent Router — Classifies incoming messages by intent.
Uses Groq for classification. Falls back to keyword matching.
"""

import os, re
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

INTENTS = [
    "sales_inquiry",      # Asking about services, pricing, hiring
    "support_request",    # Having issues, need help, complaints
    "project_discussion", # Already working on a project, discussing details
    "interview_scheduling", # Setting up calls/meetings
    "general",           # General questions, greetings, etc.
    "escalation",        # Angry client, needs human urgently
]


def classify_intent(message, history_context=""):
    """Classify a message into one of the intent categories."""
    if not GROQ_API_KEY:
        return _keyword_fallback(message)

    system = (
        "Classify the following client message into exactly ONE intent:\n"
        "- sales_inquiry: Asking about services, pricing, samples, wanting to hire\n"
        "- support_request: Having technical issues, delivery problems, revisions needed\n"
        "- project_discussion: Already hired, discussing project details, milestones, timelines\n"
        "- interview_scheduling: Setting up calls, meetings, asking about availability\n"
        "- escalation: Angry, urgent, refund requests, complaints, needs human NOW\n"
        "- general: Greetings, casual chat, thanks, anything else\n\n"
        "Reply with ONLY the intent name, nothing else."
    )

    full_message = f"{history_context}\n---\n{message}" if history_context else message

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": full_message[:500]},
                ],
                "temperature": 0.1,
                "max_tokens": 20,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            intent = resp.json()["choices"][0]["message"]["content"].strip().lower()
            if intent in INTENTS:
                return intent
    except:
        pass

    return _keyword_fallback(message)


def _keyword_fallback(message):
    """Keyword-based fallback when Groq is unavailable."""
    m = message.lower()

    if any(w in m for w in ["angry", "refund", "complaint", "cancel", "disappointed", "poor", "terrible"]):
        return "escalation"

    if any(w in m for w in ["price", "cost", "how much", "services", "hire", "quote", "sample"]):
        return "sales_inquiry"

    if any(w in m for w in ["not working", "bug", "issue", "problem", "error", "wrong", "fix"]):
        return "support_request"

    if any(w in m for w in ["call", "meeting", "available", "schedule", "discuss", "when", "time"]):
        return "interview_scheduling"

    if any(w in m for w in ["milestone", "revision", "delivery", "deadline", "project", "progress"]):
        return "project_discussion"

    return "general"
