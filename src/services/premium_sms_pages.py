"""Seiten und harte Kuerzung fuer Premium-SMS-Befehlsantworten (#3133).

Jede Premium-Antwort ist genau EINE Nachricht von hoechstens 153 Zeichen
(``CHANNEL_LIMITS["premium_sms"]``). Lange, statische Texte (HILFE, KUERZEL)
werden seitenweise abgefragt: ``paginate`` schneidet nur an Eintragsgrenzen,
haengt bis zur vorletzten Seite einen Verweis auf die naechste Seite an und
misst immer erst NACH ``fold_ascii`` (Falten kann verlaengern).
"""
from __future__ import annotations

from typing import Callable

from utils.ascii_fold import fold_ascii

#: Zeichenbudget einer Premium-SMS (GSM-7, Verkettungs-Sicherheitsabstand).
PREMIUM_LIMIT = 153
#: Kennzeichen am Ende einer hart gekuerzten Antwort (zaehlt ins Budget).
KUERZUNG = "~"


def kuerzen(text: str, limit: int = PREMIUM_LIMIT) -> str:
    """Falten, und bei Ueberlaenge hart kuerzen mit ``~`` als letztem Zeichen."""
    text = fold_ascii(text)
    if len(text) <= limit:
        return text
    return text[:limit - len(KUERZUNG)].rstrip() + KUERZUNG


def seiten(zeilen: list[str], *, verweis_fn: Callable[[int], str],
           limit: int = PREMIUM_LIMIT) -> list[str]:
    """Alle Seiten: gierig ganze Eintraege, Verweis im Budget, letzte ohne Verweis."""
    rest = [fold_ascii(z) for z in zeilen if z.strip()]
    ergebnis: list[str] = []
    while rest:
        if len("\n".join(rest)) <= limit:
            ergebnis.append("\n".join(rest))
            break
        verweis = fold_ascii(verweis_fn(len(ergebnis) + 2))
        budget = limit - len(verweis) - 1
        seite: list[str] = []
        while rest and len("\n".join(seite + [rest[0]])) <= budget:
            seite.append(rest.pop(0))
        if not seite:
            seite.append(kuerzen(rest.pop(0), budget))
        ergebnis.append("\n".join(seite) + "\n" + verweis)
    return ergebnis


def paginate(zeilen: list[str], page: int, *, verweis_fn: Callable[[int], str],
             limit: int = PREMIUM_LIMIT) -> str:
    """Seite ``page`` (1-basiert); ``page`` <= 0 ergibt Seite 1, ueber N ``""``."""
    alle = seiten(zeilen, verweis_fn=verweis_fn, limit=limit)
    page = max(page, 1)
    return alle[page - 1] if page <= len(alle) else ""


def seitenzahl(value: str | None) -> int:
    """Seitenargument des Befehls: nicht numerisch oder <= 0 ergibt Seite 1."""
    try:
        return max(int((value or "").split()[0]), 1)
    except (ValueError, IndexError):
        return 1
