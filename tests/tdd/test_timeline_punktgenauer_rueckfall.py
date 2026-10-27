"""TDD RED -- Issue #2220 C5-38: Timeline-Mischfall behauptet Ungemessenes.

``_mit_datiertem_rueckfall`` (``src/services/trip_command_processor.py:1390-
1446``) faellt die Entscheidung "Anker behalten oder datierten Snapshot
nachziehen" heute PRO TAG, nicht pro Punkt: traegt IRGENDEIN Punkt des Tages
Werte, bleibt der GANZE Tag unveraendert -- auch seine leeren Nachbarn. Ein
solcher Nachbar rendert aktiv "0.0 mm" Regen und "kein" Gewitter, wo nichts
gemessen wurde. AC-4 bis AC-6 pruefen die neue PUNKTGENAUE Aufloesung, deren
Zuordnung zwischen Anker- und Snapshot-Punkt ueber ``label`` (Segment-ID,
``weather_extractor.py:125``) laeuft.

Spec: docs/specs/modules/fix_2220_telegram_kommando_befunde.md
Kontext: docs/context/fix-2220-telegram-kommando-befunde.md

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz. Echte
``Trip``/``Stage``/``Waypoint``-Objekte, echte Snapshot-Dateien ueber
``WeatherSnapshotService``, echter ``TripCommandProcessor`` ueber ``process()``.
Die Datenwurzel isoliert die projektweite autouse-Fixtur
(``tests/conftest.py::_isolate_data_root``).

Pfadregel #1409: der Pruefling wird relativ zur eigenen Testdatei aufgeloest.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import services.trip_command_processor as _tcp
from app.loader import save_trip
from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment
from app.trip import Stage, Trip, Waypoint
from services.trip_command_processor import CommandResult, InboundMessage, TripCommandProcessor
from services.weather_snapshot import WeatherSnapshotService

_BAUM = Path(__file__).resolve().parents[2]
_PRUEFLING = Path(_tcp.__file__).resolve()
assert _PRUEFLING.is_relative_to(_BAUM), (
    f"Pfadregel #1409 verletzt: der Pruefling liegt unter {_PRUEFLING}, "
    f"diese Testdatei aber unter {_BAUM}."
)

KORSIKA = (42.10, 9.00)
HEUTE = date(2026, 9, 10)
EMPFANGEN_UTC = datetime(2026, 9, 10, 6, 0, tzinfo=timezone.utc)
LUECKE = "noch keine Wetterdaten"

# seg_id=1 (08:00 UTC -> 10:00 Ortszeit, Korsika im September UTC+2) traegt
# im Anker durchgehend Werte; seg_id=2 (10:00 UTC -> 12:00 Ortszeit) ist der
# Mischfall-Punkt, den AC-4/AC-5 unterschiedlich beantworten.
_ANK_1 = datetime(HEUTE.year, HEUTE.month, HEUTE.day, 8, 0, tzinfo=timezone.utc)
_ANK_2 = datetime(HEUTE.year, HEUTE.month, HEUTE.day, 10, 0, tzinfo=timezone.utc)


def _stage() -> Stage:
    lat, lon = KORSIKA
    return Stage(
        id="S1", name="Etappe", date=HEUTE,
        waypoints=[
            Waypoint(id="S1-A", name="Start", lat=lat, lon=lon, elevation_m=500),
            Waypoint(id="S1-B", name="Ziel", lat=lat + 0.05, lon=lon + 0.05, elevation_m=800),
        ],
    )


def _trip(trip_id: str) -> Trip:
    trip = Trip(id=trip_id, name=trip_id, stages=[_stage()])
    save_trip(trip, "default")
    return trip


def _seg(ankunft_utc: datetime, *, seg_id: int, leer: bool = False,
        temp_min: float = 0.0, temp_max: float = 0.0) -> SegmentWeatherData:
    """Ein Wetter-Wegpunkt; ``leer=True`` baut den inhaltsleeren
    Fehler-Platzhalter (alle Metrikfelder ``None``, F005-Muster)."""
    lat, lon = KORSIKA
    segment = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1400.0),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=1500.0),
        start_time=ankunft_utc - timedelta(hours=1), end_time=ankunft_utc,
        duration_hours=1.0, distance_km=3.0, ascent_m=50.0, descent_m=0.0,
    )
    aggregiert = (SegmentWeatherSummary() if leer else
                 SegmentWeatherSummary(temp_min_c=temp_min, temp_max_c=temp_max, wind_max_kmh=15.0))
    return SegmentWeatherData(
        segment=segment, timeseries=None, aggregated=aggregiert,
        fetched_at=ankunft_utc, provider="test",
    )


def _befehl(trip: Trip, body: str) -> CommandResult:
    return TripCommandProcessor().process(InboundMessage(
        channel="telegram", trip_name=trip.name, body=body, sender="test",
        received_at=EMPFANGEN_UTC, user_id="default",
    ))


# ═══════════════════════════ AC-4 ════════════════════════════════════════════


def test_ac4_nicht_tragender_ankerpunkt_wird_durch_datierten_snapshot_ersetzt():
    """AC-4.

    GIVEN der Anker traegt fuer HEUTE ZWEI Punkte -- einen mit Werten
          (10-18 °C) und einen leeren Platzhalter (label '2') --, der datierte
          Snapshot traegt fuer DENSELBEN Punkt (label '2') echte Werte
          (21-29 °C),
    WHEN  ``timeline_heute`` abgefragt wird,
    THEN  bleibt der tragende Punkt unveraendert (AC-7-Regression: Anker
          schlaegt Snapshot) UND der nicht-tragende Punkt zeigt die Werte des
          datierten Snapshots -- keine Zeile zeigt '?-? °C'.
    """
    trip = _trip("ac4-mischfall")
    svc = WeatherSnapshotService("default")
    svc.save(trip.id, [
        _seg(_ANK_1, seg_id=1, temp_min=10.0, temp_max=18.0),
        _seg(_ANK_2, seg_id=2, leer=True),
    ], HEUTE)
    svc.save_dated(trip.id, HEUTE, [
        _seg(_ANK_2, seg_id=2, temp_min=21.0, temp_max=29.0),
    ])

    body = _befehl(trip, "### query: timeline_heute").confirmation_body

    assert "🌡 ?–? °C" not in body, (
        f"AC-4: mindestens eine Zeile zeigt weiterhin '🌡 ?–? °C':\n{body}"
    )
    assert "🕐 10:00" in body and "🌡 10–18 °C" in body, (
        f"AC-4: der tragende Ankerpunkt fehlt oder ist veraendert:\n{body}"
    )
    assert "🕐 12:00" in body and "🌡 21–29 °C" in body, (
        f"AC-4: die Werte des datierten Snapshots fuer den nicht-tragenden "
        f"Punkt fehlen:\n{body}"
    )


# ═══════════════════════════ AC-5 ════════════════════════════════════════════


def test_ac5_zeitpunkt_ohne_werte_in_beiden_quellen_fehlt_vollstaendig():
    """AC-5.

    GIVEN derselbe Mischfall wie AC-4, aber der datierte Snapshot traegt fuer
          label '2' ebenfalls KEINE Werte,
    WHEN  ``timeline_heute`` abgefragt wird,
    THEN  fehlt der Zeitpunkt (12:00) VOLLSTAENDIG in der Ausgabe -- nicht nur
          '?-? °C', auch der Zeitstempel selbst kommt nicht mehr vor. Der
          tragende Nachbarpunkt (10:00) bleibt unveraendert.
    """
    trip = _trip("ac5-beide-leer")
    svc = WeatherSnapshotService("default")
    svc.save(trip.id, [
        _seg(_ANK_1, seg_id=1, temp_min=10.0, temp_max=18.0),
        _seg(_ANK_2, seg_id=2, leer=True),
    ], HEUTE)
    svc.save_dated(trip.id, HEUTE, [
        _seg(_ANK_2, seg_id=2, leer=True),
    ])

    body = _befehl(trip, "### query: timeline_heute").confirmation_body

    assert "🕐 10:00" in body and "🌡 10–18 °C" in body, (
        f"Testaufbau: der tragende Nachbarpunkt fehlt:\n{body}"
    )
    assert "🕐 12:00" not in body, (
        f"AC-5: der Zeitstempel des beidseitig leeren Punkts erscheint noch, "
        f"obwohl weder Anker noch Snapshot Werte tragen:\n{body}"
    )
    assert "🌡 ?–? °C" not in body, (
        f"AC-5: eine Fragezeichen-Zeile ist stehen geblieben statt entfernt:\n{body}"
    )


# ═══════════════════════════ AC-6 ════════════════════════════════════════════


def test_ac6_tag_ohne_jede_tragende_quelle_zeigt_ehrliche_datenluecke():
    """AC-6.

    GIVEN der Anker traegt fuer HEUTE ZWEI Punkte, KEINER traegt Werte, und es
          existiert kein datierter Snapshot fuer HEUTE,
    WHEN  ``glance``, ``timeline_heute`` und ``heute_gewitter`` abgefragt
          werden,
    THEN  erscheint in allen drei Antworten die ehrliche Datenluecken-Meldung
          -- keine Fragezeichen-Zeile.
    """
    trip = _trip("ac6-alles-leer")
    WeatherSnapshotService("default").save(trip.id, [
        _seg(_ANK_1, seg_id=1, leer=True),
        _seg(_ANK_2, seg_id=2, leer=True),
    ], HEUTE)

    for query, marker in (
        ("### query: timeline_heute", "timeline_heute"),
        ("glance", "glance"),
        ("gewitter", "heute_gewitter"),
    ):
        body = _befehl(trip, query).confirmation_body
        assert "🌡 ?–? °C" not in body, (
            f"AC-6 ({marker}): eine Fragezeichen-Zeile verdeckt die ehrliche "
            f"Fehlanzeige:\n{body}"
        )
        assert LUECKE in body, (
            f"AC-6 ({marker}): erwartete Datenluecken-Meldung {LUECKE!r} fehlt:\n{body}"
        )
