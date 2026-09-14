"""Selbsttest des Ortstag-Helfers (Issue #2314, AC-5).

`tests.helpers.ortstag.ortstag(lat, lon, *, now_utc=None) -> date` liefert den
Kalendertag AM ORT der uebergebenen Koordinaten -- nicht den Kalendertag der
fixierten Prozesszone `America/St_Johns` (#1402) und nicht den UTC-Kalendertag.
Diese Datei ist der Selbsttest des Helfers selbst -- die Sollwerte stehen
deshalb als LITERALE hier, nie aus `tz_for_coords()`/`zoneinfo` berechnet,
sonst pruefte der Test nur seine eigene Kopie (Tautologie-Verbot, Spec
Abschnitt "Explizit NICHT umgestellt").

Der Helfer existiert zum Zeitpunkt dieser RED-Phase noch nicht -- der Import
auf Modulebene macht die Datei deshalb absichtlich mit einem
`ModuleNotFoundError` rot.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from freezegun import freeze_time

from tests.helpers.ortstag import ortstag

# Drei Zonen, die im Kontrollzeitraum (22:00-04:30 UTC, Spec-Nachtfenster)
# unterschiedlich vom UTC-Kalendertag und von der Prozesszone St. John's
# abweichen.
_TIROL = (47.0, 11.0)  # UTC+2 im September (CEST)
_REYKJAVIK = (64.13, -21.90)  # UTC+0, keine Sommerzeit
_KALIFORNIEN = (39.19, -120.24)  # UTC-7 im September (PDT)


@pytest.mark.parametrize(
    "lat_lon,now_utc,erwartet",
    [
        # 23:00 UTC: Tirol ist schon ueber Mitternacht, Reykjavik und
        # Kalifornien noch nicht.
        (_TIROL, datetime(2026, 9, 14, 23, 0, tzinfo=timezone.utc), date(2026, 9, 15)),
        (_REYKJAVIK, datetime(2026, 9, 14, 23, 0, tzinfo=timezone.utc), date(2026, 9, 14)),
        (_KALIFORNIEN, datetime(2026, 9, 14, 23, 0, tzinfo=timezone.utc), date(2026, 9, 14)),
        # 00:30 UTC (Folgetag): jetzt ist auch Reykjavik ueber Mitternacht.
        (_REYKJAVIK, datetime(2026, 9, 15, 0, 30, tzinfo=timezone.utc), date(2026, 9, 15)),
        # 04:00 UTC: Kalifornien liegt noch im Vortag, Tirol schon im Folgetag.
        (_KALIFORNIEN, datetime(2026, 9, 15, 4, 0, tzinfo=timezone.utc), date(2026, 9, 14)),
        (_TIROL, datetime(2026, 9, 15, 4, 0, tzinfo=timezone.utc), date(2026, 9, 15)),
    ],
)
def test_ortstag_liefert_den_kalendertag_am_ort(lat_lon, now_utc, erwartet):
    """GIVEN Koordinaten in einer von drei Zonen und ein fester UTC-Zeitpunkt
    WHEN `ortstag(lat, lon, now_utc=...)` aufgerufen wird
    THEN liefert er den Kalendertag DIESER Ortszone -- nicht den UTC-Tag und
    nicht den Kalendertag der Prozesszone St. John's.
    """
    lat, lon = lat_lon
    ergebnis = ortstag(lat, lon, now_utc=now_utc)

    assert ergebnis == erwartet, (
        f"ortstag({lat}, {lon}, now_utc={now_utc.isoformat()}) lieferte "
        f"{ergebnis} statt {erwartet}"
    )


def test_ortstag_liest_die_uhr_wenn_now_utc_fehlt():
    """GIVEN keine explizite `now_utc` UND eine auf 2026-09-14T23:00:00+00:00
    gestellte Uhr (freezegun)
    WHEN `ortstag(47.0, 11.0)` ohne `now_utc` aufgerufen wird
    THEN liefert er trotzdem den Ortstag in Tirol (2026-09-15) -- obwohl
    `date.today()` im selben Block noch den 2026-09-14 zeigt. Messgrenze:
    unter freezegun ist `date.today()` der UTC-Tag, nicht der Tag der
    fixierten Prozesszone St. John's (#1402). Belegt: der Helfer rechnet
    selbst die Ortszeit um, statt nur einen Kalendertag weiterzureichen.
    """
    with freeze_time("2026-09-14T23:00:00+00:00"):
        assert date.today() == date(2026, 9, 14), (
            "Vorbedingung: `date.today()` (unter freezegun der UTC-Tag) muss "
            "hier noch den 14.09. zeigen -- sonst prueft der Test die falsche "
            "Abweichung"
        )
        ergebnis = ortstag(47.0, 11.0)

    assert ergebnis == date(2026, 9, 15), (
        f"ortstag(47.0, 11.0) ohne now_utc lieferte {ergebnis} statt "
        f"date(2026, 9, 15) -- der Helfer muss selbst die aktuelle Uhrzeit "
        f"lesen und in die Ortszone umrechnen"
    )


def test_ortstag_ohne_argumente_ist_typeerror():
    """GIVEN der Helfer ohne jedes Argument
    WHEN `ortstag()` aufgerufen wird
    THEN scheitert der Aufruf mit `TypeError` -- `lat`/`lon` sind
    Pflichtparameter ohne Default. Ein stiller Rueckfall auf eine
    Standardkoordinate wuerde genau den Fehler reproduzieren, den diese
    Lieferung behebt.
    """
    with pytest.raises(TypeError):
        ortstag()  # type: ignore[call-arg]


def test_ortstag_nur_mit_breitengrad_ist_typeerror():
    """GIVEN der Helfer nur mit `lat`, ohne `lon`
    WHEN `ortstag(47.0)` aufgerufen wird
    THEN scheitert der Aufruf ebenfalls mit `TypeError` -- `lon` ist genauso
    Pflicht wie `lat`.
    """
    with pytest.raises(TypeError):
        ortstag(47.0)  # type: ignore[call-arg]
