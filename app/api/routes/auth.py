import asyncio
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import jwt
import psycopg
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, model_validator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.database import run_query
from app.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_auth_secret,
    hash_password,
    verify_password,
)

router = APIRouter()
GOOGLE_STATE_ISSUER = "ai-recog-google-oauth"
GOOGLE_STATE_AUDIENCE = "ai-recog-google-oauth"
GOOGLE_STATE_LIFETIME = timedelta(minutes=10)
GOOGLE_LOGIN_CODE_LIFETIME = timedelta(minutes=2)
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class Credentials(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(validation_alias=AliasChoices("email", "username"))
    password: str = Field(min_length=8, max_length=128)


class SignupCredentials(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    fullname: str = Field(
        min_length=1,
        max_length=120,
        validation_alias=AliasChoices("fullname", "full_name", "name"),
    )
    email: EmailStr = Field(validation_alias=AliasChoices("email", "username"))
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(
        min_length=8,
        max_length=128,
        validation_alias=AliasChoices("confirmPassword", "confirm_password"),
    )

    @model_validator(mode="after")
    def passwords_must_match(self) -> "SignupCredentials":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password must match.")
        return self


class UserDetails(BaseModel):
    id: str
    email: str
    name: str
    full_name: str | None


class AuthResult(BaseModel):
    access_token: str
    token: str
    refresh_token: str | None
    token_type: str
    username: str
    user: UserDetails


class GoogleCodeExchange(BaseModel):
    code: str = Field(min_length=32, max_length=256)


def create_auth_result(user: dict[str, object]) -> AuthResult:
    user_id = str(user["id"])
    email = str(user["email"])
    access_token = create_access_token(user_id, email)
    return AuthResult(
        access_token=access_token,
        token=access_token,
        refresh_token=None,
        token_type="bearer",
        username=email,
        user=UserDetails(
            id=user_id,
            email=email,
            name=str(user["full_name"] or ""),
            full_name=user["full_name"] if isinstance(user["full_name"], str) else None,
        ),
    )


def google_oauth_configuration() -> tuple[str, str, str, str]:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    frontend_redirect_uri = os.getenv("GOOGLE_FRONTEND_REDIRECT_URI")
    if not all((client_id, client_secret, redirect_uri, frontend_redirect_uri)):
        raise HTTPException(
            status_code=503,
            detail=(
                "Google sign-in is not configured. Set GOOGLE_CLIENT_ID, "
                "GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, and "
                "GOOGLE_FRONTEND_REDIRECT_URI."
            ),
        )
    return client_id, client_secret, redirect_uri, frontend_redirect_uri


def create_google_state() -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "purpose": "google_oauth",
        "nonce": secrets.token_urlsafe(32),
        "iss": GOOGLE_STATE_ISSUER,
        "aud": GOOGLE_STATE_AUDIENCE,
        "iat": now,
        "exp": now + GOOGLE_STATE_LIFETIME,
    }
    return jwt.encode(claims, get_auth_secret(), algorithm="HS256")


def validate_google_state(state: str) -> None:
    try:
        claims = jwt.decode(
            state,
            get_auth_secret(),
            algorithms=["HS256"],
            issuer=GOOGLE_STATE_ISSUER,
            audience=GOOGLE_STATE_AUDIENCE,
            options={"require": ["purpose", "nonce", "iat", "exp"]},
        )
        if claims["purpose"] != "google_oauth":
            raise ValueError("Invalid Google OAuth state.")
    except HTTPException:
        raise
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail="The Google sign-in state is invalid or expired.",
        ) from error


def append_query_parameter(url: str, key: str, value: str) -> str:
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append((key, value))
    return urlunsplit(parsed._replace(query=urlencode(query)))


@router.post("/signup", response_model=AuthResult, status_code=201)
async def signup(credentials: SignupCredentials) -> AuthResult:
    get_auth_secret()
    user_id = uuid4()
    email = str(credentials.email).lower()
    password_digest = await asyncio.to_thread(hash_password, credentials.password)

    try:
        user = await asyncio.to_thread(
            run_query,
            lambda connection: connection.execute(
                """
                INSERT INTO public.app_users (id, email, password_hash, full_name)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, full_name
                """,
                (user_id, email, password_digest, credentials.fullname),
            ).fetchone(),
        )
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        ) from error
    except psycopg.Error as error:
        raise HTTPException(
            status_code=503,
            detail="The database could not create the account.",
        ) from error

    if user is None:
        raise HTTPException(
            status_code=500,
            detail="The database did not return the created account.",
        )
    return create_auth_result(user)


@router.get("/google", include_in_schema=True)
async def start_google_login() -> RedirectResponse:
    client_id, _, redirect_uri, _ = google_oauth_configuration()
    state = create_google_state()
    
    authorization_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }

    authorization_url = f"{GOOGLE_AUTHORIZE_URL}?{urlencode(authorization_params)}"

    response = RedirectResponse(authorization_url, status_code=302)
    response.set_cookie(
        key="google_oauth_state",
        value=state,
        max_age=int(GOOGLE_STATE_LIFETIME.total_seconds()),
        path="/api/auth/google/callback",
        secure=redirect_uri.startswith("https://"),
        httponly=True,
        samesite="lax",
    )
    print("Google OAuth state cookie set on login response")
    return response


@router.get("/google/callback", include_in_schema=True)
async def google_login_callback(
    request: Request,
    state: str = Query(min_length=1),
    code: str = Query(min_length=1),
) -> RedirectResponse:
    client_id, client_secret, redirect_uri, frontend_redirect_uri = (
        google_oauth_configuration()
    )
    state_cookie = request.cookies.get("google_oauth_state")
    print("Returned state exists:", bool(state))
    print("Cookie state exists:", bool(state_cookie))
    print("State matches:", bool(state_cookie) and secrets.compare_digest(state, state_cookie))
    
    if not state_cookie or not secrets.compare_digest(state, state_cookie):
        raise HTTPException(
            status_code=400,
            detail="Google sign-in state validation failed.",
        )
    validate_google_state(state)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise HTTPException(
                    status_code=502,
                    detail="Google did not return an access token.",
                )

            profile_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            status_code=502,
            detail="Google sign-in could not be completed.",
        ) from error

    email_value = profile.get("email")
    google_subject = profile.get("sub")
    if (
        not isinstance(email_value, str)
        or profile.get("email_verified") is not True
        or not isinstance(google_subject, str)
        or not google_subject
    ):
        raise HTTPException(
            status_code=401,
            detail="Google did not provide a verified email address.",
        )

    email = email_value.strip().lower()
    full_name = profile.get("name")
    if not isinstance(full_name, str) or not full_name.strip():
        full_name = email.split("@", 1)[0]
    else:
        full_name = full_name.strip()[:120]

    password_digest = await asyncio.to_thread(
        hash_password, secrets.token_urlsafe(48)
    )
    try:
        user = await asyncio.to_thread(
            run_query,
            lambda connection: connection.execute(
                """
                INSERT INTO public.app_users (id, email, password_hash, full_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE
                    SET full_name = COALESCE(public.app_users.full_name, EXCLUDED.full_name)
                RETURNING id, email, full_name
                """,
                (uuid4(), email, password_digest, full_name),
            ).fetchone(),
        )
    except psycopg.Error as error:
        raise HTTPException(
            status_code=503,
            detail="The database could not create or load the Google account.",
        ) from error

    if user is None:
        raise HTTPException(
            status_code=500,
            detail="The database did not return the Google account.",
        )

    raw_login_code = secrets.token_urlsafe(32)
    code_hash = hashlib.sha256(raw_login_code.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + GOOGLE_LOGIN_CODE_LIFETIME

    def store_google_login_code(connection) -> None:
        connection.execute(
            "DELETE FROM public.google_login_codes WHERE expires_at <= now()"
        )
        connection.execute(
            """
            INSERT INTO public.google_login_codes (code_hash, user_id, expires_at)
            VALUES (%s, %s, %s)
            """,
            (code_hash, user["id"], expires_at),
        )

    try:
        await asyncio.to_thread(
            run_query,
            store_google_login_code,
        )
    except psycopg.Error as error:
        raise HTTPException(
            status_code=503,
            detail="The database could not complete the Google sign-in.",
        ) from error

    response = RedirectResponse(
        append_query_parameter(frontend_redirect_uri, "google_code", raw_login_code),
        status_code=303,
    )
    response.delete_cookie(
        key="google_oauth_state",
        path="/api/auth/google/callback",
        secure=redirect_uri.startswith("https://"),
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/google/exchange", response_model=AuthResult)
async def exchange_google_login_code(request: GoogleCodeExchange) -> AuthResult:
    code_hash = hashlib.sha256(request.code.encode("utf-8")).hexdigest()
    def consume_google_login_code(connection) -> dict[str, object] | None:
        user = connection.execute(
            """
            DELETE FROM public.google_login_codes
            WHERE code_hash = %s AND expires_at > now()
            RETURNING user_id
            """,
            (code_hash,),
        ).fetchone()
        if user is None:
            return None
        return connection.execute(
            """
            SELECT id, email, full_name
            FROM public.app_users
            WHERE id = %s
            """,
            (user["user_id"],),
        ).fetchone()

    account = await asyncio.to_thread(run_query, consume_google_login_code)
    if account is None:
        raise HTTPException(
            status_code=401,
            detail="The Google sign-in code is invalid, expired, or already used.",
        )
    return create_auth_result(account)


@router.post("/login", response_model=AuthResult)
async def login(credentials: Credentials) -> AuthResult:
    get_auth_secret()
    email = str(credentials.email).lower()
    try:
        user = await asyncio.to_thread(
            run_query,
            lambda connection: connection.execute(
                """
                SELECT id, email, full_name, password_hash
                FROM public.app_users
                WHERE email = %s
                """,
                (email,),
            ).fetchone(),
        )
    except psycopg.Error as error:
        raise HTTPException(
            status_code=503,
            detail="The database could not authenticate the account.",
        ) from error

    password_is_valid = await asyncio.to_thread(
        verify_password,
        credentials.password,
        user["password_hash"] if user else DUMMY_PASSWORD_HASH,
    )
    if user is None or not password_is_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return create_auth_result(user)
