# Saywise frontend

React and JavaScript client for the AI Recognition FastAPI service.

## Run locally

1. Start the backend from the attached `ai_recog` project using its README. By default it runs at `http://localhost:8000`.
2. In this folder, install and start the frontend:

```powershell
npm install
npm run dev
```

Open the URL printed by Vite, usually `http://localhost:5173`.

Set `VITE_API_URL` in a local `.env` file to change the backend origin. The frontend defaults to `http://localhost:8000`. Never put backend secrets in this frontend project.

Google sign-in uses the backend's one-time `google_code` callback exchange. Set the backend's `GOOGLE_FRONTEND_REDIRECT_URI` to the frontend origin plus `/` (for example, `http://localhost:5173/`) and allow that frontend origin in the backend CORS configuration. The backend README currently configures its OAuth redirect for port `3000`, so update it to port `5173` when using Vite.

Voice input uses the browser's Web Speech API and may require HTTPS outside localhost. Spoken replies use the browser speech synthesis API.

## Commands

```powershell
npm run dev
npm run build
npm run lint
```