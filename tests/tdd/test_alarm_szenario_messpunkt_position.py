"""Issue #2261 Teil A, Szenario 8 — Waechter: der Radar-Alarm misst dort, wo der
Nutzer sein wird (Herkunft #2050 B-3 / #2017).

SPEC: docs/specs/modules/feat_2261_sz8_messpunkt_position.md (AC-1..AC-4;
AC-5 ist Doku-Abnahme, AC-6 der Mutations-Durchlauf des Adversary).

Die Zusicherung wirkt an den ARGUMENTEN von `get_nowcast` im echten
`TripAlertService.check_radar_alerts()` — nicht in `position_at_time` selbst.
Deshalb faehrt dieser Waechter zwei echte Laeufe (Standard-Etappe / Endwegpunkt
gespiegelt und hoeher) und vergleicht die aufgezeichneten Abrufe. Die Erwartung
ist KEIN Spiegel von `position_at_time`: geprueft werden Ungleichheit, Richtung
und Abstand, keine aus dem Prueflings-Code gerechneten Sollwerte.

Mock-frei: echte Trips auf der isolierten Datenwurzel, echter `frame_source`-
Seam, echte `RadarNowcastService`-Unterklasse, die nur mitschreibt.
"""
from __future__ import annotations

import dataclasses
import math

from freezegun import freeze_time

from tests.helpers.nowcast_gate_fixtures import (
    TRIP_LON,
    CountingFrameSource,
    aufzeichnender_radar_dienst,
    clean_uid,
    fresh_uid,
    make_trip,
    reset_radar_cache,
    save_trip,
    settings_email_only,
    write_user_tier,
)

# Mittags, Reykjavik (UTC+0 ganzjaehrig): die HH:MM-Angaben der Etappe sind
# direkt aus der gestellten UTC-Zeit ablesbar (Muster `_alarm_lauf_2017`).
_MITTAGS = "2026-08-11T12:00:00+00:00"

# Endwegpunkt von Lauf B: Laenge gespiegelt (Standard: TRIP_LON + 0,1), Hoehe 900 m.
_B_END_LON = TRIP_LON - 0.1
_A_END_HOEHE, _B_END_HOEHE = 600.0, 900.0


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Luftlinie in km (Haversine) — unabhaengig vom Prueflings-Code."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _lauf(zweck: str, *, verschoben: bool, end_lat: float | None = None):
    """Ein echter `check_radar_alerts()`-Lauf unter gestellter Uhr.

    Liefert `(abrufe, start, ende)`; `start`/`ende` sind die Wegpunkte der
    von der Platte GELESENEN Etappe (dieselbe Fassung wie beim Prueflings-Lauf).
    """
    from app.loader import load_all_trips
    from services.trip_alert import TripAlertService

    uid = fresh_uid(f"sz8-{zweck}")
    trip_id = f"trip-sz8-{zweck}"
    clean_uid(uid)
    try:
        with freeze_time(_MITTAGS):
            write_user_tier(uid, "premium")
            trip = make_trip(trip_id, arrival_start="11:00", arrival_end="15:00")
            if verschoben:
                wps0 = trip.stages[0].waypoints
                wps0[1] = dataclasses.replace(
                    wps0[1], lon=_B_END_LON, elevation_m=_B_END_HOEHE,
                )
            if end_lat is not None:
                wps0 = trip.stages[0].waypoints
                wps0[1] = dataclasses.replace(wps0[1], lat=end_lat)
            save_trip(trip, uid)
            geladen = next(t for t in load_all_trips(user_id=uid) if t.id == trip_id)
            wps = geladen.stages[0].waypoints

            reset_radar_cache()
            dienst = aufzeichnender_radar_dienst(CountingFrameSource(onset_minutes=8))
            svc = TripAlertService(
                settings=settings_email_only(), throttle_hours=2, user_id=uid,
                radar_service=dienst, mail_sink=lambda subject, body: None,
            )
            svc.check_radar_alerts()
            return dienst.calls, wps[0], wps[1]
    finally:
        clean_uid(uid)


def _laeufe():
    a, a_start, a_ende = _lauf("a", verschoben=False)
    b, b_start, b_ende = _lauf("b", verschoben=True)
    # Testvoraussetzungen: ohne Abrufe / ohne lange Etappe ist nichts zu pruefen.
    assert a and b, f"Testvoraussetzung: get_nowcast nicht aufgerufen (A={len(a)}, B={len(b)})"
    assert _km(a_start.lat, a_start.lon, a_ende.lat, a_ende.lon) > 12.0, (
        "Testvoraussetzung: Etappe A muss laenger als 12 km sein"
    )
    assert _km(b_start.lat, b_start.lon, b_ende.lat, b_ende.lon) > 12.0, (
        "Testvoraussetzung: Etappe B muss laenger als 12 km sein"
    )
    assert (a_ende.lon - a_start.lon) > 0 > (b_ende.lon - b_start.lon), (
        "Testvoraussetzung: A laeuft nach Osten, B nach Westen"
    )
    return a, a_start, b, b_start


def test_sz8_messpunkt_wandert_mit_dem_wegpunkt():
    """AC-1: derselbe Lauf mit verschobenem Endwegpunkt fragt ANDERE Koordinaten
    ab — jeder Punkt, nicht nur der erste; Richtung folgt dem Endwegpunkt."""
    a, a_start, b, b_start = _laeufe()

    assert a[0]["lon"] > a_start.lon, (
        f"AC-1: erster Messpunkt in A ({a[0]['lon']:.5f}) muss oestlich des "
        f"Startpunkts ({a_start.lon:.5f}) liegen"
    )
    assert b[0]["lon"] < b_start.lon, (
        f"AC-1: erster Messpunkt in B ({b[0]['lon']:.5f}) muss westlich des "
        f"Startpunkts ({b_start.lon:.5f}) liegen"
    )
    for i, (pa, pb) in enumerate(zip(a, b)):
        assert _km(pa["lat"], pa["lon"], pb["lat"], pb["lon"]) > 1.0, (
            f"AC-1: Punkt {i} unterscheidet sich zwischen A "
            f"({pa['lat']:.5f}, {pa['lon']:.5f}) und B ({pb['lat']:.5f}, "
            f"{pb['lon']:.5f}) nicht — die Verschiebung des Wegpunkts kommt "
            f"an der Abfrage nicht an"
        )


def test_sz8_messpunkt_ist_nicht_der_startpunkt():
    """AC-2: der erste Messpunkt liegt in beiden Laeufen > 1 km vom Startpunkt."""
    a, a_start, b, b_start = _laeufe()

    for name, abrufe, start in (("A", a, a_start), ("B", b, b_start)):
        d = _km(abrufe[0]["lat"], abrufe[0]["lon"], start.lat, start.lon)
        assert d > 1.0, (
            f"AC-2: Lauf {name}: erster Messpunkt nur {d:.3f} km vom "
            f"Segment-Startpunkt — der Nutzer hat ihn zur Fenstermitte laengst "
            f"verlassen (#2017)"
        )


def test_sz8_folgepunkte_wandern_mit_dem_wegpunkt():
    """AC-3: mehr als ein, hoechstens RADAR_ZONE_MAX_POINTS Abrufe; jeder
    Folgepunkt liegt in A oestlich, in B westlich des ersten Punkts."""
    from services.trip_segments import RADAR_ZONE_MAX_POINTS

    a, _a_start, b, _b_start = _laeufe()

    for name, abrufe in (("A", a), ("B", b)):
        assert 1 < len(abrufe) <= RADAR_ZONE_MAX_POINTS, (
            f"AC-3: Lauf {name}: {len(abrufe)} Abrufe; erwartet mehr als 1 "
            f"und hoechstens {RADAR_ZONE_MAX_POINTS}"
        )
    for i, p in enumerate(a[1:], start=1):
        assert p["lon"] > a[0]["lon"], (
            f"AC-3: Folgepunkt {i} in A ({p['lon']:.5f}) liegt nicht oestlich "
            f"des ersten Punkts ({a[0]['lon']:.5f})"
        )
    for i, p in enumerate(b[1:], start=1):
        assert p["lon"] < b[0]["lon"], (
            f"AC-3: Folgepunkt {i} in B ({p['lon']:.5f}) liegt nicht westlich "
            f"des ersten Punkts ({b[0]['lon']:.5f})"
        )


def test_sz8_hoehe_wandert_mit_dem_messpunkt():
    """AC-4: die an `get_nowcast` uebergebene Hoehe wandert mit — zwischen
    Start- und Endhoehe der Etappe, in B groesser als in A, nicht die
    Startpunkt-Hoehe, ganze Meter."""
    a, a_start, b, b_start = _laeufe()
    ha, hb = a[0]["elevation_m"], b[0]["elevation_m"]

    assert ha is not None and hb is not None, (
        f"AC-4: die Abfrage muss eine Hoehe tragen (A={ha}, B={hb})"
    )
    assert isinstance(ha, int) and isinstance(hb, int), (
        f"AC-4: Hoehe in ganzen Metern erwartet (A={ha!r}, B={hb!r})"
    )
    assert a_start.elevation_m < ha < _A_END_HOEHE, (
        f"AC-4: Hoehe in A ({ha}) nicht zwischen Start ({a_start.elevation_m}) "
        f"und Ende ({_A_END_HOEHE})"
    )
    assert b_start.elevation_m < hb < _B_END_HOEHE, (
        f"AC-4: Hoehe in B ({hb}) nicht zwischen Start ({b_start.elevation_m}) "
        f"und Ende ({_B_END_HOEHE})"
    )
    assert hb > ha, f"AC-4: Hoehe in B ({hb}) muss ueber der in A ({ha}) liegen"


def test_sz8_obergrenze_der_messpunkte():
    """AC-3 (Obergrenze): Etappe ~45 km, Reststrecke ab Fenstermitte weit ueber
    der Obergrenze bei 2-km-Abstand — es erfolgen genau RADAR_ZONE_MAX_POINTS
    Abrufe (die Fixture-Etappe liefert nur ~4 und beweist die Grenze nicht)."""
    from services.trip_segments import RADAR_ZONE_MAX_POINTS

    abrufe, start, ende = _lauf("lang", verschoben=False, end_lat=64.53)
    assert _km(start.lat, start.lon, ende.lat, ende.lon) > 40.0, (
        "Testvoraussetzung: lange Etappe muss ueber 40 km sein"
    )
    assert len(abrufe) == RADAR_ZONE_MAX_POINTS, (
        f"AC-3: {len(abrufe)} Abrufe; erwartet genau {RADAR_ZONE_MAX_POINTS}"
    )
