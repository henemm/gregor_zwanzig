"""TDD RED — Issue #2985: Debug-Route waehlt die Etappe ueber den EINEN
Baustein ``resolve_current_segment`` statt ueber eine eigene Kopie.

SPEC: docs/specs/fast/fix-2985-debug-segmentwahl.md (AC-1 … AC-4)
(Die Spec nennt den Arbeitstitel ``test_issue_2985_debug_segmentwahl.py``;
das Testnamen-Gate verlangt Benennung nach Verhalten, daher dieser Name.)

RED-Grund heute: ``api/routers/debug.py`` hat keine Hilfsfunktion
``_pick_debug_segment``; die Route bestimmt das Segment inline mit einer
eigenen "aktiv oder erstes"-Schleife ohne Vortags-Rueckgriff.

Testpolitik: echte ``Trip``-Objekte aus dem geteilten Helfer
(``tests/helpers/nowcast_gate_fixtures.py``), kein Mock/patch. Die Erwartung
fuer AC-1 wird ZUSAETZLICH unabhaengig vom Pruefling aufgebaut (laufendes
Segment der gestrigen Etappe ueber ``convert_trip_to_segments`` +
Zeitfenster), damit der Test nicht nur die Vorrangkette gegen sich selbst
prueft.

Mutations-Gegenprobe (AC-4): Ersetzt man in ``_pick_debug_segment`` den
Aufruf von ``resolve_current_segment`` durch ``None`` (nur noch eigene
Heute-Schleife bzw. Test-Seam-Rueckfall), liefert die Funktion fuer AC-1 das
ERSTE Segment der Etappe (Gehsegment ab 22:00) statt des noch laufenden
Ziel-Segments — ``test_ac1_…`` wird rot.

Ausfuehrung:
    uv run pytest tests/tdd/test_debug_radar_segmentwahl.py -v
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timezone

from services.trip_segments import convert_trip_to_segments, resolve_current_segment

from tests.helpers.nowcast_gate_fixtures import make_trip

# Atlantic/Reykjavik (UTC+0): Ortstag == UTC-Tag, kein Zonenrauschen.
REYKJAVIK_LAT, REYKJAVIK_LON = 64.1466, -21.9426


def _pick():
    from api.routers.debug import _pick_debug_segment

    return _pick_debug_segment


def _key(seg):
    """Identitaet eines Segments ueber fachliche Felder."""
    return (
        str(seg.segment_id),
        seg.start_time,
        seg.end_time,
        round(seg.start_point.lat, 6),
        round(seg.start_point.lon, 6),
        round(seg.end_point.lat, 6),
        round(seg.end_point.lon, 6),
    )


def _nacht_trip(tag: date_type):
    """Etappe 22:00 -> 02:00 Ortszeit: das Ziel-Segment laeuft am Folgetag
    ab 02:00 bis Tagesfenster-Ende (siehe #1667 S3)."""
    return make_trip(
        "trip-2985-nacht", stage_date=tag, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="22:00", arrival_end="02:00",
    )


def test_ac1_vortags_zielsegment_nach_mitternacht_wie_resolve_current_segment():
    """AC-1: Gestrige Etappe kommt nach Mitternacht an, ihr Ziel-Segment laeuft
    jetzt (11.8. 03:00 UTC) noch, heute keine Etappe. Die Debug-Segmentwahl
    muss genau das Segment liefern, das ``resolve_current_segment`` liefert —
    nicht das erste Segment des Trips."""
    tag = date_type(2026, 8, 10)
    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 3, 0, tzinfo=timezone.utc)
    trip = _nacht_trip(tag)

    erwartet = resolve_current_segment(trip, now_utc, heute)
    assert erwartet is not None, "Vorbedingung: Vorrangkette liefert das Vortags-Ziel"
    erwartet_seg, erwartet_datum = erwartet
    assert erwartet_datum == tag, "Vorbedingung: Segment stammt von gestern"

    gestern_segs = convert_trip_to_segments(trip, tag)
    laufend = [s for s in gestern_segs if s.start_time <= now_utc <= s.end_time]
    assert len(laufend) == 1, f"Vorbedingung: genau ein laufendes Segment, war {laufend!r}"
    erstes = gestern_segs[0]
    assert _key(erstes) != _key(laufend[0]), (
        "Vorbedingung: erstes Segment und laufendes Ziel-Segment muessen sich "
        "unterscheiden, sonst diskriminiert der Test nicht"
    )

    gewaehlt = _pick()(trip, now_utc, heute)

    assert gewaehlt is not None, "AC-1: Debug-Segmentwahl lieferte None"
    assert _key(gewaehlt) == _key(erwartet_seg), (
        f"AC-1: erwartet das Segment aus resolve_current_segment "
        f"{_key(erwartet_seg)!r}, war {_key(gewaehlt)!r}"
    )
    assert _key(gewaehlt) == _key(laufend[0])
    assert _key(gewaehlt) != _key(erstes), (
        "AC-1: die Debug-Segmentwahl fiel auf das erste Segment des Trips zurueck "
        "statt das noch laufende Vortags-Ziel zu nehmen"
    )


def test_ac2_heute_aktives_segment_bleibt_unveraendert():
    """AC-2: Ist heute ein Segment aktiv, liefert die Debug-Segmentwahl genau
    dieses Segment (Verhalten wie vor dem Umbau)."""
    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    trip = make_trip(
        "trip-2985-heute", stage_date=heute, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="08:00", arrival_end="16:00",
    )

    segs = convert_trip_to_segments(trip, heute)
    aktiv = [s for s in segs if s.start_time <= now_utc <= s.end_time]
    assert aktiv, f"Vorbedingung: heute ist ein Segment aktiv, Segmente {segs!r}"

    gewaehlt = _pick()(trip, now_utc, heute)

    assert gewaehlt is not None, "AC-2: Debug-Segmentwahl lieferte None"
    assert _key(gewaehlt) == _key(aktiv[0]), (
        f"AC-2: erwartet das heute aktive Segment {_key(aktiv[0])!r}, "
        f"war {_key(gewaehlt)!r}"
    )


def test_ac3_vergangene_etappen_test_seam_rueckfall_auf_erstes_segment():
    """AC-3: Alle Etappen liegen in der Vergangenheit (Staging-Testdaten) —
    ``resolve_current_segment`` liefert None, die Debug-Segmentwahl faellt auf
    das erste Segment der ersten Etappe zurueck statt None zu liefern."""
    alt = date_type(2026, 8, 1)
    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    trip = make_trip(
        "trip-2985-alt", stage_date=alt, lat=REYKJAVIK_LAT, lon=REYKJAVIK_LON,
        arrival_start="08:00", arrival_end="16:00",
    )
    assert resolve_current_segment(trip, now_utc, heute) is None, (
        "Vorbedingung: keine aktive Etappe, keine Vorschau"
    )
    erwartet = convert_trip_to_segments(trip, alt)[0]

    gewaehlt = _pick()(trip, now_utc, heute)

    assert gewaehlt is not None, "AC-3: Test-Seam-Rueckfall fehlt, lieferte None"
    assert _key(gewaehlt) == _key(erwartet), (
        f"AC-3: erwartet das erste Segment der ersten Etappe {_key(erwartet)!r}, "
        f"war {_key(gewaehlt)!r}"
    )


def test_trip_ohne_etappen_liefert_kein_segment():
    """Rand zu AC-3: ohne Etappen gibt es kein Segment -> None (die Route
    antwortet weiterhin ``no_segment``)."""
    from app.trip import Trip

    heute = date_type(2026, 8, 11)
    now_utc = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    trip = Trip(id="trip-2985-leer", name="leer", stages=[])

    assert _pick()(trip, now_utc, heute) is None
