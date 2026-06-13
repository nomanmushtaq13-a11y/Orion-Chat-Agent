-- ORION Chat Agent Schema
-- Run this in Supabase SQL Editor

-- Messages table (multi-platform)
CREATE TABLE IF NOT EXISTS messages (
  id BIGSERIAL PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('client', 'agent', 'system')),
  content TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT 'api' CHECK (platform IN ('freelancer', 'email', 'whatsapp', 'api')),
  project_id TEXT,
  intent TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_platform ON messages(platform);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

-- Client profiles (for context across conversations)
CREATE TABLE IF NOT EXISTS clients (
  id BIGSERIAL PRIMARY KEY,
  platform_client_id TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT 'api',
  name TEXT,
  email TEXT,
  company TEXT,
  notes TEXT,
  first_contact TIMESTAMPTZ DEFAULT NOW(),
  last_contact TIMESTAMPTZ DEFAULT NOW(),
  total_spent DECIMAL(12,2) DEFAULT 0,
  UNIQUE(platform_client_id, platform)
);

-- Escalation requests (human handoff)
CREATE TABLE IF NOT EXISTS escalations (
  id BIGSERIAL PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  reason TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'resolved', 'ignored')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

-- Row Level Security
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_messages" ON messages FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_clients" ON clients FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_escalations" ON escalations FOR ALL USING (auth.role() = 'service_role');
