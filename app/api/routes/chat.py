import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.dependencies import AuthContext, get_auth_context
from app.api.chat_service import create_chat_turn, parse_conversation_id
from app.database import run_as_user

router = APIRouter()


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text must not be blank.")
        return cleaned


class ChatMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    prompt: str
    response: str
    created_at: datetime


@router.post("", response_model=ChatMessage)
async def create_chat_message(
    request: ChatRequest,
    auth: AuthContext = Depends(get_auth_context),
) -> ChatMessage:
    turn = await create_chat_turn(
        auth,
        request.text,
        parse_conversation_id(request.conversation_id),
    )
    return ChatMessage(
        id=turn.id,
        conversation_id=turn.conversation_id,
        prompt=turn.prompt,
        response=turn.response,
        created_at=turn.created_at,
    )


@router.get("/history", response_model=list[ChatMessage])
async def get_chat_history(
    auth: AuthContext = Depends(get_auth_context),
) -> list[ChatMessage]:
    rows = await asyncio.to_thread(
        run_as_user,
        auth,
        lambda connection: connection.execute(
            """
            SELECT
                m.id,
                c.id::text AS conversation_id,
                m.user_message AS prompt,
                m.ai_response AS response,
                m.created_at
            FROM public.conversations AS c
            JOIN public.messages AS m ON m.conversation_id = c.id
            WHERE c.user_id = %s
            ORDER BY m.created_at DESC
            LIMIT 100
            """,
            (auth.user_id,),
        ).fetchall(),
    )
    return [ChatMessage.model_validate(row) for row in rows]
