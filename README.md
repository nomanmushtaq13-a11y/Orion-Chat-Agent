# ORION Universal Chat Agent v2

Multi-platform AI client communication system. 24/7 uptime on Railway.

## Live Features

| Feature | Status | Details |
|---------|--------|---------|
| Freelancer Auto-Reply | ✅ Active | Monitors threads, auto-responds via Groq |
| RAG Knowledge Base | ✅ Active | Reads services.md, pricing.md, company.md, faq.md |
| Intent Router | ✅ Active | Sales / Support / Project / Meeting / Escalation |
| Conversation Dashboard | ✅ Active | `/dashboard` - see all conversations |
| Escalation Workflow | ✅ Built | Routes angry clients to human |

## Ready to Enable

| Connector | Setup Needed | 
|-----------|-------------|
| Email (Gmail) | Gmail API OAuth credentials |
| WhatsApp (Twilio) | Twilio account + WhatsApp Business approval |

## API Endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Status check |
| `/health` | GET | Health check with feature flags |
| `/webhook/freelancer` | POST | Freelancer message webhook |
| `/poll` | GET | Poll Freelancer for unread messages |
| `/api/message` | POST | Generic message endpoint (for testing) |
| `/dashboard` | GET | HTML conversation dashboard |
| `/api/conversations` | GET | Conversation stats JSON |

## How to Push Updates to Railway

```bash
cd chat-agent
git add .
git commit -m "description of changes"
git push
```

Railway auto-deploys when you push to GitHub.

## Knowledge Base

Edit files in `knowledge/` to update what the agent knows:

| File | What it contains |
|------|-----------------|
| `services.md` | Services offered, delivery process, turnaround |
| `pricing.md` | Pricing by service, packages, payment terms |
| `company.md` | About Noman, working hours, communication style |
| `faq.md` | Common questions and answers |

The agent automatically searches these files for context relevant to each client message. No code changes needed.

## Env Variables Needed

```
FREELANCER_ACCESS_TOKEN=your_token
FREELANCER_USER_ID=92619113
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=https://epfdhzgizosbjczxpgxp.supabase.co
SUPABASE_KEY=your_service_role_key
```

**Secrets should NEVER be committed to git.**
Use environment variables or a .env file for local development.
