"""Core-Bind-Guard (Issue #2190): der Python-Core lauscht nur auf 127.0.0.1.

Spec: docs/specs/modules/core_bind_guard.md

Laeuft als erster Schritt im FastAPI-Lifespan. uvicorn ruft den Lifespan in
``Server.startup()`` VOR ``loop.create_server`` auf; ein ``RuntimeError`` hier
beendet uvicorn mit Exit 3, bevor je ein Socket lauscht.

Bewusst ohne Umgebungsvariable oder Flag zum Aufweichen: ein Override waere
selbst die Luecke.
"""

from __future__ import annotations

import gc
import logging

logger = logging.getLogger(__name__)

ALLOWED_HOST = "127.0.0.1"
_MAX_CHAIN_DEPTH = 32


def is_bind_allowed(host: object, uds: object, fd: object) -> bool:
    """Reine Pruefregel: erlaubt ist ausschliesslich ``127.0.0.1`` ohne UDS und FD."""
    return host == ALLOWED_HOST and uds is None and fd is None


def _chain_reaches(loaded_app: object, app: object) -> bool:
    """True, wenn die ``.app``-Kette der uvicorn-Middleware auf genau ``app`` zeigt."""
    current = loaded_app
    for _ in range(_MAX_CHAIN_DEPTH):
        if current is app:
            return True
        current = getattr(current, "app", None)
        if current is None:
            return False
    return False


def find_own_configs(app: object) -> list:
    """Alle ``uvicorn.Config``-Objekte im Prozess, die genau diese App bedienen."""
    try:
        from uvicorn import Config
    except ImportError:
        return []
    own = []
    for obj in gc.get_objects():
        if isinstance(obj, Config) and _chain_reaches(
            getattr(obj, "loaded_app", None), app
        ):
            own.append(obj)
    return own


def enforce_loopback_bind(app: object) -> None:
    """Bricht den Start ab, wenn die eigene uvicorn-Config nicht auf 127.0.0.1 bindet."""
    configs = find_own_configs(app)
    if not configs:
        logger.debug(
            "Bind-Guard (#2190): keine uvicorn-Config fuer diese App, nicht anwendbar"
        )
        return
    for config in configs:
        host = getattr(config, "host", None)
        port = getattr(config, "port", None)
        uds = getattr(config, "uds", None)
        fd = getattr(config, "fd", None)
        if is_bind_allowed(host, uds, fd):
            continue
        logger.critical(
            "Core-Start verweigert: Bind-Adresse host=%s port=%s uds=%s fd=%s ist nicht %s "
            "(Bind-Guard #2190, nur Loopback erlaubt)",
            host,
            port,
            uds,
            fd,
            ALLOWED_HOST,
        )
        raise RuntimeError(
            f"Bind-Guard #2190: Core darf nur auf {ALLOWED_HOST} lauschen, nicht host={host} port={port}"
        )
