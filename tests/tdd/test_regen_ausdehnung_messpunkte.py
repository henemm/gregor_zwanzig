"""TDD RED — Issue #2051 Scheibe S2a: Mehrpunkt-Abfrage entlang der
Reststrecke der aktiven Etappe.

SPEC: docs/specs/modules/feat_2051_s2a_raeumliche_ausdehnung.md — AC-1, AC-2,
AC-3.

RED-Ursache: `services.trip_segments.points_along_remaining_route` (und die
Modulkonstanten `RADAR_ZONE_POINT_SPACING_KM`/`RADAR_ZONE_MAX_POINTS`)
existieren noch nicht -> ImportError.

Mock-frei: echte `TripSegment`/`GPXPoint`-Objekte, echte `haversine_km()` zur
Verifikation (kein Mock). `trip=None` ist fuer diese Faelle zulaessig, weil
`points_along_remaining_route()` laut Spec `position_at_time()` als Baustein
nutzt — dessen Vorschau-/Interpolations-Zweige (`at <= active.end_time`)
lesen `trip` nicht, nur die Vorwaertssuche ueber Segment-/Tagesgrenzen tut
das, die hier nie erreicht wird (`at` liegt stets innerhalb des Segments).
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from app.models import GPXPoint, TripSegment
from utils.geo import haversine_km

# Muss zu `utils.geo._EARTH_KM` passen — dort steht der Referenzwert; hier
# nur zur Konstruktion, nicht als zweite Quelle der Wahrheit (die tatsaechlich
# gemessene Distanz wird unten per `haversine_km()` GEGENGEPRUEFT, s.
# `_aequator_segment`).
_EARTH_KM = 6371.0088
_UTC = timezone.utc


def _aequator_segment(distance_km: float, *, segment_id: int = 1) -> TripSegment:
    """Ein `TripSegment` entlang des Aequators (lat=0).

    Am Aequator faellt die Grosskreis-Distanz (`haversine_km`) mit der
    linearen Laengengrad-Interpolation zusammen (dlat=0, cos(0)=1 in der
    Formel) — der Test wird dadurch unabhaengig davon, ob die Punktbildung
    linear in Grad oder ueber wiederholte `haversine_km`-Schritte
    interpoliert.
    """
    delta_lon = math.degrees(distance_km / _EARTH_KM)
    start = GPXPoint(lat=0.0, lon=0.0, elevation_m=1000.0, distance_from_start_km=0.0)
    end = GPXPoint(
        lat=0.0, lon=delta_lon, elevation_m=1000.0,
        distance_from_start_km=distance_km,
    )
    gemessen = haversine_km(start.lat, start.lon, end.lat, end.lon)
    assert abs(gemessen - distance_km) < 1e-6, (
        f"Testvoraussetzung: die konstruierte Strecke muss {distance_km} km "
        f"messen, misst tatsaechlich {gemessen} km"
    )
    start_time = datetime(2026, 8, 23, 8, 0, tzinfo=_UTC)
    end_time = start_time + timedelta(hours=4)
    return TripSegment(
        segment_id=segment_id, start_point=start, end_point=end,
        start_time=start_time, end_time=end_time, duration_hours=4.0,
        distance_km=distance_km, ascent_m=0.0, descent_m=0.0,
    )


def test_ac1_zwoelf_km_reststrecke_ergibt_sechs_gedeckelte_punkte():
    """AC-1: Reststrecke 12,0 km -> genau 6 Punkte bei km 0/2/4/6/8/10 — der
    Deckel `RADAR_ZONE_MAX_POINTS=6` greift, die letzten 2 km bleiben
    unabgefragt."""
    from services.trip_segments import (
        RADAR_ZONE_MAX_POINTS,
        RADAR_ZONE_POINT_SPACING_KM,
        points_along_remaining_route,
    )

    assert RADAR_ZONE_POINT_SPACING_KM == 2.0, (
        f"Testvoraussetzung: Abstand muss 2.0 km sein, war "
        f"{RADAR_ZONE_POINT_SPACING_KM}"
    )
    assert RADAR_ZONE_MAX_POINTS == 6, (
        f"Testvoraussetzung: Deckel muss 6 sein, war {RADAR_ZONE_MAX_POINTS}"
    )

    seg = _aequator_segment(12.0)
    at = seg.start_time  # Vorschau-Zweig von position_at_time: p=0, Reststrecke = volle Laenge.

    pts = points_along_remaining_route(None, seg, date(2026, 8, 23), at)

    assert len(pts) == RADAR_ZONE_MAX_POINTS, (
        f"AC-1: erwartet genau {RADAR_ZONE_MAX_POINTS} Punkte (Deckel), "
        f"erhalten {len(pts)}"
    )
    erwartete_km = [i * RADAR_ZONE_POINT_SPACING_KM for i in range(RADAR_ZONE_MAX_POINTS)]
    gemessene_km = [
        haversine_km(seg.start_point.lat, seg.start_point.lon, p.lat, p.lon)
        for p in pts
    ]
    for i, (soll, ist) in enumerate(zip(erwartete_km, gemessene_km)):
        assert abs(soll - ist) < 0.05, (
            f"AC-1: Punkt {i} liegt bei km {ist:.3f}, erwartet km {soll:.1f} "
            f"(alle Punkte: {gemessene_km})"
        )
    # Negativkontrolle gegen die Formeigenschaft "Form statt Wert": eine
    # Implementierung, die z.B. km 0/2/4/6/8/9 (falsch geraster) liefert,
    # faellt hier durch, nicht nur eine, die die Punktzahl verfehlt.
    assert abs(gemessene_km[-1] - 10.0) < 0.05, (
        f"AC-1: der letzte der 6 Punkte muss bei km 10 liegen (nicht bei km "
        f"12, dem Etappenende), erhalten km {gemessene_km[-1]:.3f}"
    )


def test_ac2_unter_zwei_km_reststrecke_ergibt_genau_einen_punkt():
    """AC-2 (Positivkontrolle zu AC-1): Reststrecke 1,9 km (unter der 2-km-
    Schwelle) -> genau EIN Punkt an der heutigen Fenstermitte-Position
    (unveraendertes Verhalten gegenueber dem Stand vor dieser Spec)."""
    from services.trip_segments import points_along_remaining_route

    seg = _aequator_segment(1.9)
    at = seg.start_time

    pts = points_along_remaining_route(None, seg, date(2026, 8, 23), at)

    assert len(pts) == 1, (
        f"AC-2: erwartet genau 1 Punkt unterhalb der 2-km-Schwelle, erhalten "
        f"{len(pts)}: {pts!r}"
    )
    # Der eine Punkt IST die heutige Fenstermitte-Position — hier per
    # Konstruktion `start_point` (Vorschau-Zweig).
    assert abs(pts[0].lat - seg.start_point.lat) < 1e-9, (
        f"AC-2: der einzige Punkt muss die Fenstermitte-Position sein "
        f"(lat={seg.start_point.lat}), erhalten lat={pts[0].lat}"
    )
    assert abs(pts[0].lon - seg.start_point.lon) < 1e-9, (
        f"AC-2: der einzige Punkt muss die Fenstermitte-Position sein "
        f"(lon={seg.start_point.lon}), erhalten lon={pts[0].lon}"
    )


def test_ac3_acht_km_reststrecke_liegt_auf_der_geometrie_ohne_duplikate():
    """AC-3: Reststrecke 8,0 km -> alle 5 Punkte (km 0/2/4/6/8) liegen auf
    der interpolierten Streckengeometrie der aktiven Etappe, keine zwei
    Koordinaten sind identisch."""
    from services.trip_segments import (
        RADAR_ZONE_POINT_SPACING_KM,
        points_along_remaining_route,
    )

    seg = _aequator_segment(8.0)
    at = seg.start_time

    pts = points_along_remaining_route(None, seg, date(2026, 8, 23), at)

    assert len(pts) == 5, f"AC-3: erwartet 5 Punkte, erhalten {len(pts)}"

    # "Auf der Geometrie" der Aequator-Etappe: lat bleibt 0.0 fuer jeden
    # Punkt (die Etappe verlaeuft rein in Laengengrad-Richtung).
    for i, p in enumerate(pts):
        assert abs(p.lat - 0.0) < 1e-6, (
            f"AC-3: Punkt {i} liegt nicht auf der Streckengeometrie "
            f"(lat={p.lat}, erwartet 0.0)"
        )

    # Keine zwei Koordinaten identisch.
    lons = [round(p.lon, 8) for p in pts]
    assert len(set(lons)) == len(lons), (
        f"AC-3: mindestens zwei Punkte sind identisch: {lons}"
    )

    # Jeder Punkt an der erwarteten Distanz-vom-Start.
    gemessene_km = [
        haversine_km(seg.start_point.lat, seg.start_point.lon, p.lat, p.lon)
        for p in pts
    ]
    erwartete_km = [i * RADAR_ZONE_POINT_SPACING_KM for i in range(5)]
    for i, (soll, ist) in enumerate(zip(erwartete_km, gemessene_km)):
        assert abs(soll - ist) < 0.05, (
            f"AC-3: Punkt {i} liegt bei km {ist:.3f}, erwartet km {soll:.1f}"
        )
