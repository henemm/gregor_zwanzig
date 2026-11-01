"""Einzige Aufloesungsstelle der Nutzersprache im Python-Core (Issue #2646).

Go schreibt ``language`` (top-level) in ``users/<id>/user.json``; Python liest
es nur hier. Leer, fehlend oder unbekannt bedeutet ``de`` (ADR-0104 Nr. 9).
Kein Prozess- oder Modulzustand: jeder Aufruf liest die Datei neu.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

Lang = Literal["de", "en"]

_SPRACHEN: frozenset[str] = frozenset({"de", "en"})


def _gueltig(wert: Any) -> Lang | None:
    return wert if isinstance(wert, str) and wert in _SPRACHEN else None  # type: ignore[return-value]


def language_from_user_dict(data: dict) -> Lang:
    """Top-Level ``language`` > ``preferences.language`` > ``de``."""
    if not isinstance(data, dict):
        return "de"
    prefs = data.get("preferences")
    aus_prefs = prefs.get("language") if isinstance(prefs, dict) else None
    return _gueltig(data.get("language")) or _gueltig(aus_prefs) or "de"


def resolve_user_lang(user_id: str, data_dir: str | Path | None = None) -> Lang:
    """Sprache des Nutzers ``user_id``; jeder Fehler ergibt ``de`` ohne Ausnahme.

    ``data_dir=None`` liest unter ``get_data_root()`` (Testisolation #1133).
    Eine unsichere Kennung (``VALID_USER_ID_RE``) wird nie in einen Pfad gebaut.
    """
    try:
        # Lokaler Import: app.loader importiert dieses Modul (Zirkularitaet).
        from app.loader import get_data_root, is_valid_user_id

        if not is_valid_user_id(user_id):
            return "de"
        root = get_data_root() if data_dir is None else Path(data_dir)
        pfad = root / "users" / user_id / "user.json"
        return language_from_user_dict(json.loads(pfad.read_text(encoding="utf-8")))
    except Exception:
        return "de"
