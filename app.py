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


# ─── Email Connector ───────────────────────────────────────
from connectors_email import check_email, send_email, EMAIL_ENABLED, EMAIL_ADDRESS, responded_email_ids

responded_email_subjects = set()

def handle_email_message(email_data):
    """Process and respond to an email message."""
    thread_key = email_data["thread_key"]
    conversation_id = hashlib.md5(("email:" + thread_key).encode()).hexdigest()

    history = get_history(conversation_id)
    history_text = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in history[-5:]])
    intent = classify_intent(email_data["body"], history_text)

    reply = generate_response(email_data["body"], intent, history_text)

    save_message(conversation_id, "client", email_data["body"], "email", None, intent)
    save_message(conversation_id, "agent", reply, "email", None, intent)

    reply_subject = email_data["subject"]
    if not reply_subject.lower().startswith("re:"):
        reply_subject = "Re: " + reply_subject

    success = send_email(
        to_addr=email_data["sender_email"],
        subject=reply_subject,
        body=reply,
        in_reply_to=email_data.get("message_id"),
    )

    return {
        "conversation_id": conversation_id,
        "intent": intent,
        "reply": reply,
        "success": success,
        "to": email_data["sender_email"],
        "subject": reply_subject,
    }

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
        "email": EMAIL_ENABLED,
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


@app.route("/poll/email", methods=["GET"])
def poll_email():
    """Poll Gmail inbox for new client emails."""
    if not EMAIL_ENABLED:
        return jsonify({"error": "email_disabled", "checked": 0, "replied": 0})

    emails = check_email()
    results = []
    for em in emails:
        if em["uid"] in responded_email_ids:
            continue
        thread_key = em["thread_key"]
        if thread_key in responded_email_subjects:
            continue
        result = handle_email_message(em)
        if result:
            responded_email_ids.add(em["uid"])
            responded_email_subjects.add(thread_key)
            results.append(result)

    return jsonify({"checked": len(emails), "replied": len(results), "results": results})


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
    """Multi-page ORION Command Center dashboard."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ORION Command Center</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&family=Orbitron:wght@400;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Inter,sans-serif;background:#0b1919;color:#c8d8d8;min-height:100vh}
.nav{display:flex;gap:0;background:#0f2424;border-bottom:1px solid #1a3a3a;padding:0 20px;position:sticky;top:0;z-index:100}
.nav a{padding:16px 24px;color:#6b9e9e;text-decoration:none;font-size:13px;font-weight:500;letter-spacing:0.5px;border-bottom:2px solid transparent;transition:all .2s}
.nav a:hover{color:#39AEA9;background:#132929}
.nav a.active{color:#39AEA9;border-bottom-color:#39AEA9}
.nav .brand{font-family:Orbitron,sans-serif;font-size:16px;color:#39AEA9;padding:16px 24px 16px 0;margin-right:auto;font-weight:700}
.main{padding:24px;max-width:1400px;margin:0 auto}
.page{display:none}
.page.active{display:block}
h1{font-family:Orbitron,sans-serif;color:#39AEA9;font-size:22px;margin-bottom:20px;font-weight:400}
h2{color:#e0e0e0;font-size:15px;margin-bottom:12px;font-weight:500}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:24px}
.stat-card{background:#0f2424;padding:16px;border-radius:8px;border:1px solid #1a3a3a;transition:border-color .2s}
.stat-card:hover{border-color:#39AEA9}
.stat-card .num{font-size:30px;color:#39AEA9;font-weight:700;font-family:Orbitron,sans-serif}
.stat-card .label{font-size:11px;color:#6b9e9e;margin-top:4px;text-transform:uppercase;letter-spacing:1px}
.stat-card .sub{font-size:12px;color:#4a7a7a;margin-top:2px}
.card{background:#0f2424;border-radius:8px;border:1px solid #1a3a3a;padding:16px;margin-bottom:16px}
.card h3{color:#39AEA9;font-size:13px;margin-bottom:10px;text-transform:uppercase;letter-spacing:1px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px 10px;color:#6b9e9e;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid #1a3a3a;font-weight:500}
td{padding:8px 10px;border-bottom:1px solid #1a3a3a}
tr:hover{background:#132929}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:500;text-transform:uppercase}
.badge-fl{background:#1a3a3a;color:#39AEA9}
.badge-em{background:#3a1a3a;color:#A95EAE}
.badge-wa{background:#1a3a1a;color:#5EAE5E}
.badge-api{background:#3a3a1a;color:#AEAE5E}
.badge-sent{background:#1a2a3a;color:#5e8eae}
.badge-replied{background:#1a3a2a;color:#5eae8e}
.badge-won{background:#1a3a1a;color:#5ece5e}
.badge-lost{background:#3a1a1a;color:#ce5e5e}
.empty{color:#4a7a7a;font-size:13px;padding:20px;text-align:center}
.loading{color:#4a7a7a;font-size:13px;padding:20px;text-align:center}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:800px){.grid-2{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="nav">
  <div class="brand">ORION</div>
  <a href="#" class="active" data-page="overview">Overview</a>
  <a href="#" data-page="freelancing">Freelancing</a>
  <a href="#" data-page="chat">Chat Log</a>
  <a href="#" data-page="settings">Settings</a>
</div>
<div class="main">

<div id="page-overview" class="page active">
  <h1>Command Center</h1>
  <div class="stats-grid" id="ov-stats"></div>
  <div class="grid-2">
    <div class="card">
      <h3>Recent Conversations</h3>
      <table><thead><tr><th>ID</th><th>Platform</th><th>Messages</th><th>Last</th></tr></thead><tbody id="ov-convos"></tbody></table>
    </div>
    <div class="card">
      <h3>Platform Distribution</h3>
      <div id="ov-platforms"></div>
    </div>
  </div>
</div>

<div id="page-freelancing" class="page">
  <h1>Freelancing Center</h1>
  <div class="stats-grid" id="fl-stats"></div>
  <div class="card">
    <h3>Bid History</h3>
    <table><thead><tr><th>Project</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead><tbody id="fl-bids"></tbody></table>
  </div>
</div>

<div id="page-chat" class="page">
  <h1>Conversation Log</h1>
  <div class="card">
    <table><thead><tr><th>Conversation ID</th><th>Platform</th><th>Role</th><th>Content</th><th>Intent</th><th>Time</th></tr></thead><tbody id="chat-rows"></tbody></table>
  </div>
</div>

<div id="page-settings" class="page">
  <h1>System Settings</h1>
  <div class="stats-grid" id="set-stats"></div>
</div>

</div>
<script>
const API={base:'/api'};
async function getJSON(url){const r=await fetch(url);return r.json()}

function esc(s){const d=document.createElement('div');d.textContent=s||'';return d.innerHTML}

// Overview
async function loadOverview(){
  const d=await getJSON('/api/conversations');
  const total=d.total||0, convos=d.conversations||0, plats=d.platforms||{};
  document.getElementById('ov-stats').innerHTML=
    '<div class="stat-card"><div class="num">'+total+'</div><div class="label">Total Messages</div></div>'+
    '<div class="stat-card"><div class="num">'+convos+'</div><div class="label">Conversations</div></div>'+
    '<div class="stat-card"><div class="num">'+(plats.freelancer||0)+'</div><div class="label">Freelancer</div></div>'+
    '<div class="stat-card"><div class="num">'+(plats.email||0)+'</div><div class="label">Email</div></div>'+
    '<div class="stat-card"><div class="num">'+(plats.whatsapp||0)+'</div><div class="label">WhatsApp</div></div>'+
    '<div class="stat-card"><div class="num">'+(plats.api||0)+'</div><div class="label">API</div></div>';
  const recent=d.recent||[];
  let rows='';
  for(const c of recent){
    const platClass={freelancer:'badge-fl',email:'badge-em',whatsapp:'badge-wa',api:'badge-api'}[c.platform]||'badge-api';
    rows+='<tr><td>'+esc(c.conversation_id).substr(0,12)+'...</td><td><span class="badge '+platClass+'">'+esc(c.platform)+'</span></td><td>'+c.count+'</td><td>'+esc((c.last_message||'').substr(0,19))+'</td></tr>';
  }
  document.getElementById('ov-convos').innerHTML=rows||'<tr><td colspan="4" class="empty">No conversations yet</td></tr>';
  let platHtml='';
  const colors={freelancer:'#39AEA9',email:'#A95EAE',whatsapp:'#5EAE5E',api:'#AEAE5E'};
  for(const [k,v] of Object.entries(plats)){
    if(total>0){const pct=Math.round(v/total*100);platHtml+='<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:2px"><span>'+k+'</span><span>'+v+' ('+pct+'%)</span></div><div style="background:#1a3a3a;height:6px;border-radius:3px;overflow:hidden"><div style="width:'+pct+'%;height:100%;background:'+(colors[k]||'#39AEA9')+';border-radius:3px"></div></div></div>';}
  }
  document.getElementById('ov-platforms').innerHTML=platHtml||'<div class="empty">No data</div>';
}

// Freelancing
async function loadFreelancing(){
  let bids=[];
  try{const r=await fetch('/api/freelancer/bids');if(r.ok){const d=await r.json();bids=d.bids||[]}}catch(e){}
  document.getElementById('fl-stats').innerHTML=
    '<div class="stat-card"><div class="num">'+bids.length+'</div><div class="label">Total Bids</div></div>'+
    '<div class="stat-card"><div class="num">'+bids.filter(b=>b.status==='won').length+'</div><div class="label">Won</div></div>'+
    '<div class="stat-card"><div class="num">'+(bids.reduce((s,b)=>s+(parseFloat(b.amount)||0),0).toFixed(0))+'</div><div class="label">Total Bid (INR)</div></div>'+
    '<div class="stat-card"><div class="num">'+bids.filter(b=>b.status==='active'||b.status==='sent').length+'</div><div class="label">Active</div></div>';
  let rows='';
  for(const b of bids){
    const cls='badge-'+(b.status||'sent');
    rows+='<tr><td>'+esc(b.project_title||b.project_id||'?')+'</td><td>'+esc((b.currency||'INR')+' '+(parseFloat(b.amount)||0))+'</td><td><span class="badge '+cls+'">'+esc(b.status||'sent')+'</span></td><td>'+esc((b.date||b.timestamp||'').substr(0,10))+'</td></tr>';
  }
  document.getElementById('fl-bids').innerHTML=rows||'<tr><td colspan="4" class="empty">No bids placed yet</td></tr>';
}

// Chat log
async function loadChat(){
  const d=await getJSON('/api/conversations?limit=200');
  const items=d.conversation_list||[];
  let rows='';
  for(const m of items){
    const platClass={freelancer:'badge-fl',email:'badge-em',whatsapp:'badge-wa',api:'badge-api'}[m.platform]||'badge-api';
    rows+='<tr><td>'+esc(m.conversation_id).substr(0,10)+'</td><td><span class="badge '+platClass+'">'+esc(m.platform)+'</span></td><td>'+esc(m.role)+'</td><td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(m.content).substr(0,80)+'</td><td>'+esc(m.intent||'-')+'</td><td>'+esc((m.created_at||'').substr(0,19))+'</td></tr>';
  }
  document.getElementById('chat-rows').innerHTML=rows||'<tr><td colspan="6" class="empty">No messages yet</td></tr>';
}

// Settings
async function loadSettings(){
  const h=await getJSON('/health');
  document.getElementById('set-stats').innerHTML=
    '<div class="stat-card"><div class="num" style="color:'+(h.groq?'#39AEA9':'#ce5e5e')+'">'+(h.groq?'ON':'OFF')+'</div><div class="label">Groq AI Engine</div></div>'+
    '<div class="stat-card"><div class="num" style="color:'+(h.freelancer_token?'#39AEA9':'#ce5e5e')+'">'+(h.freelancer_token?'ON':'OFF')+'</div><div class="label">Freelancer API</div></div>'+
    '<div class="stat-card"><div class="num" style="color:'+(h.supabase?'#39AEA9':'#ce5e5e')+'">'+(h.supabase?'ON':'OFF')+'</div><div class="label">Supabase DB</div></div>'+
    '<div class="stat-card"><div class="num" style="color:'+(h.email?'#39AEA9':'#ce5e5e')+'">'+(h.email?'ON':'OFF')+'</div><div class="label">Email Connector</div></div>'+
    '<div class="stat-card"><div class="num">'+(h.knowledge_files||0)+'</div><div class="label">Knowledge Files</div></div>'+
    '<div class="stat-card"><div class="num" style="color:#39AEA9">OK</div><div class="label">System Status</div></div>';
}

// Navigation
document.querySelectorAll('.nav a[data-page]').forEach(a=>{
  a.addEventListener('click',function(e){
    e.preventDefault();
    document.querySelectorAll('.nav a').forEach(x=>x.classList.remove('active'));
    this.classList.add('active');
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    const pg=document.getElementById('page-'+this.dataset.page);
    if(pg){pg.classList.add('active')}
  });
});

// Init
loadOverview();loadFreelancing();loadChat();loadSettings();
setInterval(loadOverview,30000);
</script>
</body></html>"""
    return render_template_string(html)


@app.route("/api/conversations")
def api_conversations():
    """Get conversation stats and full message list for dashboard."""
    rows = supabase_query("messages", {
        "select": "*",
        "order": "created_at.desc",
        "limit": 200,
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
        "conversation_list": rows,
    })


@app.route("/api/freelancer/bids")
def api_freelancer_bids():
    """Get bid history from bids_tracker.json."""
    bids_path = os.path.join(os.path.dirname(__file__), "..", "LIVE_DATA", "bids_tracker.json")
    try:
        with open(bids_path) as f:
            data = json.load(f)
        return jsonify({"bids": data if isinstance(data, list) else data.get("bids", [])})
    except:
        return jsonify({"bids": []})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"ORION Chat Agent v2 starting on port {port}")
    print(f"  Groq: {'ON' if GROQ_API_KEY else 'OFF'}")
    print(f"  Freelancer: {'ON' if ACCESS_TOKEN else 'OFF'}")
    print(f"  Supabase: {'ON' if SUPABASE_URL else 'OFF'}")
    print(f"  Knowledge files: {len(search_knowledge('').split(chr(10))) if search_knowledge('') else 0}")
    app.run(host="0.0.0.0", port=port, debug=False)
