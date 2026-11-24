from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.database.connection import engine

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "application": "Inventra", "database": "disconnected"},
        )
    return {"status": "healthy", "application": "Inventra", "database": "connected"}
