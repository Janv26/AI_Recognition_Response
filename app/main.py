from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

load_dotenv()
import os

print("GOOGLE_CLIENT_ID loaded:", bool(os.getenv("GOOGLE_CLIENT_ID")))
print("GOOGLE_CLIENT_SECRET loaded:", bool(os.getenv("GOOGLE_CLIENT_SECRET")))
print("GOOGLE_REDIRECT_URI loaded:", bool(os.getenv("GOOGLE_REDIRECT_URI")))
print("GOOGLE_FRONTEND_REDIRECT_URI loaded:", bool(os.getenv("GOOGLE_FRONTEND_REDIRECT_URI")))

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.settings import router as settings_router
from app.api.routes.voice import router as voice_router

app = FastAPI(title="AI Recognition API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(voice_router, prefix="/api/voice", tags=["voice"])
app.include_router(settings_router, prefix="/api", tags=["settings"])
app.include_router(health_router, prefix="/api", tags=["health"])
