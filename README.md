# Saywise frontend

React and JavaScript client for the AI Recognition FastAPI service.

## Run locally

Configure the backend `.env` first, including `DATABASE_URL`, `AUTH_SECRET`,
the AI provider key, and the Google OAuth values if using Google sign-in.
Install backend dependencies if needed, then start FastAPI:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

In this folder, install and start the frontend:

```powershell
npm install
npm run dev
```

Open the URL printed by Vite, usually `http://localhost:5173`.

Set `VITE_API_URL` in a local `.env` file to change the backend origin. The frontend defaults to `http://localhost:8001`. Never put backend secrets in this frontend project.

Google sign-in uses the backend's one-time `google_code` callback exchange. Set the backend's `GOOGLE_FRONTEND_REDIRECT_URI` to the frontend origin plus `/` (for example, `http://localhost:5173/`) and allow that frontend origin in the backend CORS configuration. The Google OAuth `GOOGLE_REDIRECT_URI` is a separate backend callback and must exactly match an authorized redirect URI in Google Cloud Console.

Voice input uses the browser's Web Speech API and may require HTTPS outside localhost. Spoken replies use the browser speech synthesis API.

## Password reset

The backend sends password reset links using Gmail SMTP. Configure these values
in the backend `.env` file (the placeholders are also listed in `.env.example`):

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your-gmail-address@gmail.com
SMTP_APP_PASSWORD=your-gmail-app-password
PASSWORD_RESET_FRONTEND_URL=http://localhost:5173/reset-password
```

Use a Gmail App Password, not your normal Google password. Keep the SMTP
credentials in the backend environment; do not add them to frontend code or
commit them. The reset URL may use HTTP only for localhost during development;
use HTTPS in production.

For an existing database, run
[20261029_password_reset_tokens.sql](./migrations/20261029_password_reset_tokens.sql)
in the Supabase SQL Editor. The updated [schema.sql](./schema.sql) also
includes the table for fresh database setup. The migration creates
`public.password_reset_tokens`, its indexes, and RLS protection while
revoking access from the `anon` and `authenticated` API roles. The backend
connects directly to PostgreSQL using its server-side `DATABASE_URL`; the
frontend must never access this table. Expired rows are removed by the schema
cleanup and opportunistically on later forgot-password requests.

The forgot-password endpoint always returns the same generic message for
registered and unregistered addresses. It limits requests to five per email
and twenty per client IP per hour in each backend process. This in-memory
limiter is suitable for a single local development process; production
deployments with multiple workers or instances should enforce the same limits
using a shared Redis-backed limiter or API gateway. Configure trusted proxy
handling before relying on forwarded client IP headers.

Tokens are random, stored only as SHA-256 hashes, expire after 30 minutes, and
are consumed once. Resetting a Google-created account establishes a local
password for that account; Google sign-in remains available. Password reset
does not revoke existing access tokens: this project has no session-revocation
mechanism, and issued JWTs remain valid until their 12-hour expiration.

### Test the reset flow

1. Start the backend and frontend using the commands above, then open
   `http://localhost:5173`.
2. Select **Forgot Password?**, enter an account email, and submit. The page
   displays a generic confirmation whether or not the address is registered.
3. For a registered account, open the email and follow the link within 30
   minutes. Enter and confirm a password of at least eight characters.
4. Return to login and verify the new password works. The old password should
   no longer authenticate.

Automated tests use a fake database and mocked SMTP; they do not send real
email or modify Supabase data:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run build
npm run lint
```

## Commands

```powershell
npm run dev
npm run build
npm run lint
```