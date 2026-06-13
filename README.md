# ORION Chat Agent — 24/7 Freelancer Client Communication

Auto-responds to Freelancer.com messages using Groq AI.
Stores all conversations in Supabase.
Ready to deploy on Railway in 5 minutes.

## Quick Deploy (Railway)

**1. Create Supabase table**
```sql
-- Run this in Supabase SQL Editor:
CREATE TABLE messages (
  id BIGSERIAL PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  project_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_conv ON messages(conversation_id);
```

**2. Create Railway project**
```bash
# From chat-agent/ directory:
railway login
railway init
railway up
```

**3. Set environment variables in Railway dashboard:**
| Variable | Value | Where to get |
|----------|-------|-------------|
| `FREELANCER_ACCESS_TOKEN` | your token | Freelancer API settings |
| `FREELANCER_USER_ID` | `92619113` | Already known |
| `GROQ_API_KEY` | `gsk_hRkj...` | Groq console |
| `SUPABASE_URL` | `https://xxx.supabase.co` | Supabase project settings |
| `SUPABASE_KEY` | service_role key | Supabase API settings |

**4. Set up Freelancer webhook**
Go to Freelancer.com → Settings → API → Webhooks
URL: `https://your-app.railway.app/webhook/freelancer`
Events: message_received

## How it works
```
Client sends message → Freelancer webhook → Flask app
  → Groq generates reply → Reply sent back via API
  → Both messages saved to Supabase
```

The `/poll` endpoint also checks for unread messages every minute
as a fallback if webhook is delayed.

## Test locally
```bash
pip install -r requirements.txt
python app.py
# Visit http://localhost:8080
# Poll: GET http://localhost:8080/poll
# Health: GET http://localhost:8080/health
```
