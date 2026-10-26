import asyncio
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import psycopg

from app.database import run_query
from app.security import decode_access_token


@dataclass
class AuthContext:
    user_id: str
    email: str | None
    full_name: str | None


bearer_scheme = HTTPBearer(auto_error=False)


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="A valid access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="A valid access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_claims = decode_access_token(token)

    try:
        user = await asyncio.to_thread(
            run_query,
            lambda connection: connection.execute(
                """
                SELECT id, email, full_name
                FROM public.app_users
                WHERE id = %s
                """,
                (token_claims["user_id"],),
            ).fetchone(),
        )
    except psycopg.Error as error:
        raise HTTPException(
            status_code=503,
            detail="The database could not verify the account.",
        ) from error

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="The account for this access token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthContext(
        user_id=str(user["id"]),
        email=user["email"],
        full_name=user["full_name"],
    )