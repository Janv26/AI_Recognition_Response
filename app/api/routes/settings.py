import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import AuthContext, get_auth_context
from app.database import run_as_user

router = APIRouter()


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    language: str | None = Field(default=None, min_length=1, max_length=40)
    voice_enabled: bool | None = Field(default=None, alias="voiceEnabled")


class SettingsResponse(BaseModel):
    name: str | None
    language: str
    voice_enabled: bool = Field(alias="voiceEnabled")


@router.get("/settings", response_model=SettingsResponse, include_in_schema=False)
@router.get("/users/settings", response_model=SettingsResponse)
async def get_settings(
    auth: AuthContext = Depends(get_auth_context),
) -> SettingsResponse:
    row = await asyncio.to_thread(
        run_as_user,
        auth,
        lambda connection: connection.execute(
            """
            SELECT full_name, language, voice_enabled
            FROM public.app_users
            WHERE id = %s
            """,
            (auth.user_id,),
        ).fetchone(),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="The account was not found.")

    return SettingsResponse(
        name=row["full_name"],
        language=row["language"],
        voiceEnabled=row["voice_enabled"],
    )


@router.put("/users/settings", response_model=SettingsResponse)
@router.put("/settings", response_model=SettingsResponse, include_in_schema=False)
async def update_settings(
    request: SettingsUpdate,
    auth: AuthContext = Depends(get_auth_context),
) -> SettingsResponse:
    values = request.model_dump()
    row = await asyncio.to_thread(
        run_as_user,
        auth,
        lambda connection: connection.execute(
            """
            UPDATE public.app_users
            SET full_name = COALESCE(%s, full_name),
                language = COALESCE(%s, language),
                voice_enabled = COALESCE(%s, voice_enabled)
            WHERE id = %s
            RETURNING full_name, language, voice_enabled
            """,
            (
                values["name"],
                values["language"],
                values["voice_enabled"],
                auth.user_id,
            ),
        ).fetchone(),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="The account was not found.")

    return SettingsResponse(
        name=row["full_name"],
        language=row["language"],
        voiceEnabled=row["voice_enabled"],
    )
