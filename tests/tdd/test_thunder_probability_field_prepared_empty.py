"""TDD RED — Issue #1474 (S3 zu #1419), AC-10.

SPEC: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.3 Abschnitt 5

`ForecastDataPoint.thunder_probability_pct: Optional[int] = None` wird
angelegt -- die getrennte, vom PO ausdruecklich als eigenes, spaeter erst
befuelltes Feld benannte Wahrscheinlichkeits-Achse. In dieser Scheibe bleibt
es bei JEDEM Datenpunkt `None` (keine Quelle befuellt es) und hat KEINEN
Renderer-Anschluss.

RED-Ursache (heute): `ForecastDataPoint` kennt kein `thunder_probability_pct`
-> `TypeError: unexpected keyword argument` beim Konstruieren, bzw.
`AttributeError` beim Lesen.

Keine Mocks: echte reguläre Vorhersage ueber den Provider-Weg (Muster wie
AC-9), echte gerenderte Trip-Mail als Textsuche-Gegentest.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.models import ForecastDataPoint

# Repo-relative Auflösung ueber die eigene Testdatei (#1409-Pfadregel), nicht
# ueber einen festen Hauptrepo-Pfad.
_FIXTURE_DIR = str(Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo")


def test_ac10_feld_existiert_und_ist_standardmaessig_none():
    """Das Feld muss existieren und per Default None sein -- 'keine Aussage',
    nie '0%'."""
    dp = ForecastDataPoint(ts=datetime.now(timezone.utc))
    assert dp.thunder_probability_pct is None, (
        "thunder_probability_pct muss ohne explizite Belegung None sein "
        f"('keine Aussage'), erhalten {dp.thunder_probability_pct!r}"
    )


def test_ac10_feld_laesst_sich_explizit_setzen():
    """Vorbereitung fuer #1419 S6: das Feld ist beschreibbar, auch wenn es in
    dieser Scheibe von keiner Quelle befuellt wird."""
    dp = ForecastDataPoint(ts=datetime.now(timezone.utc), thunder_probability_pct=47)
    assert dp.thunder_probability_pct == 47


def test_ac10_regulaere_vorhersage_laesst_das_feld_ueberall_leer():
    """Given eine reguläre Vorhersage ueber den heutigen (unveraenderten)
    Provider-Weg / When sie abgerufen wird / Then traegt
    ForecastDataPoint.thunder_probability_pct bei JEDEM Datenpunkt None."""
    from app.config import Location
    from providers.fixture import FixtureProvider

    location = Location(latitude=47.0, longitude=11.0, name="Test")
    reihe = FixtureProvider(_FIXTURE_DIR).fetch_forecast(location)

    assert reihe.data, "Vorhersage ist leer -- Test kann nichts pruefen"
    assert all(dp.thunder_probability_pct is None for dp in reihe.data), (
        "Mindestens ein Datenpunkt traegt bereits einen Wahrscheinlichkeits-"
        "Wert -- diese Scheibe darf das Feld von KEINER Quelle befuellen"
    )


def test_ac10_gerenderte_beispiel_mail_erwaehnt_keine_gewitter_wahrscheinlichkeit():
    """Textsuche-Gegentest: eine gerenderte Beispiel-Mail darf kein
    Wahrscheinlichkeits-Wort/-Symbol fuer Gewitter enthalten -- das Feld hat
    in dieser Scheibe KEINEN Renderer-Anschluss."""
    from app.config import Location
    from output.renderers.trip_report import TripReportFormatter
    from providers.fixture import FixtureProvider

    location = Location(latitude=47.0, longitude=11.0, name="Test")
    reihe = FixtureProvider(_FIXTURE_DIR).fetch_forecast(location)
    for dp in reihe.data:
        dp.thunder_probability_pct = 47  # simuliert eine kuenftig befuellte Quelle

    from app.models import (
        GPXPoint,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=8.0),
        start_time=reihe.data[0].ts,
        end_time=reihe.data[-1].ts,
        duration_hours=4.0, distance_km=8.0, ascent_m=500, descent_m=0,
    )
    data = SegmentWeatherData(
        segment=seg, timeseries=reihe,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="fixture",
    )
    report = TripReportFormatter().format_email([data], "Test", "morning")
    combined = f"{report.email_plain}\n{report.email_html}".lower()
    for verboten in ("wahrscheinlichkeit", "%-gewitter", "gewitter-w"):
        assert verboten not in combined, (
            f"Gerenderte Mail erwaehnt '{verboten}' -- das vorbereitete Feld "
            "thunder_probability_pct darf in dieser Scheibe keinen "
            "Renderer-Anschluss haben"
        )
