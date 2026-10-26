import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import HTTPException
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("not-a-real-password")
TOKEN_ISSUER = "ai-recog-api"
TOKEN_AUDIENCE = "ai-recog-api"
TOKEN_LIFETIME = timedelta(hours=12)


def get_auth_secret() -> str:
    secret = os.getenv("AUTH_SECRET")
    if not secret or len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Set AUTH_SECRET to a random secret of at least 32 characters.",
        )
    return secret


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hash.verify(password, stored_hash)


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(UUID(user_id)),
        "email": email,
        "role": "authenticated",
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": now,
        "exp": now + TOKEN_LIFETIME,
    }
    return jwt.encode(claims, get_auth_secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict[str, str]:
    try:
        claims = jwt.decode(
            token,
            get_auth_secret(),
            algorithms=["HS256"],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={"require": ["sub", "email", "role", "exp", "iat"]},
        )
        UUID(claims["sub"])
        if claims["role"] != "authenticated":
            raise ValueError("Invalid token role.")
        return {"user_id": claims["sub"], "email": claims["email"]}
    except HTTPException:
        raise
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=401,
            detail="The access token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
