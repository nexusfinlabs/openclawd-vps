CREATE TABLE IF NOT EXISTS email_drafts (
    id SERIAL PRIMARY KEY,
    target_email TEXT,
    target_name TEXT,
    company_name TEXT,
    context_tier TEXT DEFAULT 'medium',
    original_prompt TEXT,
    subject TEXT,
    body TEXT,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ
);
