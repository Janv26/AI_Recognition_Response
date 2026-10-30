CREATE TABLE IF NOT EXISTS public.app_users (
    id uuid PRIMARY KEY,
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    full_name text,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.app_users
    ADD COLUMN IF NOT EXISTS language text NOT NULL DEFAULT 'English',
    ADD COLUMN IF NOT EXISTS voice_enabled boolean NOT NULL DEFAULT true;

CREATE TABLE IF NOT EXISTS public.chat_history (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL,
    prompt text NOT NULL CHECK (char_length(prompt) BETWEEN 1 AND 4000),
    response text NOT NULL CHECK (char_length(response) > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.chat_history
    DROP CONSTRAINT IF EXISTS chat_history_user_id_fkey;

CREATE TABLE IF NOT EXISTS public.conversations (
    id bigserial PRIMARY KEY,
    title varchar(255),
    created_at timestamptz DEFAULT now(),
    user_id uuid REFERENCES public.app_users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.messages (
    id bigserial PRIMARY KEY,
    conversation_id bigint NOT NULL REFERENCES public.conversations (id) ON DELETE CASCADE,
    user_message text NOT NULL,
    ai_response text NOT NULL,
    input_type varchar(20) DEFAULT 'text',
    response_type varchar(20) DEFAULT 'voice',
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.google_login_codes (
    code_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.app_users (id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    token_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.app_users (id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_history_user_created_at_idx
    ON public.chat_history (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS conversations_user_created_at_idx
    ON public.conversations (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS messages_conversation_idx
    ON public.messages (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS password_reset_tokens_user_created_at_idx
    ON public.password_reset_tokens (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS password_reset_tokens_expires_at_idx
    ON public.password_reset_tokens (expires_at);

ALTER TABLE public.app_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read their own account" ON public.app_users;
CREATE POLICY "Users can read their own account"
    ON public.app_users FOR SELECT TO authenticated
    USING ((SELECT auth.uid()) = id);

DROP POLICY IF EXISTS "Users can update their own account" ON public.app_users;
CREATE POLICY "Users can update their own account"
    ON public.app_users FOR UPDATE TO authenticated
    USING ((SELECT auth.uid()) = id)
    WITH CHECK ((SELECT auth.uid()) = id);

DROP POLICY IF EXISTS "Users can read their own chat history" ON public.chat_history;
CREATE POLICY "Users can read their own chat history"
    ON public.chat_history FOR SELECT TO authenticated
    USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can add to their own chat history" ON public.chat_history;
CREATE POLICY "Users can add to their own chat history"
    ON public.chat_history FOR INSERT TO authenticated
    WITH CHECK ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can read their own conversations" ON public.conversations;
CREATE POLICY "Users can read their own conversations"
    ON public.conversations FOR SELECT TO authenticated
    USING ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can create their own conversations" ON public.conversations;
CREATE POLICY "Users can create their own conversations"
    ON public.conversations FOR INSERT TO authenticated
    WITH CHECK ((SELECT auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can read messages in their own conversations" ON public.messages;
CREATE POLICY "Users can read messages in their own conversations"
    ON public.messages FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.conversations
            WHERE conversations.id = messages.conversation_id
              AND conversations.user_id = (SELECT auth.uid())
        )
    );

DROP POLICY IF EXISTS "Users can add messages to their own conversations" ON public.messages;
CREATE POLICY "Users can add messages to their own conversations"
    ON public.messages FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM public.conversations
            WHERE conversations.id = messages.conversation_id
              AND conversations.user_id = (SELECT auth.uid())
        )
    );

GRANT SELECT, UPDATE ON public.app_users TO authenticated;
GRANT SELECT, INSERT ON public.chat_history TO authenticated;
GRANT SELECT, INSERT ON public.conversations TO authenticated;
GRANT SELECT, INSERT ON public.messages TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE public.conversations_id_seq TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE public.messages_id_seq TO authenticated;

ALTER TABLE public.google_login_codes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.google_login_codes FROM anon, authenticated;

ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.password_reset_tokens FROM PUBLIC, anon, authenticated;

DELETE FROM public.password_reset_tokens WHERE expires_at <= now();
