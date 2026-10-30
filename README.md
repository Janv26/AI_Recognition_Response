# AI Recognition API

Backend-only FastAPI service for account authentication, voice/text AI
responses, conversation history, and user preferences. PostgreSQL is accessed
directly through `DATABASE_URL`; the backend does not use Supabase Auth or
Supabase API keys.

## Setup

Use Python 3.10 or newer. From the project directory in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set these values in a private `.env` file:

```env
DATABASE_URL=your-supabase-postgres-connection-uri
AUTH_SECRET=your-random-secret-at-least-32-characters
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_BASE_URL=https://api.groq.com/openai/v1
# Optional fallback if you switch back to OpenAI:
# OPENAI_API_KEY=your-openai-api-key
# OPENAI_MODEL=gpt-4o-mini
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
GOOGLE_FRONTEND_REDIRECT_URI=http://localhost:5173/login
```

`AUTH_SECRET` signs 12-hour access tokens. Generate it once with
`python -c "import secrets; print(secrets.token_urlsafe(48))"` and keep the
same value between restarts. Never expose `.env` or `DATABASE_URL` to a
browser.

Apply [schema.sql](./schema.sql) in the Supabase SQL Editor before running the
API. It creates/updates the account preferences columns, conversation/message
storage, grants, indexes, and per-user RLS policies. Existing `conversations`
and `messages` tables are retained in their existing column format; new
voice exchanges are stored as one conversation row and one user/AI message
row. The migration removes the old `chat_history.user_id` foreign key to
`auth.users`, since this backend uses `public.app_users`.

For Google sign-in, create a Google OAuth web application and register the
exact `GOOGLE_REDIRECT_URI` as an authorized redirect URI. Configure
`GOOGLE_FRONTEND_REDIRECT_URI` as a fixed frontend callback URL. The backend
redirects there with a short-lived `google_code`; the frontend callback must
POST that code to `/api/auth/google/exchange`, then store the returned access
token and user just like a manual login. The code expires after two minutes
and can only be exchanged once. Google credentials are backend-only.

## Run

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open <http://127.0.0.1:8000/docs> for the API schema. The development CORS
allowlist includes `http://localhost:5173` and `http://127.0.0.1:5173`.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/auth/signup` | Create a user from `fullname`, `email`, `password`, and `confirmPassword`; returns user details and an access token. |
| `POST /api/auth/login` | Verify `email`/`password`; returns user details and an access token. |
| `POST /api/auth/forgot-password` | Request a password reset email; returns a generic response to avoid account enumeration. |
| `POST /api/auth/reset-password` | Set a new password with a valid, single-use reset token. |
| `GET /api/auth/google` | Redirect the browser to Google sign-in. |
| `GET /api/auth/google/callback` | Validate Google's response and redirect with a one-time login code. |
| `POST /api/auth/google/exchange` | Exchange a one-time Google login code for the backend access token. |
| `POST /api/voice/respond` | Send `{ "text": "...", "conversation_id": "..." }` to the AI and save the exchange to PostgreSQL. Omit `conversation_id` to begin a conversation; reuse the returned ID to continue it. |
| `GET /api/voice/history` | Return up to the latest 100 exchanges for the logged-in user. |
| `GET /api/users/settings` | Return the logged-in user's name, language, and voice preference. |
| `PUT /api/users/settings` | Update any of `name`, `language`, and `voiceEnabled`. |
| `GET /api/health` | Check API and PostgreSQL availability. |
| `POST /api/chat` | Text-chat endpoint using the same conversation storage and context as voice respond. |
| `GET /api/chat/history` | Return up to the latest 100 exchanges for the logged-in user. |

Conversation context sent to the AI includes up to the last 20 exchanges in
that conversation. Conversation IDs are checked against the authenticated
user; IDs belonging to another user return `404`.

Authenticated endpoints accept `Authorization: Bearer <token>` and the legacy
`Authorization: Token <token>` form. Signup and login also accept `username`
as an alias for `email` for compatibility with the existing client contract.
`confirmPassword` is a frontend-only field and is not accepted or stored by
the backend.

## Password reset

Configure Gmail SMTP in the backend `.env` file:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your-gmail-address@gmail.com
SMTP_APP_PASSWORD=your-gmail-app-password
PASSWORD_RESET_FRONTEND_URL=http://localhost:5173/reset-password
```

Use a Gmail App Password, not your regular Google password. Keep SMTP
credentials in the backend environment; do not commit them. Use HTTPS for the
reset URL in production.

For an existing database, run
[20261029_password_reset_tokens.sql](./migrations/20261029_password_reset_tokens.sql)
in Supabase SQL Editor. The updated [schema.sql](./schema.sql) includes the
table for fresh database setup. Reset tokens are stored as SHA-256 hashes,
expire after 30 minutes, and can only be used once. Password reset does not
revoke already-issued access tokens.

Run the automated backend tests with:

```powershell
python -m unittest discover -s tests -v
```
