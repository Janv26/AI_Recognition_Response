# Saywise frontend

React and JavaScript client for the AI Recognition FastAPI service.

## Run locally

1. Start the backend from the attached `ai_recog` project using its README. By default it runs at `http://localhost:8001`.
2. In this folder, install and start the frontend:

```powershell
npm install
npm run dev
```

Open the URL printed by Vite, usually `http://localhost:5173`.

Set `VITE_API_URL` in a local `.env` file to change the backend origin. The frontend defaults to `http://localhost:8001`. Never put backend secrets in this frontend project.

Google sign-in uses the backend's one-time `google_code` callback exchange. Set the backend's `GOOGLE_FRONTEND_REDIRECT_URI` to the frontend origin plus `/` (for example, `http://localhost:5173/`) and allow that frontend origin in the backend CORS configuration. The backend's Google OAuth callback URL must also exactly match an authorized redirect URI in Google Cloud Console.

Voice input uses the browser's Web Speech API and may require HTTPS outside localhost. Spoken replies use the browser speech synthesis API.

## Password reset

Select **Forgot Password?** on the login screen, submit your account email,
then follow the link sent by the backend and choose a new password. The reset
page is available at `/reset-password`. Password reset email delivery must be
configured on the backend; keep SMTP credentials out of this frontend project.

## Commands

```powershell
npm run dev
npm run build
npm run lint
```