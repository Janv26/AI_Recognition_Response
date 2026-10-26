import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.api.dependencies import AuthContext, get_auth_context
from app.api.chat_service import create_chat_turn, parse_conversation_id
from app.database import run_as_user

router = APIRouter()


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text must not be blank.")
        return cleaned


class VoiceResponse(BaseModel):
    conversation_id: str
    text: str
    answer: str
    created_at: datetime


class HistoryEntry(BaseModel):
    conversation_id: str
    text: str
    response: str
    time: datetime


class HistoryResponse(BaseModel):
    history: list[HistoryEntry]


@router.post("/respond/", response_model=VoiceResponse, include_in_schema=False)
@router.post("/respond", response_model=VoiceResponse)
async def respond_to_voice(
    request: VoiceRequest,
    auth: AuthContext = Depends(get_auth_context),
) -> VoiceResponse:
    turn = await create_chat_turn(
        auth,
        request.text,
        parse_conversation_id(request.conversation_id),
        response_type="voice",
    )
    return VoiceResponse(
        conversation_id=turn.conversation_id,
        text=turn.prompt,
        answer=turn.response,
        created_at=turn.created_at,
    )


@router.get("/history", response_model=HistoryResponse)
async def get_voice_history(
    auth: AuthContext = Depends(get_auth_context),
) -> HistoryResponse:
    rows = await asyncio.to_thread(
        run_as_user,
        auth,
        lambda connection: connection.execute(
            """
            SELECT
                c.id::text AS conversation_id,
                c.created_at AS time,
                m.user_message AS text,
                m.ai_response AS response
            FROM public.conversations AS c
            JOIN public.messages AS m ON m.conversation_id = c.id
            WHERE c.user_id = %s
            ORDER BY c.created_at DESC
            LIMIT 100
            """,
            (auth.user_id,),
        ).fetchall(),
    )
    return HistoryResponse(history=[HistoryEntry.model_validate(row) for row in rows])
