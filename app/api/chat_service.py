import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg
from fastapi import HTTPException
from openai import AsyncOpenAI, OpenAIError

from app.api.dependencies import AuthContext
from app.database import run_as_user

CHAT_CONTEXT_TURNS = 20


def get_ai_client() -> AsyncOpenAI:
    groq_api_key = os.getenv("GROQ_API_KEY")

    if not groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured.",
        )

    return AsyncOpenAI(
        api_key=groq_api_key,
        base_url="https://api.groq.com/openai/v1",
    )


def get_model_name() -> str:
    return os.getenv(
        "GROQ_MODEL",
        "llama-3.3-70b-versatile",
    )


@dataclass
class ChatTurn:
    id: int
    conversation_id: str
    prompt: str
    response: str
    created_at: datetime


def load_conversation_context(
    auth: AuthContext,
    conversation_id: int | None,
) -> tuple[int | None, list[dict[str, str]]]:

    def load(
        connection: psycopg.Connection,
    ) -> tuple[int | None, list[dict[str, str]]]:

        if conversation_id is None:
            return None, []

        conversation = connection.execute(
            """
            SELECT id
            FROM public.conversations
            WHERE id = %s AND user_id = %s
            """,
            (conversation_id, auth.user_id),
        ).fetchone()

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="The conversation was not found.",
            )

        rows = connection.execute(
            """
            SELECT user_message, ai_response
            FROM public.messages
            WHERE conversation_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (conversation_id, CHAT_CONTEXT_TURNS),
        ).fetchall()

        context: list[dict[str, str]] = []

        for row in reversed(rows):
            context.append(
                {
                    "role": "user",
                    "content": row["user_message"],
                }
            )
            context.append(
                {
                    "role": "assistant",
                    "content": row["ai_response"],
                }
            )

        return int(conversation["id"]), context

    return run_as_user(auth, load)


async def create_chat_turn(
    auth: AuthContext,
    prompt: str,
    conversation_id: int | None = None,
    response_type: str = "text",
) -> ChatTurn:

    existing_conversation_id, context = await asyncio.to_thread(
        load_conversation_context,
        auth,
        conversation_id,
    )

    context.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    try:
        async with get_ai_client() as client:
            result = await client.chat.completions.create(
                model=get_model_name(),
                messages=context,
            )

    except OpenAIError as error:
        print(
            f"Groq API error: {type(error).__name__}: {error}",
            flush=True,
        )
        raise HTTPException(
            status_code=502,
            detail="The AI provider could not generate a response.",
        ) from error

    response_text = (
        result.choices[0].message.content or ""
    ).strip()

    if not response_text:
        raise HTTPException(
            status_code=502,
            detail="The AI provider returned an empty response.",
        )

    created_at = datetime.now(timezone.utc)

    def save(connection: psycopg.Connection) -> tuple[int, int]:

        if existing_conversation_id is None:
            conversation = connection.execute(
                """
                INSERT INTO public.conversations
                    (user_id, title, created_at)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (auth.user_id, prompt[:120], created_at),
            ).fetchone()

            saved_conversation_id = int(conversation["id"])

        else:
            saved_conversation_id = existing_conversation_id

        message = connection.execute(
            """
            INSERT INTO public.messages
                (conversation_id, user_message, ai_response,
                 input_type, response_type, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                saved_conversation_id,
                prompt,
                response_text,
                "text",
                response_type,
                created_at,
            ),
        ).fetchone()

        return int(message["id"]), saved_conversation_id

    message_id, saved_conversation_id = await asyncio.to_thread(
        run_as_user,
        auth,
        save,
    )

    return ChatTurn(
        id=message_id,
        conversation_id=str(saved_conversation_id),
        prompt=prompt,
        response=response_text,
        created_at=created_at,
    )


def parse_conversation_id(
    value: str | None,
) -> int | None:

    if value is None:
        return None

    try:
        parsed = int(value)

        if parsed <= 0:
            raise ValueError

        return parsed

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="conversation_id must be a positive integer.",
        ) from error
