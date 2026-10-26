"""Geteilte Bausteine der GPS-Fix-Tests (Issue #2327, ADR-0102).

SPEC: docs/specs/modules/feat_2327_gps_etappenfortschritt.md

Genutzt von ``tests/unit/test_position_fix_snapping.py`` und
``tests/tdd/test_position_fix_inbound_e2e.py`` -- EINE Geometrie, keine
zweite Kopie, die abdriften koennte.

Geometrie (bewusst einfach, damit Sollwerte OHNE den Pruefling rechenbar
sind):

* Die Heute-Etappe laeuft exakt auf dem Meridian ``ROUTE_LON`` von
  ``START_LAT`` nach ``ZIEL_LAT`` (~11,1 km Richtung Norden). Die Route geht
  durch die erste echte PO-Koordinate (46.6370, 12.7678); die zweite echte
  Koordinate (46.6124, 12.8676) liegt rund 7,6 km oestlich daneben.
* Ein Punkt mit Laengenversatz ``d`` auf Breite ``phi`` liegt ``d`` Meter
  neben der Strecke; sein Lot auf die Strecke ist ``(phi, ROUTE_LON)``.
* Der GPX-Track hat eine LANGE Luecke (``GAP_SUED_LAT`` -> ``GAP_NORD_LAT``,
  ~5,1 km ohne Trackpunkt). Ein Punkt mitten in dieser Luecke liegt
  kilometerweit vom naechsten TRACKPUNKT entfernt, aber 0 m von der STRECKE
  (Spec-Entscheidung 5: Abstand zur Strecke, nicht zum Trackpunkt).
* Beide Wegpunkte der Etappe sind exakt Trackpunkte (``_match_track``
  verlangt <= 10 m je Wegpunkt) -- sonst schluege die Track-Zuordnung aus dem
  falschen Grund fehl.

Fortschreibung (Spec AC-4, Changelog 26.10.): ein Fix friert die Position
NICHT ein -- ``fortgeschrieben()`` rechnet die Soll-Position zur Abfragezeit
geschlossen aus Fix + Plan-Tempo.

Zeit: Montag 2026-10-26 (Tag der echten PO-Nachrichten, MEZ = UTC+1, die
Sommerzeit endete am 25.10.). Wegpunktzeiten werden ROH geschrieben
(``arrival_calculated``), nicht ueber ``app.loader.save_trip`` -- dessen
Compute-on-Save (#802) wuerde sie per Naismith ueberschreiben.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.loader import get_briefings_dir, get_data_dir, load_all_trips
from utils.geo import haversine_km
from utils.timezone import tz_for_coords

# ---------------------------------------------------------------------------
# Echte Nachrichtentexte des PO vom 26.10.2026 (woertlich, Spec-Vorgabe)
# ---------------------------------------------------------------------------

ECHT_HEUTE = "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  (46.6370, 12.7678)"
ECHT_SO_MORGEN = "so morgen  inreachlink.com/gGF87yQgGC0h_fnW_2_ngUA  (46.6124, 12.8676)"
ECHT_HEUTE_KOORD = (46.6370, 12.7678)
ECHT_SO_MORGEN_KOORD = (46.6124, 12.8676)

# ---------------------------------------------------------------------------
# Geometrie
# ---------------------------------------------------------------------------

ROUTE_LON = 12.7678
START_LAT = 46.6000
ZIEL_LAT = 46.7000
FOLGETAG_ZIEL_LAT = 46.8000  # Etappe am Folgetag: Ziel -> weiter nach Norden
GAP_SUED_LAT = 46.6040
GAP_NORD_LAT = 46.6500
GAP_MITTE_LAT = round((GAP_SUED_LAT + GAP_NORD_LAT) / 2, 4)  # 46.627

#: Trackpunkte der Heute-Etappe: 5 dichte Punkte, lange Luecke, 6 Punkte.
TRACK_LATS = (
    46.6000, 46.6010, 46.6020, 46.6030, GAP_SUED_LAT,
    GAP_NORD_LAT, 46.6600, 46.6700, 46.6800, 46.6900, ZIEL_LAT,
)

#: Zweiter Trip, EINDEUTIG getrennt: Parallel-Meridian ~10 km oestlich.
ANDERER_ROUTE_LON = 12.9000

#: Zweiter Trip, KREUZEND (X-Form): Ost-West-Strecke auf der Breite der
#: ersten echten Koordinate, Wegpunkte weit weg von der Kreuzung (je ~5 km),
#: damit die Track-Zuordnung beider Trips eindeutig bleibt und NUR der Fix an
#: der Kreuzung mehrdeutig ist.
KREUZ_LAT = ECHT_HEUTE_KOORD[0]
KREUZ_WEST_LON = 12.7000
KREUZ_OST_LON = 12.8400

TAG = date(2026, 10, 26)
ZONE = ZoneInfo(str(tz_for_coords(ECHT_HEUTE_KOORD[0], ROUTE_LON)))
START_ZEIT = "08:00"
ZIEL_ZEIT = "16:00"


def ortszeit(stunde: int, minute: int = 0, *, tag: date = TAG) -> datetime:
    """Ortszeit der Etappe als zonenbewusster UTC-Zeitstempel."""
    return datetime.combine(tag, time(stunde, minute), tzinfo=ZONE).astimezone(timezone.utc)


def fortgeschrieben(fix_lat: float, observed_at: datetime, at: datetime) -> tuple[float, float]:
    """Soll-Position zur Abfragezeit ``at`` nach Spec AC-4 (Stand 26.10.):
    gesnappter Fix plus Planfortschritt zwischen ``observed_at`` und ``at``
    (Plan-Tempo der Heute-Etappe), begrenzt auf das Etappenende; bei
    ``at <= observed_at`` der Fix selbst.

    Geschlossen gerechnet, NICHT ueber den Pruefling: die Etappe laeuft auf
    dem Meridian von ``START_LAT`` (``START_ZEIT``) nach ``ZIEL_LAT``
    (``ZIEL_ZEIT``) -- Plan-Tempo 0,1 Grad Breite in 8 h (~23,2 m/min). Auf
    dem Meridian ist Streckenanteil linear in der Breite, deshalb ist die
    Rechnung im Modell "Streckenanteil == Zeitanteil" exakt. Vergleich NUR
    mit :func:`toleranz_fortschreibung` (Begruendung dort)."""
    plan_s = (ortszeit(*map(int, ZIEL_ZEIT.split(":")))
              - ortszeit(*map(int, START_ZEIT.split(":")))).total_seconds()
    vergangen_s = max(0.0, (at - observed_at).total_seconds())
    lat = fix_lat + (ZIEL_LAT - START_LAT) * vergangen_s / plan_s
    return (min(ZIEL_LAT, lat), ROUTE_LON)


def toleranz_fortschreibung(erwartet, fix) -> float:
    """Toleranz (m) fuer den Vergleich mit :func:`fortgeschrieben`:
    5 m Snapping/Rundung + 0,5 % der Fortschreibungsstrecke.

    Begruendung (gemessen 26.10.): das Produkt fuehrt zwei Distanz-Skalen --
    die Segmente rechnen die Etappe mit 11,1 km (``distance_from_start_km``
    1,3875 bei 46.6125, also 111,0 km/Grad), GPX/``position_fix._snap``
    mit der echten Meridianlaenge (~111,195 km/Grad). Eine zulaessige
    Implementierung, die Plan-Tempo aus ``seg.distance_km`` nimmt und auf dem
    GPX-Track weiterlaeuft, liegt ~0,18 % der Strecke daneben (~7 m auf
    4,2 km). Die kleinste Fortschreibung im Testbestand (15 min, ~350 m)
    ergibt ~6,7 m Toleranz -- ein eingefrorener Fix verfehlt sie um ~50x."""
    return 5.0 + 0.005 * abstand_m(erwartet, fix)


def planposition(at: datetime) -> tuple[float, float]:
    """Planposition auf der Heute-Etappe zur Zeit ``at`` (geschlossen, fuer
    Testaufbau-Abstaende -- der Pruefling liefert sie per ``user_id=None``)."""
    return fortgeschrieben(START_LAT, ortszeit(*map(int, START_ZEIT.split(":"))), at)


def lon_versatz(lat: float, meter: float) -> float:
    """Laengenversatz (Grad), der auf Breite ``lat`` exakt ``meter`` Meter
    Grosskreisabstand ergibt -- geschlossen geloest, nicht ueber den
    Pruefling."""
    r_m = 6371.0088 * 1000.0
    return math.degrees(2 * math.asin(math.sin(meter / (2 * r_m)) / math.cos(math.radians(lat))))


def punkt_neben_route(lat: float, meter: float) -> tuple[float, float]:
    """Punkt ``meter`` Meter OESTLICH der Strecke auf Breite ``lat``; sein
    Lot auf die Strecke ist ``(lat, ROUTE_LON)``."""
    p = (lat, ROUTE_LON + lon_versatz(lat, meter))
    ist_m = haversine_km(lat, ROUTE_LON, p[0], p[1]) * 1000.0
    assert abs(ist_m - meter) < 0.05, (
        f"Testaufbau: Versatz {ist_m:.3f} m statt {meter} m"
    )
    return p


def abstand_m(a, b) -> float:
    """Abstand zweier Punkte (GPXPoint ODER (lat, lon)) in Metern."""
    la, lo = (a.lat, a.lon) if hasattr(a, "lat") else a
    lb, lob = (b.lat, b.lon) if hasattr(b, "lat") else b
    return haversine_km(la, lo, lb, lob) * 1000.0


# ---------------------------------------------------------------------------
# Persistenz: GPX + Trip (roh), Nutzerprofil
# ---------------------------------------------------------------------------

def gpx_schreiben(user_id: str, name: str, punkte) -> Path:
    """GPX in den Nutzer-Bestand ``data/users/<uid>/gpx/`` (>= 10 Punkte,
    jeder mit ``<ele>`` -- Mindestanforderungen von ``parse_gpx``)."""
    punkte = list(punkte)
    assert len(punkte) >= 10, "Testaufbau: parse_gpx verlangt >= 10 Trackpunkte"
    ordner = get_data_dir(user_id) / "gpx"
    ordner.mkdir(parents=True, exist_ok=True)
    trkpts = "".join(
        f'<trkpt lat="{lat:.9f}" lon="{lon:.9f}"><ele>{1000.0 + i:.1f}</ele></trkpt>'
        for i, (lat, lon) in enumerate(punkte)
    )
    pfad = ordner / f"{name}.gpx"
    pfad.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="tdd-2327" '
        'xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><name>{name}</name><trkseg>{trkpts}</trkseg></trk></gpx>",
        encoding="utf-8",
    )
    return pfad


def heute_track_punkte():
    return [(lat, ROUTE_LON) for lat in TRACK_LATS]


def anderer_track_punkte():
    return [(lat, ANDERER_ROUTE_LON) for lat in TRACK_LATS]


def kreuz_track_punkte():
    schritt = (KREUZ_OST_LON - KREUZ_WEST_LON) / 10
    return [(KREUZ_LAT, round(KREUZ_WEST_LON + i * schritt, 6)) for i in range(11)]


def _wegpunkt(wid: str, lat: float, lon: float, zeit: str) -> dict:
    return {
        "id": wid, "name": wid, "lat": lat, "lon": lon,
        "elevation_m": 1000.0, "arrival_calculated": zeit,
    }


def _etappe(sid: str, tag: date, a: tuple, b: tuple, *, start: str, ziel: str) -> dict:
    return {
        "id": sid, "name": f"Etappe {sid}", "date": tag.isoformat(),
        "waypoints": [
            _wegpunkt(f"{sid}a", a[0], a[1], start),
            _wegpunkt(f"{sid}b", b[0], b[1], ziel),
        ],
    }


def trip_schreiben(
    user_id: str, trip_id: str, *, route: str = "heute", tag: date = TAG,
    start: str = START_ZEIT, ziel: str = ZIEL_ZEIT, mit_folgetag: bool = False,
    name: str = "GPS-Fix-Trip",
) -> None:
    """Trip ROH unter ``briefings/<id>.json`` (Wegpunktzeiten bleiben exakt).

    ``route``: ``"heute"`` (Meridian ROUTE_LON), ``"anders"`` (Parallel-
    Meridian), ``"kreuz"`` (Ost-West durch die erste echte Koordinate)."""
    if route == "heute":
        a, b = (START_LAT, ROUTE_LON), (ZIEL_LAT, ROUTE_LON)
    elif route == "anders":
        a, b = (START_LAT, ANDERER_ROUTE_LON), (ZIEL_LAT, ANDERER_ROUTE_LON)
    elif route == "kreuz":
        a, b = (KREUZ_LAT, KREUZ_WEST_LON), (KREUZ_LAT, KREUZ_OST_LON)
    else:
        raise ValueError(route)
    etappen = [_etappe("S1", tag, a, b, start=start, ziel=ziel)]
    if mit_folgetag:
        etappen.append(_etappe(
            "S2", tag + timedelta(days=1), b, (FOLGETAG_ZIEL_LAT, b[1]),
            start=start, ziel=ziel,
        ))
    daten = {
        "id": trip_id, "name": name, "stages": etappen,
        "official_alerts_enabled": False,
        "report_config": {
            "trip_id": trip_id, "send_email": True, "send_telegram": True,
            "send_sms": True, "send_premium_sms": True,
            # Weit weg vom Testzeitpunkt (Vorlauf-Sperre #1594 bleibt still).
            "morning_time": "05:00", "evening_time": "21:00",
        },
    }
    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(json.dumps(daten), encoding="utf-8")


#: Mehrsegment-Etappen auf demselben Meridian (Wegpunkte sind Trackpunkte
#: von ``heute_track_punkte``): (Breite, Ankunftszeit "HH:MM"). Ungleiches
#: Tempo je Segment, damit eine Fortschreibung ueber nur EIN Segment oder ein
#: einheitliches Etappentempo sichtbar falsch wird.
FAHRPLAN_ZWEI = ((START_LAT, "08:00"), (GAP_NORD_LAT, "10:00"), (ZIEL_LAT, "16:00"))
#: Wie ``FAHRPLAN_ZWEI``, aber mit einer Stunde Rast am Zwischenpunkt
#: (Segment ohne Strecke, 10:00-11:00).
FAHRPLAN_RAST = (
    (START_LAT, "08:00"), (GAP_NORD_LAT, "10:00"), (GAP_NORD_LAT, "11:00"), (ZIEL_LAT, "16:00"),
)


def trip_schreiben_fahrplan(user_id: str, trip_id: str, fahrplan, *, tag: date = TAG) -> None:
    """Trip mit EINER Etappe auf ``ROUTE_LON`` nach ``fahrplan`` (roh, wie
    :func:`trip_schreiben`)."""
    etappe = {
        "id": "S1", "name": "Etappe S1", "date": tag.isoformat(),
        "waypoints": [
            _wegpunkt(f"S1w{i}", lat, ROUTE_LON, zeit) for i, (lat, zeit) in enumerate(fahrplan)
        ],
    }
    daten = {
        "id": trip_id, "name": "GPS-Fix-Fahrplan", "stages": [etappe],
        "official_alerts_enabled": False,
        "report_config": {
            "trip_id": trip_id, "send_email": True, "morning_time": "05:00",
            "evening_time": "21:00",
        },
    }
    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(json.dumps(daten), encoding="utf-8")


def _fahrplan_zeiten(fahrplan, tag: date = TAG):
    return [(lat, ortszeit(*map(int, zeit.split(":")), tag=tag)) for lat, zeit in fahrplan]


def planzeit_bei(fahrplan, lat: float) -> datetime:
    """Planzeit, zu der der Plan die Breite ``lat`` erreicht (erstes
    bewegtes Segment, das sie enthaelt) -- geschlossen, nicht ueber den
    Pruefling."""
    zeiten = _fahrplan_zeiten(fahrplan)
    for (la, ta), (lb, tb) in zip(zeiten, zeiten[1:]):
        if lb > la and la - 1e-12 <= lat <= lb + 1e-12:
            return ta + (tb - ta) * ((lat - la) / (lb - la))
    raise AssertionError(f"Testaufbau: {lat} liegt nicht auf dem Fahrplan")


def plan_lat_bei(fahrplan, t: datetime) -> float:
    """Planbreite zur Planzeit ``t``; in einer Rast der Rastort, vor dem
    Start der Start, nach der Ankunft das Ziel."""
    zeiten = _fahrplan_zeiten(fahrplan)
    if t <= zeiten[0][1]:
        return zeiten[0][0]
    for (la, ta), (lb, tb) in zip(zeiten, zeiten[1:]):
        if t <= tb:
            return la + (lb - la) * ((t - ta) / (tb - ta))
    return zeiten[-1][0]


def lade_trip(user_id: str, trip_id: str):
    """Der Trip so, wie ihn JEDER Konsument bekommt: ``load_all_trips(uid)``."""
    return next(t for t in load_all_trips(user_id) if t.id == trip_id)


def fix_datei(user_id: str) -> Path:
    """Spec: eigene Laufzeitdatei je Nutzer, nicht im Trip-JSON."""
    return get_data_dir(user_id) / "position_fix.json"


def alle_fix_dateien(data_root: Path) -> list[Path]:
    return sorted(data_root.rglob("position_fix.json"))
