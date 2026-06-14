-- ============================================================
-- ORION Chat Agent - Full Database Schema
-- ============================================================
-- HOW TO RUN:
-- 1. Go to https://supabase.com/dashboard/project/epfdhzgizosbjczxpgxp/sql
-- 2. Paste ALL of this SQL
-- 3. Click "Run" (Ctrl+Enter)
-- ============================================================

-- Add new columns to existing messages table
ALTER TABLE IF EXISTS messages 
  ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT 'api',
  ADD COLUMN IF NOT EXISTS intent TEXT;

-- Create clients table
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

-- Create escalations table
CREATE TABLE IF NOT EXISTS escalations (
  id BIGSERIAL PRIMARY KEY,
  conversation_id TEXT NOT NULL,
  reason TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'resolved', 'ignored')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_platform ON messages(platform);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

-- Enable Row Level Security
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalations ENABLE ROW LEVEL SECURITY;

-- Grant access to service_role
DROP POLICY IF EXISTS "service_role_all_messages" ON messages;
DROP POLICY IF EXISTS "service_role_all_clients" ON clients;
DROP POLICY IF EXISTS "service_role_all_escalations" ON escalations;

CREATE POLICY "service_role_all_messages" ON messages FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_clients" ON clients FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_escalations" ON escalations FOR ALL USING (auth.role() = 'service_role');

-- Verify
SELECT 'messages' AS table_name, COUNT(*) AS row_count FROM messages
UNION ALL
SELECT 'clients', COUNT(*) FROM clients
UNION ALL
SELECT 'escalations', COUNT(*) FROM escalations;
