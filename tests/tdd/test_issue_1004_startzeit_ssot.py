"""TDD RED — Issue #1004: Segment-Startzeit, eine maßgebliche Quelle (SSoT).

PO-verbindliche Regel (#1004): Es gibt genau EINE maßgebliche Startzeit pro
Etappe — ``stage.start_time``. ``Waypoint.time_window`` ist ein reines
GPX-Import-Artefakt ohne manuellen Schreibpfad und verliert JEDE Autorität
in der Prioritätskette von ``convert_trip_to_segments()`` — kein Flag,
keine Migration, gilt sofort für alle Trips inkl. Bestand.

Neue Kette: arrival_override > stage.start_time (i==0) > arrival_calculated
> Default 08:00. RED, weil die aktuelle Kette ``time_window`` weiterhin an
oberster Stelle liest (origin=None ≈ autoritativ → Bestand zeigt Importzeit).

Mock-frei: echte Trip-Dateien, echte Persistenz (``save_trip`` ist per
Issue #802 bit-identisch zu Go ``store.SaveTrip`` — beide berechnen
``arrival_calculated`` bei JEDEM Speichern neu ab ``stage.start_time``;
der Speicherpfad ist damit das Python-seitige Äquivalent des API-Schreibwegs),
echte Funktionsaufrufe gegen die SSoT ``services.trip_segments``.

SPEC: docs/specs/modules/issue_1004_startzeit_ssot.md
(AC-1, AC-2, AC-4, AC-5, AC-6, AC-7 — AC-3 in test_issue_1004_ssot_callers.py)
"""
from __future__ import annotations

import dataclasses
import logging
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest

from app.loader import load_trip, save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint
from services.trip_segments import convert_trip_to_segments
from utils.timezone import tz_for_coords

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAIN_REPO = Path("/home/hem/gregor_zwanzig")
_REFERENCE_REL = "data/users/henning/trips/74de939c.json"


def _reference_trip_path() -> Path:
    """Echter Bestandstrip (AC-1) — Worktree hat kein data/, Hauptrepo schon."""
    for root in (_REPO_ROOT, _MAIN_REPO):
        p = root / _REFERENCE_REL
        if p.exists():
            return p
    pytest.fail(f"Referenz-Bestandstrip {_REFERENCE_REL} nicht gefunden")


def _local_hhmm(segment) -> str:
    """UTC-Segmentzeit → lokale 'HH:MM' am Segment-Startpunkt."""
    tz = tz_for_coords(segment.start_point.lat, segment.start_point.lon)
    return segment.start_time.astimezone(tz).strftime("%H:%M")


def _local_hhmm_end(segment) -> str:
    """UTC-Segmentendzeit → lokale 'HH:MM' am Segment-Endpunkt."""
    tz = tz_for_coords(segment.end_point.lat, segment.end_point.lon)
    return segment.end_time.astimezone(tz).strftime("%H:%M")


def _to_minutes(hhmm: str) -> int:
    """'HH:MM' → Minuten seit Mitternacht (für Monotonie-Vergleiche)."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _imported_tw(hhmm: str) -> TimeWindow:
    """GPX-Import-Artefakt: TimeWindow wie segments_to_trip() es erzeugt."""
    t = time.fromisoformat(hhmm)
    return TimeWindow(start=t, end=t)


# ---------------------------------------------------------------------------
# AC-1 — Bestandstrip: konfigurierte Startzeit gewinnt OHNE Migration
# ---------------------------------------------------------------------------

def test_ac1_bestandstrip_rendert_konfigurierte_startzeit():
    """AC-1: echter VOR dem Fix gespeicherter Trip (74de939c.json,
    Etappe 'nach Sassenberg', start_time=14:00, Import-Zeiten 07:00/09:00/11:00)
    → Segment 1 beginnt 14:00, Kaskade 14:21/14:46, nirgends mehr 07:00."""
    trip = load_trip(_reference_trip_path())
    assert trip is not None, "Bestandstrip konnte nicht geladen werden"

    segments = convert_trip_to_segments(trip, date(2026, 7, 3))
    assert segments, "Segmentliste des Bestandstrips ist leer"

    starts = [_local_hhmm(s) for s in segments]
    assert starts[0] == "14:00", (
        f"Segment 1 beginnt {starts[0]} statt der konfigurierten "
        f"Etappen-Startzeit 14:00 (alle Startzeiten: {starts})"
    )
    assert starts[1] == "14:21" and starts[2] == "14:46", (
        f"Folgesegmente folgen nicht der Naismith-Kaskade 14:21/14:46: {starts}"
    )
    assert "07:00" not in starts, (
        f"Alte GPX-Importzeit 07:00 erscheint weiterhin: {starts}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Persistenz-Roundtrip: Startzeit-Änderung überlebt Reload
# ---------------------------------------------------------------------------

def test_ac2_persistenz_roundtrip_startzeit_aenderung(tmp_path):
    """AC-2: echter GPX-Import → Speichern → Reload → Startzeit ändern
    (Persistenz-Schreibweg = API-Äquivalent, Compute-on-Save #802) →
    erneuter Reload → Rendering zeigt die NEUE Startzeit."""
    from app.models import EtappenConfig
    from services.gpx_processing import (
        compute_full_segmentation,
        process_gpx_upload,
        segments_to_trip,
    )

    gpx_path = _REPO_ROOT / "frontend" / "e2e" / "fixtures" / "test-trip.gpx"
    assert gpx_path.exists(), f"GPX-Fixture fehlt: {gpx_path}"

    trip_date = date(2026, 8, 1)
    track = process_gpx_upload(
        gpx_path.read_bytes(), "test-trip.gpx", upload_dir=tmp_path
    )
    gpx_segments = compute_full_segmentation(
        track,
        EtappenConfig(),
        datetime.combine(trip_date, time(7, 0), tzinfo=timezone.utc),
    )
    trip = segments_to_trip(
        gpx_segments, track, trip_date, trip_name="TDD-1004-AC2 Roundtrip"
    )

    user_id = "tdd-1004-ac2"
    saved_path = save_trip(trip, user_id=user_id)
    reloaded = load_trip(saved_path)
    assert reloaded is not None

    # Startzeit ändern wie der API-Schreibweg: Feld setzen + speichern
    # (save_trip berechnet arrival_calculated neu — bit-identisch zu Go).
    new_start = time(14, 30)
    changed = dataclasses.replace(
        reloaded,
        stages=[dataclasses.replace(reloaded.stages[0], start_time=new_start)],
    )
    save_trip(changed, user_id=user_id)

    final = load_trip(saved_path)
    assert final is not None
    assert final.stages[0].start_time == new_start, (
        "start_time hat den Persistenz-Roundtrip nicht überlebt"
    )

    segments = convert_trip_to_segments(final, trip_date)
    assert segments, "Segmentliste nach Roundtrip leer"
    first = _local_hhmm(segments[0])
    assert first == "14:30", (
        f"Nach Reload beginnt Segment 1 um {first} statt der neu gesetzten "
        f"14:30 — #995-Fehlermodus 'wirkt nur im Speicher' besteht weiter"
    )


# ---------------------------------------------------------------------------
# AC-4 — arrival_override bleibt oberste Instanz
# ---------------------------------------------------------------------------

def test_ac4_arrival_override_bleibt_massgeblich():
    """AC-4: manuell gesetzter arrival_override (Issue #303) schlägt
    stage.start_time UND jede importierte time_window."""
    trip_date = date(2026, 8, 2)
    wp0 = Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500,
        time_window=_imported_tw("07:00"),
        arrival_override="13:37",
    )
    wp1 = Waypoint(
        id="G2", name="Ziel", lat=47.02, lon=11.02, elevation_m=600,
        time_window=_imported_tw("09:00"),
    )
    stage = Stage(id="T1", name="Override-Etappe", date=trip_date,
                  start_time=time(14, 0), waypoints=[wp0, wp1])
    trip = Trip(id="tdd-1004-ac4", name="AC4", stages=[stage])

    user_id = "tdd-1004-ac4"
    saved_path = save_trip(trip, user_id=user_id)
    reloaded = load_trip(saved_path)
    assert reloaded is not None
    assert reloaded.stages[0].waypoints[0].arrival_override == "13:37", (
        "arrival_override hat die Persistenz nicht überlebt"
    )

    segments = convert_trip_to_segments(reloaded, trip_date)
    assert segments, "Segmentliste leer"
    first = _local_hhmm(segments[0])
    assert first == "13:37", (
        f"Segment 1 beginnt {first} statt des manuellen arrival_override "
        f"13:37 (stage.start_time=14:00, importierte time_window=07:00)"
    )


# ---------------------------------------------------------------------------
# AC-5 — Mitternachts-Klemme: kein stiller Totalausfall der Etappe
# ---------------------------------------------------------------------------

def test_ac5_spaete_startzeit_kein_totalausfall(caplog):
    """AC-5: start_time=22:00 + lange Etappe → Naismith klemmt Folge-
    Ankünfte auf 23:59. Erstes Segment bleibt erhalten (Start 22:00),
    geklemmte Folgesegmente kollabieren geloggt — Liste nie leer."""
    trip_date = date(2026, 8, 3)
    # ~12 km Abstände → Ankünfte weit nach Mitternacht → Clamp auf 23:59
    coords = [(47.0, 11.0), (47.0, 11.16), (47.0, 11.32), (47.0, 11.48)]
    tws = ["07:00", "09:00", "11:00", "13:00"]
    waypoints = [
        Waypoint(
            id=f"G{i+1}", name=f"WP{i+1}", lat=lat, lon=lon,
            elevation_m=500, time_window=_imported_tw(tw),
        )
        for i, ((lat, lon), tw) in enumerate(zip(coords, tws))
    ]
    stage = Stage(id="T1", name="Nachtetappe", date=trip_date,
                  start_time=time(22, 0), waypoints=waypoints)
    trip = Trip(id="tdd-1004-ac5", name="AC5", stages=[stage])

    saved_path = save_trip(trip, user_id="tdd-1004-ac5")
    reloaded = load_trip(saved_path)
    assert reloaded is not None

    with caplog.at_level(logging.WARNING, logger="trip_segments"):
        segments = convert_trip_to_segments(reloaded, trip_date)

    assert segments, (
        "Kompletter stiller Totalausfall: späte Startzeit liefert leere "
        "Segmentliste"
    )
    first = _local_hhmm(segments[0])
    assert first == "22:00", (
        f"Segment 1 beginnt {first} statt der konfigurierten 22:00 "
        f"(importierte time_window 07:00 gewinnt weiterhin)"
    )
    # Geklemmte Folgesegmente kollabieren → muss nachvollziehbar geloggt sein.
    assert any(r.levelno >= logging.WARNING for r in caplog.records), (
        "Kollabierte (geklemmte) Folgesegmente wurden ohne Warnung verworfen"
    )


# ---------------------------------------------------------------------------
# AC-6 — Zwei-Nutzer-Isolation
# ---------------------------------------------------------------------------

def test_ac6_zwei_nutzer_isolation():
    """AC-6: Nutzer A ändert seine Etappen-Startzeit, Nutzer B nicht —
    beide sehen über denselben SSoT-Aufrufer nur ihre eigene Zeit."""
    from services.preview_service import PreviewService
    from services.trip_report_scheduler import TripReportSchedulerService

    trip_date = date(2026, 8, 4)

    def _make_trip(trip_id: str, start: time | None) -> Trip:
        wp0 = Waypoint(id="G1", name="Start", lat=47.0, lon=11.0,
                       elevation_m=500, time_window=_imported_tw("07:00"))
        wp1 = Waypoint(id="G2", name="Ziel", lat=47.02, lon=11.02,
                       elevation_m=600, time_window=_imported_tw("09:00"))
        stage = Stage(id="T1", name="Iso-Etappe", date=trip_date,
                      start_time=start, waypoints=[wp0, wp1])
        return Trip(id=trip_id, name=trip_id, stages=[stage])

    user_a, user_b = "tdd-1004-usera", "tdd-1004-userb"
    save_trip(_make_trip("tdd-1004-iso", time(15, 0)), user_id=user_a)
    save_trip(_make_trip("tdd-1004-iso", None), user_id=user_b)

    ps = PreviewService()
    results = {}
    for uid in (user_a, user_b):
        trip = ps._load_trip("tdd-1004-iso", uid)
        scheduler = TripReportSchedulerService(user_id=uid)
        segments = scheduler._convert_trip_to_segments(trip, trip_date)
        assert segments, f"Segmentliste leer für {uid}"
        results[uid] = _local_hhmm(segments[0])

    assert results[user_a] == "15:00", (
        f"Nutzer A sieht {results[user_a]} statt seiner neuen Startzeit 15:00"
    )
    assert results[user_b] == "08:00", (
        f"Nutzer B sieht {results[user_b]} statt seines Defaults 08:00"
    )
    assert results[user_a] != results[user_b], (
        "Cross-User-Vermischung: beide Nutzer sehen dieselbe Startzeit"
    )


# ---------------------------------------------------------------------------
# AC-7 — teilweise gefülltes arrival_calculated: keine stille Lücke
# ---------------------------------------------------------------------------

def test_ac7_teilweise_arrival_calculated_keine_stille_luecke():
    """AC-7: nur der MITTLERE Wegpunkt hat arrival_calculated=None
    (Self-Heal greift nicht, da nicht ALLE None sind) → alle Segmente
    erscheinen, Segment 1 beginnt bei stage.start_time."""
    trip_date = date(2026, 8, 5)
    wps = [
        Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500,
                 time_window=_imported_tw("07:00"), arrival_calculated="14:00"),
        Waypoint(id="G2", name="Mitte", lat=47.01, lon=11.01, elevation_m=550,
                 time_window=_imported_tw("09:00"), arrival_calculated=None),
        Waypoint(id="G3", name="Fast-Ziel", lat=47.02, lon=11.02,
                 elevation_m=600, time_window=_imported_tw("11:00"),
                 arrival_calculated="15:00"),
        Waypoint(id="G4", name="Ziel", lat=47.03, lon=11.03, elevation_m=650,
                 time_window=_imported_tw("13:00"), arrival_calculated="15:30"),
    ]
    stage = Stage(id="T1", name="Lücken-Etappe", date=trip_date,
                  start_time=time(14, 0), waypoints=wps)
    trip = Trip(id="tdd-1004-ac7", name="AC7", stages=[stage])

    segments = convert_trip_to_segments(trip, trip_date)
    assert segments, "Segmentliste leer"

    starts = [_local_hhmm(s) for s in segments if s.segment_id != "Ziel"]
    assert starts[0] == "14:00", (
        f"Segment 1 beginnt {starts[0]} statt stage.start_time 14:00 "
        f"(alle Startzeiten: {starts})"
    )
    numeric_ids = [s.segment_id for s in segments if s.segment_id != "Ziel"]
    assert numeric_ids == [1, 2, 3], (
        f"Stille Lücke: Segment-IDs {numeric_ids} statt [1, 2, 3] — ein "
        f"Wegpunkt ohne arrival_calculated darf kein Segment verschlucken"
    )
    # F001: die fehlende Zeit des mittleren Wegpunkts (G2) muss linear
    # zwischen G1 (14:00) und G3 (15:00) interpoliert werden — sonst
    # starten Segment 1 und Segment 2 beide um 14:00 (stille Duplikat-Startzeit).
    assert starts == ["14:00", "14:30", "15:00"], (
        f"Interpolierte Segmentstarts sind {starts} statt ['14:00', '14:30', "
        f"'15:00'] — G2 (arrival_calculated=None) muss linear zwischen G1 "
        f"und G3 interpoliert werden"
    )
    assert all(
        _to_minutes(starts[i]) < _to_minutes(starts[i + 1])
        for i in range(len(starts) - 1)
    ), (
        f"Segmentstarts {starts} sind nicht streng monoton steigend — "
        f"Duplikat-Startzeit deutet auf eine stille Zeit-Lücke hin"
    )


# ---------------------------------------------------------------------------
# F002 — Minuten-Spanne kleiner als Lücken-Anzahl: Rundung darf nicht auf
# die Vorgängerzeit kollabieren (Python-Banker's-Rounding-Falle)
# ---------------------------------------------------------------------------

def test_f002_minuten_spanne_rundung_kollabiert_nicht_auf_vorgaenger(caplog):
    """F002: G1=09:10 (stage.start_time), G2=None, G3=09:11 (arrival_calculated)
    — nur 1 Minute Spanne über 2 Interpolationsschritte verteilt. Mit Python-
    ``round()`` (Round-half-to-even) würde round(0.5)==0 den interpolierten
    Wegpunkt G2 auf 09:10 (== Vorgänger) kollabieren lassen → Segment 1
    kollabiert am end_dt<=start_dt-Guard. Mit kaufmännischer Rundung
    (math.floor(x + 0.5)) landet G2 stattdessen auf 09:11 — Segment 1
    (09:10→09:11) überlebt; Segment 2 (G2→G3, beide 09:11) kollabiert
    unvermeidbar (Minutenauflösung < Lückenzahl), aber GELOGGT, nicht still."""
    trip_date = date(2026, 8, 6)
    wps = [
        Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=500,
                 time_window=_imported_tw("07:00"), arrival_calculated=None),
        Waypoint(id="G2", name="Mitte", lat=47.001, lon=11.001, elevation_m=505,
                 time_window=_imported_tw("08:00"), arrival_calculated=None),
        Waypoint(id="G3", name="Ziel", lat=47.002, lon=11.002, elevation_m=510,
                 time_window=_imported_tw("09:00"), arrival_calculated="09:11"),
    ]
    stage = Stage(id="T1", name="F002-Etappe", date=trip_date,
                  start_time=time(9, 10), waypoints=wps)
    trip = Trip(id="tdd-1004-f002", name="F002", stages=[stage])

    with caplog.at_level(logging.WARNING, logger="trip_segments"):
        segments = convert_trip_to_segments(trip, trip_date)

    # (a) Segmentliste nicht leer
    assert segments, "F002: Segmentliste komplett leer — Totalausfall"

    non_ziel = [s for s in segments if s.segment_id != "Ziel"]
    assert non_ziel, (
        "F002: kein einziges Nicht-Ziel-Segment überlebt — Rundung hat "
        "Segment 1 (09:10→09:11) fälschlich kollabieren lassen"
    )

    # (b) Zeitfolge der überlebenden Segmente ist monoton nicht-fallend
    starts = [_local_hhmm(s) for s in non_ziel]
    assert all(
        _to_minutes(starts[i]) <= _to_minutes(starts[i + 1])
        for i in range(len(starts) - 1)
    ), f"F002: Segmentstarts {starts} sind nicht monoton nicht-fallend"

    # (d) interpolierter Zwischenwert (Segment-1-Ende) ist NICHT die
    # Vorgängerzeit — beweist kaufmännische statt Banker's-Rounding.
    seg1_start = starts[0]
    seg1_end = _local_hhmm_end(non_ziel[0])
    assert seg1_start == "09:10", f"F002: Segment 1 beginnt {seg1_start} statt 09:10"
    assert seg1_end == "09:11", (
        f"F002: Segment 1 endet {seg1_end} statt 09:11 — round(0.5) hat den "
        f"interpolierten Wegpunkt auf die Vorgängerzeit 09:10 kollabieren lassen "
        f"(Round-half-to-even statt kaufmännischer Rundung)"
    )
    assert seg1_end != seg1_start, (
        "F002: interpolierter Wegpunkt ist identisch zur Vorgängerzeit — "
        "Segment 1 hätte Dauer 0 und würde stumm verschwinden"
    )

    # (c) unvermeidbares Restkollabieren (Segment 2: G2→G3, beide 09:11)
    # muss geloggt sein, nicht still verworfen werden.
    assert any(
        r.levelno >= logging.WARNING and "kollabiert" in r.getMessage()
        for r in caplog.records
    ), (
        "F002: das unvermeidbar kollabierende Segment 2 (Minutenauflösung "
        "< Lückenzahl) wurde ohne Warnung still verworfen"
    )


# ---------------------------------------------------------------------------
# Issue #1091 — fallende arrival_override-Werte über Tagesgrenze bleiben
# chronologisch monoton (volle datetime statt nackter time).
# ---------------------------------------------------------------------------

def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def test_1091_falling_override_over_midnight_interpolates_monotonically():
    """Adversary #1091: arrival_override 22:00 -> None -> 00:30 darf nicht
    22:00 -> 11:15 -> 00:30 ergeben. Mit datetime-Rechnung liegt 00:30 am
    naechsten Tag; die Interpolation muss monoton steigend sein."""
    from services.trip_segments import _interpolate_missing_times

    known = [time(22, 0), None, time(0, 30)]
    result = _interpolate_missing_times(known)

    assert result[0] == time(22, 0)
    assert result[2] == time(0, 30)
    # 22:00 -> 00:30 (naechster Tag) = 150 Minuten; eine Luecke -> Mitte bei 23:15
    assert result[1] == time(23, 15), (
        f"Interpolierter Zwischenwert ist {result[1]} statt 23:15"
    )


def test_1091_multiple_gaps_over_midnight():
    """Adversary #1091: 22:00 -> None -> None -> 00:30 muss zwei monoton
    steigende Zwischenzeiten liefern."""
    from services.trip_segments import _interpolate_missing_times

    known = [time(22, 0), None, None, time(0, 30)]
    result = _interpolate_missing_times(known)

    # 22:00 -> 00:30 = 150 Minuten, 3 Schritte -> 50 Minuten/Schritt
    assert result[1] == time(22, 50), f"Erste Luecke unerwartet: {result[1]}"
    assert result[2] == time(23, 40), f"Zweite Luecke unerwartet: {result[2]}"


def test_1091_daytime_override_unchanged():
    """Regression: normale steigende Overrides ohne Tagesgrenze bleiben
    unveraendert (08:00 -> None -> 12:00 -> 10:00)."""
    from services.trip_segments import _interpolate_missing_times

    known = [time(8, 0), None, time(12, 0)]
    result = _interpolate_missing_times(known)

    assert result == [time(8, 0), time(10, 0), time(12, 0)], (
        f"Tag-Override-Interpolation unerwartet: {result}"
    )
