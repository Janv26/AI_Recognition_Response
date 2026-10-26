from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

if TYPE_CHECKING:
    from app.api.dependencies import AuthContext

T = TypeVar("T")


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=503,
            detail="The server is missing its DATABASE_URL configuration.",
        )
    return database_url


def run_query(operation: Callable[[psycopg.Connection], T]) -> T:
    try:
        with psycopg.connect(
            get_database_url(),
            row_factory=dict_row,
            connect_timeout=10,
        ) as connection:
            with connection.transaction():
                connection.execute("SET LOCAL statement_timeout = '15s'")
                return operation(connection)
    except psycopg.OperationalError as error:
        raise HTTPException(
            status_code=503,
            detail="The database is unavailable.",
        ) from error


def run_as_user(auth: AuthContext, operation: Callable[[psycopg.Connection], T]) -> T:

    claims = json.dumps({"sub": auth.user_id, "role": "authenticated"})
    try:
        with psycopg.connect(
            get_database_url(),
            row_factory=dict_row,
            connect_timeout=10,
        ) as connection:
            with connection.transaction():
                connection.execute("SET LOCAL ROLE authenticated")
                connection.execute("SET LOCAL statement_timeout = '15s'")
                connection.execute(
                    "SELECT set_config('request.jwt.claims', %s, true)",
                    (claims,),
                )
                connection.execute(
                    "SELECT set_config('request.jwt.claim.sub', %s, true)",
                    (auth.user_id,),
                )
                return operation(connection)
    except psycopg.OperationalError as error:
        raise HTTPException(
            status_code=503,
            detail="The database is unavailable.",
        ) from error
    except psycopg.Error as error:
        raise HTTPException(
            status_code=502,
            detail="The database request failed.",
        ) from error
