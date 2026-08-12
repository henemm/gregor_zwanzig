"""TDD RED — Issue #1680 Scheibe 1, AC-8/AC-9: die Herkunfts-Angabe ueberlebt
die Wetter-Schnappschuss-Persistenz, und ein ALTER Schnappschuss ohne das neue
Feld laedt und rendert unveraendert weiter.

SPEC: docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md (D9).
RED-Ursache: ``SegmentWeatherSummary`` kennt kein Feld
``thunder_level_max_signals`` -> ``TypeError``/``AttributeError``.
Kein Mock-Theater: echte ``WeatherSnapshotService.save()``/``load()`` gegen das
isolierte Daten-Wurzelverzeichnis der Test-Suite, echter Renderer.
"""
from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.models import (  # noqa: E402
    GPXPoint, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from app.user import ComparisonResult, LocationResult, SavedLocation  # noqa: E402
from output.renderers.comparison import render_compare_email  # noqa: E402

from tests.tdd.test_thunder_origin_compare import _html_zellen  # noqa: E402

_TRIP = "tdd-1680-herkunft"
_TAG = date(2026, 8, 6)


def _segment(aggregiert: SegmentWeatherSummary) -> SegmentWeatherData:
    punkt = GPXPoint(lat=47.0, lon=12.0)
    return SegmentWeatherData(
        segment=TripSegment(
            segment_id=1, start_point=punkt, end_point=punkt,
            start_time=datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 6, 18, 0, tzinfo=timezone.utc),
            duration_hours=6.0, distance_km=5.0, ascent_m=300.0, descent_m=100.0,
        ),
        timeseries=None, aggregated=aggregiert,
        fetched_at=datetime(2026, 8, 5, 18, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def test_ac8_snapshot_roundtrip_erhaelt_die_herkunft(caplog):
    """AC-8: Given ein versendeter Schnappschuss traegt die Herkunfts-Angabe,
    When er gespeichert und spaeter wieder geladen wird, Then kommt dieselbe
    Angabe zurueck -- ohne dass ein Serialisierungsfehler sie still (nur als
    ``logger.warning``) verschluckt."""
    from services.weather_snapshot import WeatherSnapshotService

    dienst = WeatherSnapshotService(user_id="tdd-1680")
    segment = _segment(SegmentWeatherSummary(
        temp_max_c=20.0, thunder_level_max=ThunderLevel.HIGH,
        thunder_level_max_signals=["cape", "blitzpotenzial"],
    ))
    with caplog.at_level(logging.WARNING, logger="services.weather_snapshot"):
        dienst.save(_TRIP, [segment], _TAG)
    geladen = dienst.load(_TRIP)
    warnungen = [r for r in caplog.records if r.name == "services.weather_snapshot"]

    assert not warnungen, (
        f"Das Speichern darf nicht in den Warn-Pfad laufen (dort geht der "
        f"Schnappschuss still verloren): {[r.message for r in warnungen]!r}")
    assert geladen is not None, "Der Schnappschuss muss ladbar sein."
    assert geladen[0].aggregated.thunder_level_max_signals == ["cape", "blitzpotenzial"], (
        f"Die Herkunft muss den Roundtrip unveraendert ueberstehen: "
        f"{geladen[0].aggregated.thunder_level_max_signals!r}")


def test_ac9_alter_schnappschuss_ohne_feld_laedt_und_rendert_ohne_herkunft():
    """AC-9: Given ein vor dieser Aenderung erzeugter Schnappschuss kennt das
    neue Feld nicht, When er geladen und die Vergleichsmail gerendert wird,
    Then steht das Feld auf ``None``, die Stufe erscheint unveraendert und es
    gibt weder Fehler noch Herkunfts-Zusatz."""
    from services.weather_snapshot import _deserialize_summary

    alt = _deserialize_summary({
        "temp_max_c": 20.0, "thunder_level_max": "HIGH", "hail_flag": None,
    })
    assert alt.thunder_level_max_signals is None, (
        f"Ein Alt-Schnappschuss ohne das Feld muss mit None laden: "
        f"{alt.thunder_level_max_signals!r}")

    ort = LocationResult(
        location=SavedLocation(id="altort", name="Altort", lat=47.0, lon=12.0,
                               elevation_m=1000),
        score=50, hourly_data=[], thunder_level_max=alt.thunder_level_max,
    )
    html, _ = render_compare_email(
        ComparisonResult(locations=[ort], time_window=(12, 20), target_date=_TAG,
                         created_at=datetime(2026, 8, 5, 18, 0)),
        enabled_metrics=["thunder_max"], hourly_enabled=False,
    )
    assert _html_zellen(html) == ["hoch"], (
        f"Ohne gespeicherte Herkunft zeigt die Zeile nur die Stufe: "
        f"{_html_zellen(html)!r}")
