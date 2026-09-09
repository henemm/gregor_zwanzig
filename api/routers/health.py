"""Health check endpoint."""
from fastapi import APIRouter

from app.config import Settings, resolve_public_host

router = APIRouter()


@router.get("/health")
def health():
    # #2272: derselbe Helper wie die Render-Stellen — eine zweite, eigene
    # Ableitung wuerde nur sich selbst bestaetigen, nicht die wirksame Config.
    return {
        "status": "ok",
        "version": "0.1.0",
        "public_host": resolve_public_host(Settings()),
    }
