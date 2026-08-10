"""Issue #1667 S2 — Wirkungsbeleg am Segmentbau (AC-2).

Prueflings-Ort ist ``convert_trip_to_segments``, NICHT ``_format_hhmm``: die
23:59-Klemme wird erst dort schaedlich, wo der ``wp_days``-Rollover den
Tageswechsel an strikt fallenden Uhrzeiten erkennen soll und stattdessen ein
``23:59``-Plateau vorfindet -- die Folgesegmente laufen dann in den
Kollaps-Guard und verschwinden samt Wetterueberwachung.

Wegpunkt-Fixture (im Testfile eingecheckt, Korsika-Laengengrad, drei
gleichfoermige Anstiege): je 8,006 km Distanz und +600 Hm ergeben nach
Naismith je 8,006/4,0 + 600/300 = 4,0015 h. Drei Schenkel = 12,0045 h; ab
``start_time=22:00`` ist Mitternacht damit sicher ueberschritten
(22:00 + 4h = 02:00 des Folgetags). Der 08:00-Lauf derselben Fixture bleibt
vollstaendig im selben Kalendertag (08:00/12:00/16:00/20:00) und dient als
Vergleichsmassstab.
"""
from __future__ import annotations

from datetime import date, time

import pytest

from app.trip import Stage, Trip, Waypoint
from core.naismith import compute_stage_arrivals
from services.trip_segments import convert_trip_to_segments

# (lat, lon, elevation_m)
_WEGPUNKTE = [
    (42.300, 9.00, 500),
    (42.372, 9.00, 1100),
    (42.444, 9.00, 1700),
    (42.516, 9.00, 2300),
]
_ETAPPEN_DATUM = date(2026, 8, 12)


def _trip_mit_startzeit(start: time) -> Trip:
    """Trip mit bereits berechneten Ankunftszeiten.

    Spiegelt den Produktivpfad Compute-on-Save (``app/loader.py:1684``):
    ``arrival_calculated`` wird beim Speichern gerechnet und persistiert, der
    Segmentbau liest die Werte anschliessend nur noch.
    """
    waypoints = [
        Waypoint(id=f"G{i + 1}", name=f"P{i + 1}", lat=lat, lon=lon, elevation_m=elev)
        for i, (lat, lon, elev) in enumerate(_WEGPUNKTE)
    ]
    stage = Stage(
        id="T1",
        name="Nachtetappe",
        date=_ETAPPEN_DATUM,
        waypoints=waypoints,
        start_time=start,
    )
    stage = compute_stage_arrivals(stage, "")
    return Trip(id="wrap-1667", name="Wrap 1667", stages=[stage])


def _paar_segmente(trip: Trip) -> list:
    """Nur die Wegpunkt-Paar-Segmente -- das zusaetzlich angehaengte
    ``Ziel``-Segment gehoert zu keinem Wegpunkt-Paar."""
    return [
        s
        for s in convert_trip_to_segments(trip, _ETAPPEN_DATUM)
        if s.segment_id != "Ziel"
    ]


def test_start_22_uhr_liefert_alle_segmente_ohne_plateau():
    """AC-2 (a) alle Paar-Segmente entstehen, (b) kein Ankunfts-Plateau,
    (c) die Gehdauern sind dieselben wie beim 08:00-Lauf."""
    trip22 = _trip_mit_startzeit(time(22, 0))
    ankuenfte = [wp.arrival_calculated for wp in trip22.stages[0].waypoints]
    segmente = _paar_segmente(trip22)
    erwartet = len(_WEGPUNKTE) - 1

    befunde = []
    if len(segmente) != erwartet:
        befunde.append(
            f"(a) {len(segmente)} statt {erwartet} Paar-Segmenten -- der "
            f"Kollaps-Guard hat welche verworfen; Ankuenfte={ankuenfte}"
        )
    plateaus = [
        (i, ankuenfte[i]) for i in range(1, len(ankuenfte)) if ankuenfte[i] == ankuenfte[i - 1]
    ]
    if plateaus:
        befunde.append(
            f"(b) aufeinanderfolgende Ankuenfte identisch an {plateaus} -- "
            f"Ankuenfte={ankuenfte}"
        )
    dauern22 = [round(s.duration_hours, 6) for s in segmente]
    dauern08 = [round(s.duration_hours, 6) for s in _paar_segmente(_trip_mit_startzeit(time(8, 0)))]
    if dauern22 != pytest.approx(dauern08):
        befunde.append(
            f"(c) Gehdauern 22:00-Lauf {dauern22} != 08:00-Lauf {dauern08} -- die "
            "Naismith-Rechnung darf sich durch die Startzeit nicht aendern"
        )

    assert befunde == [], "AC-2 verletzt:\n" + "\n".join(befunde)
