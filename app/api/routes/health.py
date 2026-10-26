import asyncio

from fastapi import APIRouter

from app.database import run_query

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    await asyncio.to_thread(
        run_query,
        lambda connection: connection.execute("SELECT 1").fetchone(),
    )
    return {"status": "ok", "database": "connected"}
