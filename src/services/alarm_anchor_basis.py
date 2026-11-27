"""Reine Auswahl der Alarm-Vergleichsbasis je Kanal (Issue #1987 S2, ADR-0056).

Ohne I/O: die Aufrufer laden Briefing-Anker und Kanal-Merker selbst und
reichen sie hier herein. Regel ("Variante B'"):

* je Kanal gilt der NEUESTE gueltige Stand aus {Briefing-Anker, Merker dieses
  Kanals}; gueltig = Alter <= `max_age` und -- fuer den Merker -- gleicher
  Tagesbezug (`target_date`) wie der Briefing-Anker (beide leer = gleich).
  Ein Merker eines anderen Kanals fliesst nie ein.
* der gemeinsame Lauf vergleicht gegen die AELTESTE Kanal-Basis.

SPEC: docs/specs/modules/fix_1987_s2_compare_kanal_anker.md
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional


def _utc(ts: datetime) -> datetime:
    """Hausnorm #1345: naive Zeitstempel sind UTC."""
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def ist_frisch(point, *, now: datetime, max_age: timedelta) -> bool:
    return now - _utc(point.fetched_at) <= max_age


def kanal_basis(briefing, merker, *, now: datetime, max_age: timedelta):
    """Neuester gueltiger Stand EINES Kanals oder `None`.

    Ohne Briefing-Anker gibt es keinen Tagesbezug, dem der Merker
    widersprechen koennte; dann zaehlt allein sein Alter."""
    kandidaten = []
    if briefing is not None and ist_frisch(briefing, now=now, max_age=max_age):
        kandidaten.append(briefing)
    if (
        merker is not None
        and ist_frisch(merker, now=now, max_age=max_age)
        and (briefing is None or merker.target_date == briefing.target_date)
    ):
        kandidaten.append(merker)
    return max(kandidaten, key=lambda p: _utc(p.fetched_at), default=None)


def aelteste_basis(basen: Iterable) -> Optional[object]:
    """Aelteste der gueltigen Kanal-Basen (`None`-Eintraege zaehlen nicht)."""
    gueltig = [b for b in basen if b is not None]
    return min(gueltig, key=lambda p: _utc(p.fetched_at), default=None)
