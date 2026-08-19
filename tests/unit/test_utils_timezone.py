"""Fix #1727 S5f: isolierter Unit-Test fuer den neuen zentralen Helfer
``to_utc()`` in ``src/utils/timezone.py``.

SPEC: docs/specs/modules/fix_1727_s5f_raw_astimezone_formbereinigung.md
(AC-1, AC-2)

Reine Formbereinigung, kein Bugfix: ``to_utc()`` ersetzt 9 rohe
``.astimezone(timezone.utc)``-Aufrufe in ``weather_cache.py``,
``segment_weather.py`` und ``trip_segments.py``. Diese Datei testet nur den
neuen Helfer isoliert -- die Golden-Master-Suiten fuer die Aufrufer bleiben
unveraendert (AC-4).

Kern-Schicht, netzfrei, keine Mocks (CLAUDE.md-Pflicht) -- reine
Werteberechnung ohne externe Abhaengigkeit.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from utils.timezone import to_utc


def test_to_utc_naiver_wert_wird_als_utc_gelabelt():
    """AC-1: Ein naiver (zonenloser) datetime-Wert wird nach Hausnorm #1345
    als UTC gelabelt -- kein Wert-Sprung, nur ``tzinfo`` gesetzt."""
    naive = datetime(2026, 8, 19, 12, 0)

    result = to_utc(naive)

    assert result == datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    assert result.hour == 12 and result.minute == 0, (
        "AC-1: der Wanduhrwert darf sich beim Labeln eines naiven "
        f"Zeitstempels nicht veraendern, bekam aber {result.isoformat()}."
    )


def test_to_utc_aware_wert_in_nicht_utc_zone_wird_echt_konvertiert():
    """AC-2 (Regressionsschutz Adversary-Fund F001): Ein aware Wert in einer
    Nicht-UTC-Zone wird ECHT nach UTC umgerechnet (Stundenverschiebung
    sichtbar), nicht nur mit ``tzinfo=UTC`` ueberschrieben."""
    aware = datetime(2026, 8, 19, 14, 0, tzinfo=timezone(timedelta(hours=2)))

    result = to_utc(aware)

    assert result == datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    assert result.hour == 12, (
        "AC-2: 14:00 in +02:00 muss nach 12:00 UTC konvertiert werden, "
        f"bekam aber {result.isoformat()} -- das waere nur ein "
        "tzinfo-Ersatz statt einer echten Konvertierung."
    )
