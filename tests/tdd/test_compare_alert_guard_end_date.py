"""Stilllegungs-Regel Merkmal 4 (``end_date``): Wiener Kalendertag und ungueltige Werte
(Issue #2422 S5, AC-21; Adversary-Findings F001/F002).

Die Uhr wird an der Stelle eingefroren, an der ``_end_date_passed`` sie bezieht
(``datetime.now(ZoneInfo(...))`` im Guard-Modul): eine echte ``datetime``-Unterklasse mit
festem Zeitpunkt, kein ``Mock``. Die Zeitpunkte sind so gewaehlt, dass ein Tausch der Zone
gegen UTC, Pacific/Auckland oder einen festen +1-Offset (Winter-/Sommerzeit) je einen Fall
kippt.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from services import compare_alert_guard as guard  # noqa: E402


def _einfrieren(monkeypatch, jetzt_utc: datetime) -> None:
    class _Fest(datetime):
        @classmethod
        def now(cls, tz=None):
            return jetzt_utc.astimezone(tz) if tz else jetzt_utc

    monkeypatch.setattr(guard, "datetime", _Fest)


def _utc(jahr, monat, tag, std, minute) -> datetime:
    return datetime(jahr, monat, tag, std, minute, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "jetzt, end_date, abgelaufen",
    [
        # Winter (CET, UTC+1): 23:30 UTC = 00:30 Wien am Folgetag -> abgelaufen (faengt UTC)
        (_utc(2026, 1, 15, 23, 30), "2026-01-15", True),
        # Winter: 22:30 UTC = 23:30 Wien, noch derselbe Tag -> aktiv (faengt Auckland)
        (_utc(2026, 1, 15, 22, 30), "2026-01-15", False),
        # Sommer (CEST, UTC+2): 22:30 UTC = 00:30 Wien am Folgetag -> abgelaufen (faengt UTC und +1)
        (_utc(2026, 6, 15, 22, 30), "2026-06-15", True),
        # Sommer: 21:30 UTC = 23:30 Wien, noch derselbe Tag -> aktiv (faengt Auckland)
        (_utc(2026, 6, 15, 21, 30), "2026-06-15", False),
        # Vortag ist immer abgelaufen, Zukunft nie
        (_utc(2026, 6, 15, 12, 0), "2026-06-14", True),
        (_utc(2026, 6, 15, 12, 0), "2026-06-16", False),
    ],
)
def test_end_date_wird_gegen_den_wiener_kalendertag_geprueft(monkeypatch, jetzt, end_date, abgelaufen):
    _einfrieren(monkeypatch, jetzt)
    assert guard.is_silenced({"end_date": end_date}) is abgelaufen


@pytest.mark.parametrize("end_date", ["2026-13-45", 20260101, "abc", None, ""])
def test_ungueltiges_end_date_wirft_nicht_und_gilt_als_nicht_abgelaufen(end_date):
    assert guard.is_silenced({"end_date": end_date}) is False
