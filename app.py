"""
ORION Universal Chat Agent — 24/7 Client Communication System
Multi-platform: Freelancer, Email, WhatsApp
Features: RAG Knowledge Base, Intent Routing, Escalation, Dashboard
"""

import os, json, requests, hashlib, time
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ─── Config ────────────────────────────────────────────────
FREELANCER_API = "https://www.freelancer.com/api"
ACCESS_TOKEN = os.getenv("FREELANCER_ACCESS_TOKEN")
FREELANCER_USER_ID = os.getenv("FREELANCER_USER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
responded_threads = set()

# ─── Imports ───────────────────────────────────────────────
from knowledge import search_knowledge, get_context_for_intent
from intent import classify_intent

# ─── Groq ──────────────────────────────────────────────────
def groq_reply(system, message, temperature=0.7, max_tokens=400):
    if not GROQ_API_KEY:
        return None
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=25,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Groq] Error: {e}")
    return None


# ─── Supabase ──────────────────────────────────────────────
SUPABASE_HEADERS = {}
if SUPABASE_URL and SUPABASE_KEY:
    SUPABASE_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def supabase_save(table, data):
    if not SUPABASE_HEADERS:
        return
    try:
        requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=SUPABASE_HEADERS, json=data, timeout=10)
    except Exception as e:
        print(f"[Supabase] Save error: {e}")


def supabase_query(table, params):
    if not SUPABASE_HEADERS:
        return []
    try:
        resp = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=SUPABASE_HEADERS, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[Supabase] Query error: {e}")
    return []


def save_message(conversation_id, role, content, platform, project_id=None, intent=None):
    data = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "project_id": str(project_id) if project_id else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Only add platform/intent if the columns exist (graceful degradation)
    try:
        test = requests.get(f"{SUPABASE_URL}/rest/v1/messages", headers=SUPABASE_HEADERS, params={"limit": 1}, timeout=5)
        if test.status_code == 200:
            data["platform"] = platform
            if intent:
                data["intent"] = intent
    except:
        pass
    supabase_save("messages", data)


def get_history(conversation_id, limit=10):
    rows = supabase_query("messages", {
        "conversation_id": f"eq.{conversation_id}",
        "order": "created_at.asc",
        "limit": limit,
    })
    return rows


# ─── Response Engine ───────────────────────────────────────
SYSTEM_TEMPLATE = """You are Noman — a real freelancer, not a chatbot. You're responding to a client message on Freelancer.

HOW TO SOUND HUMAN:
- Write like a real person having a conversation. Vary your sentence length.
- Use contractions naturally: I'll, I'm, I've, I'd, that's, don't, won't, can't, it's
- Occasional filler words are fine: "well", "honestly", "actually", "to be honest"
- Don't be overly formal. You're professional, not robotic.
- Never, ever use these phrases: "rest assured", "I look forward to", "please don't hesitate", "I am writing to", "I would be happy to", "I trust this"
- If the client asks about pricing, give specific numbers, not vague ranges.
- If they want to book a call, suggest a specific time.
- If they're unhappy, apologize genuinely and propose a fix.
- Keep it tight. 100-150 words unless they asked a detailed question.

CLIENT INTENT: {intent}

YOUR COMPANY INFO (use this to answer accurately):
{knowledge}

CONVERSATION HISTORY:
{history}

Now respond naturally to the client's latest message:"""


def generate_response(message_text, intent, history_text="", query_for_knowledge=None):
    """Generate a contextually aware response using RAG + Intent."""
    search_query = query_for_knowledge or message_text
    knowledge = get_context_for_intent(intent, search_query)

    system = SYSTEM_TEMPLATE.format(
        intent=intent.replace("_", " ").title(),
        knowledge=knowledge[:2000] if knowledge else "No specific context available. Respond naturally.",
        history=history_text[:1000] if history_text else "No prior conversation.",
    )

    return groq_reply(system, message_text) or generic_fallback(intent)


def generic_fallback(intent):
    responses = {
        "sales_inquiry": "Thanks for your interest! I'd be happy to discuss your project. Could you share more details about what you need?",
        "support_request": "I understand you're having an issue. Let me look into this and get back to you shortly. Can you describe the problem in more detail?",
        "project_discussion": "Thanks for the update. Let me review what you've shared and get back to you with the next steps.",
        "interview_scheduling": "I'm available to discuss this further. What time works best for you? I'm in PKT (UTC+5).",
        "escalation": "I apologize for the frustration. Let me look into this immediately and find a solution for you.",
        "general": "Thanks for your message. How can I help you today?",
    }
    return responses.get(intent, "Thanks for reaching out. I'll get back to you shortly.")


# ─── Platform Connectors ──────────────────────────────────

def handle_freelancer_message(thread_id, message_text, sender_id, project_id=None):
    """Process and respond to a Freelancer message."""
    if str(sender_id) == str(FREELANCER_USER_ID):
        return None

    conversation_id = hashlib.md5(str(thread_id).encode()).hexdigest()
    history = get_history(conversation_id)
    history_text = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in history[-5:]])
    intent = classify_intent(message_text, history_text)

    reply = generate_response(message_text, intent, history_text)

    save_message(conversation_id, "client", message_text, "freelancer", project_id, intent)
    save_message(conversation_id, "agent", reply, "freelancer", project_id, intent)

    # Send reply to Freelancer
    try:
        r = requests.post(
            f"{FREELANCER_API}/messages/0.1/threads/{thread_id}",
            headers=HEADERS,
            json={"message": reply},
            timeout=15,
        )
        success = r.status_code in (200, 201)
    except:
        success = False

    return {"conversation_id": conversation_id, "intent": intent, "reply": reply, "success": success}


# ─── Routes ────────────────────────────────────────────────

@app.route("/")
def home():
    return jsonify({
        "agent": "ORION Universal Chat Agent",
        "version": "2.0",
        "status": "online",
        "platforms": ["freelancer", "email", "whatsapp"],
        "features": ["rag_knowledge_base", "intent_routing", "escalation", "multi_platform"],
        "time": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "groq": bool(GROQ_API_KEY),
        "freelancer_token": bool(ACCESS_TOKEN),
        "supabase": bool(SUPABASE_URL and SUPABASE_KEY),
        "knowledge_files": len(search_knowledge("").split("\n")) if search_knowledge("") else 0,
    })


@app.route("/webhook/freelancer", methods=["POST"])
def freelancer_webhook():
    """Receive Freelancer.com message notifications."""
    data = request.json
    if not data:
        return jsonify({"error": "no data"}), 400

    thread_id = data.get("thread_id")
    message_text = data.get("message", "")
    sender_id = data.get("from_user_id")
    project_id = data.get("project_id")

    if not thread_id or not message_text:
        return jsonify({"error": "missing fields"}), 400

    result = handle_freelancer_message(thread_id, message_text, sender_id, project_id)
    if result is None:
        return jsonify({"status": "own_message_skipped"})

    return jsonify(result)


@app.route("/poll", methods=["GET"])
def poll():
    """Poll Freelancer threads for new unread messages."""
    try:
        resp = requests.get(f"{FREELANCER_API}/messages/0.1/threads/?limit=30", headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return jsonify({"error": "freelancer_api_error", "checked": 0, "replied": 0})
        threads = resp.json().get("result", {}).get("threads", [])
    except Exception as e:
        return jsonify({"error": str(e), "checked": 0, "replied": 0})

    results = []
    for t in threads:
        tid = t.get("id")
        if not tid or tid in responded_threads:
            continue

        is_read = t.get("is_read", True)
        folder = t.get("folder", "inbox")
        if is_read or folder != "inbox":
            continue

        thread_obj = t.get("thread", {})
        msg = thread_obj.get("message")
        if not msg:
            continue

        sender_id = msg.get("from_user_id")
        message_text = msg.get("text", "")
        project_id = thread_obj.get("context", {}).get("id")

        if str(sender_id) == str(FREELANCER_USER_ID) or not message_text:
            continue

        result = handle_freelancer_message(tid, message_text, sender_id, project_id)
        if result:
            responded_threads.add(tid)
            results.append(result)

    return jsonify({"checked": len(threads), "replied": len(results), "results": results})


@app.route("/api/message", methods=["POST"])
def api_message():
    """Generic API endpoint for sending messages (for web widget, test, etc.)"""
    data = request.json
    if not data or not data.get("message"):
        return jsonify({"error": "message required"}), 400

    message_text = data["message"]
    conversation_id = data.get("conversation_id") or hashlib.md5(
        (message_text + str(time.time())).encode()
    ).hexdigest()
    platform = data.get("platform", "api")
    project_id = data.get("project_id")

    history = get_history(conversation_id)
    history_text = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in history[-5:]])
    intent = classify_intent(message_text, history_text)

    reply = generate_response(message_text, intent, history_text)

    save_message(conversation_id, "client", message_text, platform, project_id, intent)
    save_message(conversation_id, "agent", reply, platform, project_id, intent)

    return jsonify({
        "reply": reply,
        "intent": intent,
        "conversation_id": conversation_id,
    })


@app.route("/dashboard")
def dashboard():
    """Simple conversation dashboard."""
    conversations = supabase_query("messages", {
        "select": "conversation_id,platform,count=conversation_id",
        "order": "created_at.desc",
        "limit": 50,
    })
    html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>ORION Chat Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Inter,sans-serif;background:#0b1919;color:#e0e0e0;padding:20px}
h1{color:#39AEA9;font-family:Orbitron,sans-serif;margin-bottom:20px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:30px}
.stat-card{background:#0f2424;padding:15px;border-radius:8px;border:1px solid #1a3a3a}
.stat-card .num{font-size:28px;color:#39AEA9;font-weight:700}
.stat-card .label{font-size:12px;color:#6b9e9e;margin-top:4px}
table{width:100%;border-collapse:collapse;background:#0f2424;border-radius:8px;overflow:hidden}
th{text-align:left;padding:10px 12px;color:#6b9e9e;font-size:12px;border-bottom:1px solid #1a3a3a}
td{padding:10px 12px;border-bottom:1px solid #1a3a3a;font-size:14px}
tr:hover{background:#132929}
.platform-tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;background:#1a3a3a}
.platform-freelancer{background:#1a3a3a;color:#39AEA9}
.platform-email{background:#3a1a3a;color:#A95EAE}
.platform-whatsapp{background:#1a3a1a;color:#5EAE5E}
</style></head>
<body>
<h1>ORION Chat Dashboard</h1>
<div class="stats" id="stats">Loading...</div>
<table>
<thead><tr><th>Conversation</th><th>Platform</th><th>Last Activity</th><th>Messages</th></tr></thead>
<tbody id="conversations">Loading...</tbody>
</table>
<script>
async function load(){
  const r=await fetch('/api/conversations');
  const d=await r.json();
  let stats='<div class="stat-card"><div class="num">'+d.total+'</div><div class="label">Total Messages</div></div>'+
    '<div class="stat-card"><div class="num">'+d.conversations+'</div><div class="label">Conversations</div></div>'+
    '<div class="stat-card"><div class="num">'+d.platforms.freelancer+'</div><div class="label">Freelancer</div></div>'+
    '<div class="stat-card"><div class="num">'+d.platforms.email+'</div><div class="label">Email</div></div>'+
    '<div class="stat-card"><div class="num">'+d.platforms.whatsapp+'</div><div class="label">WhatsApp</div></div>';
  document.getElementById('stats').innerHTML=stats;
  let rows='';
  for(const c of d.recent){
    rows+='<tr><td>'+c.conversation_id.substr(0,12)+'...</td><td><span class="platform-tag platform-'+c.platform+'">'+c.platform+'</span></td><td>'+c.last_message+'</td><td>'+c.count+'</td></tr>';
  }
  document.getElementById('conversations').innerHTML=rows;
}
load();
setInterval(load,30000);
</script>
</body></html>"""
    return render_template_string(html)


@app.route("/api/conversations")
def api_conversations():
    """Get conversation stats for dashboard."""
    rows = supabase_query("messages", {
        "select": "*",
        "order": "created_at.desc",
        "limit": 100,
    })

    platforms = {"freelancer": 0, "email": 0, "whatsapp": 0, "api": 0}
    convos = {}
    for r in rows:
        p = r.get("platform", "api")
        platforms[p] = platforms.get(p, 0) + 1
        cid = r.get("conversation_id")
        if cid not in convos:
            convos[cid] = {"count": 0, "last_message": r.get("created_at", ""), "platform": p}
        convos[cid]["count"] += 1

    recent = sorted(convos.items(), key=lambda x: x[1]["last_message"], reverse=True)[:20]
    return jsonify({
        "total": len(rows),
        "conversations": len(convos),
        "platforms": platforms,
        "recent": [{"conversation_id": cid, **v} for cid, v in recent],
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"ORION Chat Agent v2 starting on port {port}")
    print(f"  Groq: {'ON' if GROQ_API_KEY else 'OFF'}")
    print(f"  Freelancer: {'ON' if ACCESS_TOKEN else 'OFF'}")
    print(f"  Supabase: {'ON' if SUPABASE_URL else 'OFF'}")
    print(f"  Knowledge files: {len(search_knowledge('').split(chr(10))) if search_knowledge('') else 0}")
    app.run(host="0.0.0.0", port=port, debug=False)
