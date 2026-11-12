"""Drossel fuer automatische Fehlerantworten im Mail-Eingang (Issue #2961).

Eine Fehlerantwort (unbekannter Befehl, unbekannter Trip, sonstiger Fehler)
geht je Nutzer hoechstens ``FEHLERANTWORTEN_JE_STUNDE``-mal in einem
gleitenden Fenster von einer Stunde raus. Das bricht Mail-Schleifen mit
Fremdsystemen, die nicht als automatisch gekennzeichnet sind, und begrenzt die
Last bei massenhaft eingehenden Mails.

Persistiert unter ``data/users/<user_id>/inbound_fehlerantworten.json``
(Liste von Unix-Zeitstempeln), damit die Grenze einen Neustart des Dienstes
ueberlebt. Erfolgreiche Befehlsantworten sind nicht betroffen.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time

from app.loader import get_data_dir

logger = logging.getLogger(__name__)

FEHLERANTWORTEN_JE_STUNDE = 5
_FENSTER_SEKUNDEN = 3600.0
_DATEINAME = "inbound_fehlerantworten.json"
_lock = threading.Lock()


def _lesen(pfad) -> list[float]:
    try:
        roh = json.loads(pfad.read_text())
        return [float(x) for x in roh] if isinstance(roh, list) else []
    except (OSError, ValueError, TypeError):
        return []


def fehlerantwort_erlaubt(user_id: str, *, now: float | None = None) -> bool:
    """``True`` und Versand vermerken, solange das Stundenkontingent reicht."""
    jetzt = time.time() if now is None else now
    ordner = get_data_dir(user_id)
    pfad = ordner / _DATEINAME
    with _lock:
        stempel = [s for s in _lesen(pfad) if 0 <= jetzt - s < _FENSTER_SEKUNDEN]
        if len(stempel) >= FEHLERANTWORTEN_JE_STUNDE:
            return False
        stempel.append(jetzt)
        try:
            ordner.mkdir(parents=True, exist_ok=True)
            tmp = pfad.with_name(pfad.name + ".tmp")
            tmp.write_text(json.dumps(stempel))
            os.replace(tmp, pfad)
        except OSError as e:
            logger.warning("Fehlerantwort-Drossel nicht speicherbar: %s", e)
        return True
