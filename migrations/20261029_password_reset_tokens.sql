BEGIN;

CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    token_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.app_users (id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS password_reset_tokens_user_created_at_idx
    ON public.password_reset_tokens (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS password_reset_tokens_expires_at_idx
    ON public.password_reset_tokens (expires_at);

ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.password_reset_tokens
    FROM PUBLIC, anon, authenticated;

DELETE FROM public.password_reset_tokens WHERE expires_at <= now();

COMMIT;
