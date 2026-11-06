"""#2744 AC-3/AC-6: gemeinsame Gestern-Zone-Hilfe fuer die Prozesszonen-Tests.

RED heute: ``tests/helpers/gestern_zone.py`` existiert nicht (ImportError).

Die Hilfe waehlt fuer die ECHTE Startzeit eine Zone, die den GANZEN UTC-Tag
traegt (Prozesstag = UTC-Tag - 1). Gemessen: ``<-24>+24`` tut das um 00:00:00,
23:45:00 und 23:59:59 UTC. Die Pruefung laeuft im Subprozess mit gesetztem
``TZ`` und gestellter echter Zeit per ``faketime``-freiem Weg: die Hilfe
bekommt den Zeitpunkt als Parameter, der Subprozess rechnet ihn mit der
gewaehlten Zone in den Prozesstag um.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from tests.helpers.gestern_zone import echte_utc_jetzt, gestern_zone_fuer


def _prozesstag_unter_zone(zone: str, jetzt_utc: datetime) -> str:
    """Kalendertag, den ein Prozess mit ``TZ=zone`` zu ``jetzt_utc`` sieht."""
    proc = subprocess.run(
        ["date", f"--date=@{int(jetzt_utc.timestamp())}", "+%F"],
        capture_output=True, text=True, timeout=10, check=True,
        env={"TZ": zone, "PATH": "/usr/bin:/bin"},
    )
    return proc.stdout.strip()


@pytest.mark.parametrize("stunde,minute,sekunde", [
    (0, 0, 0), (9, 15, 0), (9, 45, 0), (23, 45, 0), (23, 59, 59),
])
def test_ac3_gestern_zone_traegt_den_ganzen_utc_tag(stunde, minute, sekunde):
    jetzt = datetime(2026, 9, 15, stunde, minute, sekunde, tzinfo=timezone.utc)
    zone = gestern_zone_fuer(jetzt)
    erwartet = (jetzt.date() - timedelta(days=1)).isoformat()
    assert _prozesstag_unter_zone(zone, jetzt) == erwartet, (
        f"Zone {zone!r} traegt um {jetzt.isoformat()} nicht (UTC-Tag-1)."
    )


def test_ac3_zonenwahl_ist_von_der_tageszeit_unabhaengig():
    zonen = {
        gestern_zone_fuer(datetime(2026, 9, 15, h, 0, tzinfo=timezone.utc))
        for h in (0, 9, 10, 23)
    }
    assert len(zonen) == 1, f"Zonenwahl uneinheitlich: {zonen}"


def test_ac6_echte_uhr_wird_per_date_gelesen_nicht_per_datetime_now(monkeypatch):
    """Unter eingefrorener Uhr muss ``echte_utc_jetzt`` trotzdem die ECHTE
    Zeit liefern (Subprozess ``date -u``, #2096)."""
    from freezegun import freeze_time
    from freezegun.api import real_datetime

    # Vergleichsuhr unabhaengig von einer session-weit gestellten Wanduhr
    # (GZ_TEST_WALL_CLOCK_UTC) und nicht ueber ``date -u`` (sonst Zirkelschluss).
    echt_vorher = real_datetime.now(timezone.utc)
    with freeze_time("2001-01-01 00:00:00+00:00"):
        gelesen = echte_utc_jetzt()
    assert gelesen.year >= 2026
    assert abs((gelesen - echt_vorher).total_seconds()) < 120
