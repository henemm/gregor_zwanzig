"""TDD RED — Issue #822: Radar-/Regen-Nowcast-Alert segmentbewusst machen.

RED-Treiber:
- AC-1: ImportError — `services.trip_segments` existiert noch nicht.
- AC-2: AssertionError — check_radar_alerts wählt heute stage.waypoints[0], nicht
        das zeitlich aktive Segment (falsche Koordinaten an get_nowcast).
- AC-3: AssertionError — get_nowcast wird mit waypoints[0]-Coords aufgerufen, nicht
        mit active.start_point.lat/lon (welches für den Test abweicht).
- AC-4: AssertionError — Mail-Body enthält heute kein Segment-Label „Etappe N, km X–Y"
        und keinen dynamischen Cooldown-Text.
- AC-5: TypeError — format_now_text hat heute keinen `tz`-Parameter.
- AC-6: AssertionError — Body enthält „90 Minuten" / „2 Stunden" noch nicht.

Guard-Tests (vermutlich schon grün):
- AC-7: Throttle-Semantik aus #773 — markiert als REGRESSION-GUARD.
- AC-8: Mandantentrennung — markiert als REGRESSION-GUARD.

Mock-Regel: KEIN Mock()/patch()/MagicMock.
- frame_source (DI-Seam von RadarNowcastService) liefert deterministische Regen-Frames.
- TripAlertService(radar_service=RadarNowcastService(frame_source=...)) injiziert den Seam.

SPEC: docs/specs/modules/issue_822_radar_nowcast_segment.md

═══════════════════════════════════════════════════════════════════════════
Issue #2017 (Scheibe B) — Stufe 3 der Verfeinerungskette
═══════════════════════════════════════════════════════════════════════════

Der Abfragepunkt des Radar-Nowcasts hat drei Stufen durchlaufen:

  | Stufe | Issue  | Abfragepunkt                                        |
  |-------|--------|-----------------------------------------------------|
  | 1     | #656   | `waypoints[0]` — erster Wegpunkt des Tages           |
  | 2     | #822   | `active.start_point` — Start des aktiven Segments    |
  | 3     | #2017  | Position zur Mitte des Vorwarnfensters (interpoliert)|

AC-2 und AC-3 dieser Datei sind die Nachweise der STUFE 2. Sie pruefen die
Abfrage-Koordinate gegen `active.start_point` und schreiben damit ab Stufe 3
den Fehler fest, den #2017 behebt — der Startpunkt ist der Wegpunkt, den der
Wanderer bereits verlassen hat (gemessener Median-Versatz 1,99 km bei einem
Vorwarnfenster von 55 Min). Beide werden deshalb mit #2017 EINZELN und
begruendet auf den interpolierten Punkt umgestellt:

- Die Aussage aus #822 bleibt erhalten: geprueft wird weiterhin, dass die
  Abfrage dem AKTIVEN SEGMENT folgt und nicht `waypoints[0]`. Der erwartete
  Punkt liegt per Konstruktion auf der Strecke dieses Segments — waehlte der
  Pruefling wieder das falsche Segment (oder `waypoints[0]`), risse der Test
  genauso wie vorher.
- Neu ist allein, WO auf dieser Strecke: nicht mehr am Anfang, sondern beim
  Zeitanteil `(jetzt + RADAR_ONSET_THRESHOLD_MIN // 2 - start_time) /
  Segmentdauer`. Fuer den VORSCHAU-Fall (Wanderer noch nicht losgelaufen)
  bleibt die Antwort unveraendert `start_point` — Stufe 2 wird nicht
  widerrufen, sondern verfeinert.

Der Erwartungswert wird in `_erwartete_messposition()` ANALYTISCH aus den
Segmentgrenzen gerechnet, nicht durch Aufruf von `position_at_time()` — sonst
prueefte der Test den Prueefling gegen sich selbst.

Neu hinzugekommen (ADDITIV, keine bestehende Testfunktion ersetzt):
  test_2017_ac8_nowcast_an_interpolierter_position_mit_hoehe
  test_2017_ac10_spaeter_onset_wird_nicht_mehr_pauschal_unterdrueckt
  test_2017_ac12_genau_ein_get_nowcast_aufruf_je_lauf

SPEC #2017: docs/specs/modules/fix_2017_nowcast_messpunkt.md (AC-8/AC-10/AC-12)
"""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint

from tests.helpers.arrival_window_fixtures import (
    active_window_offsets,
    past_window_offsets,
    stage_date,
)

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

# Zwei klar voneinander abweichende Koordinatenpaare.
# WP0: waypoints[0] (alter Ist-Code-Pfad in check_radar_alerts).
# SEG: start_point des aktiven Segments (Ziel-Zustand nach #822).
#
# #1667 S1: Die Koordinaten lagen bis 2026-08-10 in Ligurien (UTC+1/+2). Sie
# sind nach Neuseeland (UTC+12) gewandert, weil test_ac3 ein Segment braucht,
# das JETZT SCHON VORBEI ist (wp0 = jetzt-2h). Alle Wegpunktzeiten liegen als
# Ortszeit auf dem Etappentag; westlich von der Datumsgrenze ist "zwei Stunden
# vor jetzt" kurz nach Ortszeit-Mitternacht schlicht nicht darstellbar, das
# geklemmte Fenster rutschte nach vorn und Segment 1 war noch aktiv. In
# UTC+12 liegt der Etappentag zu JEDER UTC-Uhrzeit mindestens zwoelf Stunden
# zurueck. Die Pruefaussage haengt nicht am Ort, nur an der Verschiedenheit
# der drei Punkte.
WP0_LAT, WP0_LON = -41.29, 174.78   # Wellington — waypoints[0] (alter Pfad)
SEG_LAT, SEG_LON = -41.19, 174.93   # Start-Punkt aktives Segment (neuer Pfad)
SEG_END_LAT, SEG_END_LON = -41.09, 175.08

# #1940: Die drei Tests, die ein bereits VERGANGENES erstes Segment brauchen,
# stellen ihre Uhr selbst — ein Ort allein genuegt nicht, denn auch Neuseeland
# hat eine Ortszeit-Mitternacht (sie liegt bei 12:00 UTC, weshalb die CI-Ampel
# taeglich 12:00-13:30 UTC rot war). Gewaehlt ist je Aufrufstelle der
# UTC-Zeitpunkt, zu dem am jeweiligen Ort GENAU 12:00 Ortszeit ist: maximaler
# Abstand zu beiden Tagesgrenzen, innerhalb des Tagesfensters (4-19 Uhr
# Ortszeit, #1584) und fern jeder Ruhezeit. Das Datum ist bewusst fest, sonst
# verschoebe die jeweilige Sommerzeit den Ortsbezug wieder.
UHR_TIROL = "2026-08-18T10:00:00+00:00"       # Europe/Vienna  UTC+2 -> 12:00
UHR_LONDON = "2026-08-18T11:00:00+00:00"      # Europe/London  UTC+1 -> 12:00
UHR_WELLINGTON = "2026-08-18T00:00:00+00:00"  # Pacific/Auckland UTC+12 -> 12:00


# --------------------------------------------------------------------------
# Frame-Factory: deterministische Regen-Frames (kein Mock, DI-Seam)
# --------------------------------------------------------------------------

def _wet_frames(lat: float, lon: float) -> list:
    """Liefert 3 nasse RadarFrames innerhalb des Nowcast-Fensters (jetzt+5 Min).

    Nutzt den dokumentierten DI-Seam frame_source Callable(lat,lon)->frames.
    RadarFrame ist echtes Dataclass-Objekt aus providers.brightsky, kein Mock.
    """
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0),
        RadarFrame(timestamp=now + timedelta(minutes=35), precip_mm_h=2.0),
    ]


# --------------------------------------------------------------------------
# Trip-Factories
# --------------------------------------------------------------------------

def _make_waypoint(uid: str, lat: float, lon: float, arrival: str) -> Waypoint:
    return Waypoint(
        id=uid, name=uid,
        lat=lat, lon=lon, elevation_m=1000.0,
        arrival_calculated=arrival,
    )


def _save_trip_direct(trip, user_id: str) -> None:
    """Write trip JSON directly — bypasses save_trip's Naismith Compute-on-Save.

    Used by AC-2/AC-3 to preserve arrival_calculated values for segment-selection tests.
    """
    import json

    # Issue #1133: get_briefings_dir() (get_trips_dir() ist seit #1708
    # Scheibe B2 entfernter Altbestand) folgt dem autouse-isolierten
    # Daten-Root, denselben Pfad, unter dem TripAlertService via
    # app.loader.load_all_trips() liest — statt der modulweiten
    # DATA_ROOT-Konstante (echter Baum).
    from app.loader import get_briefings_dir
    trips_dir = get_briefings_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)

    def _wp_dict(wp) -> dict:
        d: dict = {"id": wp.id, "name": wp.name, "lat": wp.lat, "lon": wp.lon}
        if wp.elevation_m is not None:
            d["elevation_m"] = wp.elevation_m
        if wp.arrival_calculated is not None:
            d["arrival_calculated"] = wp.arrival_calculated
        return d

    def _stage_dict(s) -> dict:
        d: dict = {
            "id": s.id,
            "name": s.name,
            "date": s.date.isoformat(),
            "waypoints": [_wp_dict(w) for w in s.waypoints],
        }
        if s.start_time:
            d["start_time"] = s.start_time.strftime("%H:%M")
        return d

    data: dict = {
        "id": trip.id,
        "name": trip.name,
        "stages": [_stage_dict(s) for s in trip.stages],
    }
    if getattr(trip, "alert_cooldown_minutes", None) is not None:
        data["alert_cooldown_minutes"] = trip.alert_cooldown_minutes
    if trip.report_config is not None:
        rc = trip.report_config
        data["report_config"] = {
            "trip_id": rc.trip_id,
            "send_email": getattr(rc, "send_email", True),
            "send_telegram": getattr(rc, "send_telegram", False),
        }

    path = trips_dir / f"{trip.id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


# --------------------------------------------------------------------------
# #2017: analytisch erwarteter Messpunkt (kein Aufruf von position_at_time)
# --------------------------------------------------------------------------

def _alarm_offset_minuten() -> int:
    """Zieloffset des ALARM-Pfads = halbes Vorwarnfenster.

    Gelesen ueber die MODUL-Referenz, nie als `from ... import` gebunden: der
    Laufzeit-Drift-Waechter aus #2009 (`test_radar_onset_threshold_variance.py
    ::test_ac1_shared_threshold_drives_both_paths`) setzt die Konstante zur
    Laufzeit um; eine beim Import gebundene Kopie liefe still daran vorbei.
    """
    from services import radar_service as radar_service_mod

    return radar_service_mod.RADAR_ONSET_THRESHOLD_MIN // 2


def _erwartete_messposition(trip, now_utc: datetime, offset_minuten: int):
    """(aktives Segment, Zeitanteil p, (lat, lon, elevation_m)) zum Zeitpunkt
    `now_utc + offset_minuten` — ANALYTISCH gerechnet.

    Bewusst OHNE `position_at_time()`: der Erwartungswert entsteht hier aus
    den Segmentgrenzen und der linearen Formel, nicht aus dem Pruefling. Sonst
    waere der Test gegen jede Verfaelschung des Prueflings blind, weil er sie
    mitmachte.

    Die SEGMENTWAHL kommt aus `resolve_current_segment()` — derselben Quelle,
    aus der auch `check_radar_alerts()` sie bezieht. Damit prueft der Test
    weiterhin die #822-Aussage (die Abfrage folgt dem aktiven Segment) und
    zusaetzlich die #2017-Aussage (sie folgt der Position IM Segment).
    """
    from services.trip_day import trip_local_today
    from services.trip_segments import resolve_current_segment

    aufgeloest = resolve_current_segment(trip, now_utc, trip_local_today(trip, now_utc))
    assert aufgeloest is not None, (
        "Testvoraussetzung: es muss ein aktives Segment geben"
    )
    active, _segment_date = aufgeloest
    at = now_utc + timedelta(minutes=offset_minuten)
    spanne = (active.end_time - active.start_time).total_seconds()
    assert spanne > 0, "Testvoraussetzung: das Segment braucht eine echte Dauer"
    p = (at - active.start_time).total_seconds() / spanne
    assert 0.0 < p < 1.0, (
        f"Testvoraussetzung: der Zieloffset muss INNERHALB des aktiven "
        f"Segments liegen (Zeitanteil p={p:.4f}) — sonst prueft der Fall die "
        f"Vorwaertssuche/Klemmung statt der Interpolation"
    )
    sp, ep = active.start_point, active.end_point
    hoehe = None
    if sp.elevation_m is not None and ep.elevation_m is not None:
        hoehe = sp.elevation_m + p * (ep.elevation_m - sp.elevation_m)
    return active, p, (
        sp.lat + p * (ep.lat - sp.lat),
        sp.lon + p * (ep.lon - sp.lon),
        hoehe,
    )


def _ensure_real_user_dir(uid: str) -> None:
    """Issue #1133: trip_alert.py/alert_state.py schreiben alert_log/
    radar_alert_throttle weiterhin über die relative "data/users/..."-
    Konstruktion (bewusst nicht migriert, Known Limitations) und setzen die
    Existenz des Nutzerverzeichnisses voraus. Vor der #1133-Isolation legte
    _save_trip_direct dieses Verzeichnis als Nebeneffekt im echten Baum an.
    """
    (DATA_ROOT / uid).mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# AC-1: Segment-Helfer-Roundtrip (RED: ImportError)
# --------------------------------------------------------------------------

@freeze_time(UHR_TIROL, tick=True)
def test_ac1_segment_helper_roundtrip_bit_identical():
    """AC-1: `services.trip_segments.convert_trip_to_segments` existiert noch
    NICHT → ImportError = RED-Treiber.

    Nach Implementierung muss convert_trip_to_segments(trip, target_date) die
    identische Segmentliste liefern wie
    TripReportSchedulerService._convert_trip_to_segments für denselben Trip+Datum.

    Bit-Identität: gleiche Anzahl, segment_id, distance_from_start_km,
    start_time/end_time (UTC), lat/lon.
    """
    # RED: Dieses Modul existiert noch nicht → ImportError.
    from services.trip_segments import convert_trip_to_segments  # RED: ImportError erwartet

    from services.trip_report_scheduler import TripReportSchedulerService
    from app.config import Settings

    # Trip mit 3 Waypoints und arrival_calculated (Innsbruck-Region)
    # #1667 S1: die drei Ankunftszeiten kommen aus dem wanduhr-robusten Helfer
    # (er nimmt beliebig viele Versaetze), statt roh ueber Mitternacht zu
    # rechnen. Die Bit-Identitaets-Aussage dieses Tests haengt nicht an
    # konkreten Uhrzeiten, sehr wohl aber an monoton steigenden Zeiten:
    # kollabierte Segmente wuerden auf beiden Seiten uebersprungen und der
    # Vergleich waere leer gegen leer.
    lat, lon = 47.05, 11.40
    arr0, arr1, arr2 = active_window_offsets(lat, lon, -240, -120, 120)
    wp0 = _make_waypoint("WP0", lat, lon, arr0)
    wp1 = _make_waypoint("WP1", lat + 0.1, lon + 0.1, arr1)
    wp2 = _make_waypoint("WP2", lat + 0.2, lon + 0.2, arr2)
    stage = Stage(
        id="S1", name="Tag 1",
        date=stage_date(lat, lon),
        waypoints=[wp0, wp1, wp2],
    )
    trip = Trip(id="tdd-822-ac1-trip", name="AC1 Trip", stages=[stage])
    target_date = stage_date(lat, lon)

    svc = TripReportSchedulerService(settings=Settings())
    expected = svc._convert_trip_to_segments(trip, target_date)
    actual = convert_trip_to_segments(trip, target_date)

    assert len(actual) == len(expected), (
        f"Segmentanzahl verschieden: {len(actual)} vs {len(expected)}"
    )
    for i, (a, e) in enumerate(zip(actual, expected)):
        assert str(a.segment_id) == str(e.segment_id), \
            f"Seg {i}: segment_id abweichend: {a.segment_id!r} vs {e.segment_id!r}"
        assert a.start_point.distance_from_start_km == e.start_point.distance_from_start_km, \
            f"Seg {i}: start_point.distance_from_start_km abweichend"
        assert a.end_point.distance_from_start_km == e.end_point.distance_from_start_km, \
            f"Seg {i}: end_point.distance_from_start_km abweichend"
        assert a.start_time == e.start_time, \
            f"Seg {i}: start_time abweichend: {a.start_time} vs {e.start_time}"
        assert a.end_time == e.end_time, \
            f"Seg {i}: end_time abweichend: {a.end_time} vs {e.end_time}"
        assert a.start_point.lat == e.start_point.lat, f"Seg {i}: start lat abweichend"
        assert a.start_point.lon == e.start_point.lon, f"Seg {i}: start lon abweichend"
        assert a.end_point.lat == e.end_point.lat, f"Seg {i}: end lat abweichend"
        assert a.end_point.lon == e.end_point.lon, f"Seg {i}: end lon abweichend"


# --------------------------------------------------------------------------
# AC-2: Segment-Auswahl nach Zeit (RED: falsches Segment gewählt)
# --------------------------------------------------------------------------

@freeze_time(UHR_LONDON, tick=True)
def test_ac2_segment_selection_by_time():
    """AC-2: check_radar_alerts wählt das zeitlich aktive Segment.

    Aufbau: 3 Waypoints → 2 reguläre Segmente + Ziel-Segment.
      Segment-1 (wp0→wp1): [now-2h, now-1h]  → bereits vorbei
      Segment-2 (wp1→wp2): [now-1h, now+1h]  → aktiv

    Nachweis Fall (a): get_nowcast erhält einen Punkt AUF Segment 2 — seit
    #2017 nicht mehr dessen Startpunkt (wp1), sondern die zur Fenstermitte
    (`jetzt + RADAR_ONSET_THRESHOLD_MIN // 2`) interpolierte Position
    zwischen wp1 und wp2.
    RED (#822, historisch): check_radar_alerts nutzte stage.waypoints[0] → wp0.
    RED (#2017, heute): check_radar_alerts nutzt active.start_point → wp1.

    🔴 Warum die Erwartung angepasst wurde (Verfeinerungskette #656 → #822 →
    #2017): Die #822-Aussage „die Abfrage folgt dem AKTIVEN SEGMENT, nicht
    waypoints[0]" bleibt vollstaendig erhalten — der erwartete Punkt liegt per
    Konstruktion auf der Strecke wp1→wp2 und ist von wp0 wie von wp1 klar
    verschieden. Geaendert hat sich nur die Stelle AUF dieser Strecke: der
    Startpunkt ist der Wegpunkt, den der Wanderer bereits verlassen hat
    (Median 1,99 km Versatz, #2017). Die bisherige Toleranz `< 0.01°` (≈1,1 km)
    war zugleich die Stelle, an der der alte Punkt festgeschrieben war.

    Nachweis Fall (c): Trip mit Segmenten alle in der Vergangenheit → count=0.
    RED: Heute keine Logik für „alle Segmente vorbei → kein Alert" implementiert.

    Hinweis: _save_trip_direct umgeht Naismith Compute-on-Save (Issue #802),
    damit arrival_calculated exakt kontrolliert werden kann.
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    lat_base, lon_base = 51.50, 0.00  # lon=0 → Europe/London, BST=UTC+1 in summer
    today = stage_date(lat_base, lon_base)

    # --- Fall (a): aktives Segment ---
    # Seg 1: [now-2h, now-1h] → vorbei; Seg 2: [now-1h, now+1h] → aktiv.
    # #1667 S1: der Helfer rechnet die Ortszeit selbst (der frühere manuelle
    # utcoffset-Aufschlag entfällt) und klemmt das Fenster auf den Etappentag.
    local_minus2h, local_minus1h, local_plus1h = active_window_offsets(
        lat_base, lon_base, -120, -60, 60
    )

    wp0 = _make_waypoint("WP0", lat_base, lon_base, local_minus2h)
    wp1 = _make_waypoint("WP1", lat_base + 0.10, lon_base + 0.10, local_minus1h)
    wp2 = _make_waypoint("WP2", lat_base + 0.20, lon_base + 0.20, local_plus1h)

    stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1, wp2])
    trip_id = f"tdd-822-ac2-ab-{uuid.uuid4().hex[:6]}"
    trip = Trip(id=trip_id, name="AC2 Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, send_telegram=False,
        alert_on_changes=False,
    )

    recorded_coords: list[tuple[float, float]] = []

    def _recording_frames(lat_: float, lon_: float) -> list:
        recorded_coords.append((lat_, lon_))
        return _wet_frames(lat_, lon_)

    uid = f"tdd-822-ac2-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        _save_trip_direct(trip, uid)

        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_recording_frames),
        )
        svc.clear_radar_throttle(trip_id)
        # Bezugszeitpunkt fuer die Erwartung: unmittelbar VOR dem Lauf
        # abgenommen. Die Uhr laeuft hier mit (`tick=True`), der Pruefling
        # nimmt sein eigenes `now` Sekundenbruchteile spaeter — der Unterschied
        # schlaegt bei 120 Min Segmentdauer mit weniger als 1e-4 ° durch und
        # liegt damit weit unter der Toleranz.
        now_ref = datetime.now(timezone.utc)
        svc.check_radar_alerts()

        assert len(recorded_coords) >= 1, (
            "AC-2(a): get_nowcast nicht aufgerufen — kein Segment als aktiv erkannt"
        )

        # #2017: erwarteter Punkt = analytische Interpolation auf Segment 2
        # (wp1→wp2) zur Mitte des Vorwarnfensters.
        from app.loader import load_all_trips

        trip_von_platte = next(
            t for t in load_all_trips(user_id=uid) if t.id == trip_id
        )
        active, p, (expected_lat, expected_lon, _h) = _erwartete_messposition(
            trip_von_platte, now_ref, _alarm_offset_minuten(),
        )
        actual_lat, actual_lon = recorded_coords[0]

        # Nicht-Trivialitaet: der erwartete Punkt muss vom Segment-Startpunkt
        # UND von waypoints[0] messbar abweichen — sonst waere die Zusicherung
        # in beiden Richtungen leer.
        assert abs(expected_lat - active.start_point.lat) > 0.01, (
            f"Testvoraussetzung: interpolierter Punkt (lat {expected_lat:.4f}) "
            f"und Segment-Startpunkt (lat {active.start_point.lat:.4f}) muessen "
            f"sich unterscheiden, Zeitanteil p={p:.4f}"
        )
        assert abs(expected_lat - lat_base) > 0.01, (
            "Testvoraussetzung: interpolierter Punkt und waypoints[0] muessen "
            "sich unterscheiden (#822-Aussage bleibt pruefbar)"
        )

        assert abs(actual_lat - expected_lat) < 0.002, (
            f"AC-2(a)/#2017: get_nowcast mit lat={actual_lat:.4f}; erwartet der "
            f"zur Fenstermitte interpolierte Punkt auf Segment 2 "
            f"lat={expected_lat:.4f} (Zeitanteil p={p:.4f} zwischen wp1 "
            f"{active.start_point.lat:.4f} und wp2 {active.end_point.lat:.4f}). "
            f"lat={active.start_point.lat:.4f} waere der ALTE Messpunkt "
            f"(Segment-Startpunkt, #822), lat={lat_base:.4f} der noch aeltere "
            f"(waypoints[0], vor #822)."
        )
        assert abs(actual_lon - expected_lon) < 0.002, (
            f"AC-2(a)/#2017: get_nowcast mit lon={actual_lon:.4f}; erwartet "
            f"lon={expected_lon:.4f} (interpoliert, p={p:.4f}). "
            f"lon={active.start_point.lon:.4f} waere der ALTE Messpunkt, "
            f"lon={lon_base:.4f} der noch aeltere (waypoints[0])."
        )

        # --- Fall (c): alle Segmente bereits vorbei → kein Alert ---
        # #1667 S1: Wegpunkte aus dem Vergangenheits-Helfer statt aus roher
        # now-Nh-Arithmetik.
        # ⚠️ Diese Fixture legt NUR die Wegpunkte in die Vergangenheit. Seit
        # Issue #1584 endet das Ziel-Segment am Tagesfenster-Ende (19:00
        # Ortszeit), nicht mehr bei "Ankunft + 2 h" — der Trip ist damit
        # tagsüber gar nicht "vorbei". Dass die Zusicherung trotzdem hält,
        # liegt an send_email=False/send_telegram=False unten: ohne offenen
        # Kanal zählt check_radar_alerts() nach #827 ohnehin nichts. Der Fall
        # prüft hier also nicht, was seine Überschrift behauptet; das ist ein
        # Altbefund, den S1 nicht repariert (S1 ändert keinen Produktivcode
        # und keine Zusicherung). Das saubere Gegenstück steht in
        # test_issue_818_radar_briefing_integration.py::
        # test_ac5_past_segment_no_alert_guard_test.
        local_minus4h, local_minus2h_c = past_window_offsets(
            lat_base, lon_base, -240, -120
        )
        wp_p0 = _make_waypoint("P0", lat_base, lon_base, local_minus4h)
        wp_p1 = _make_waypoint("P1", lat_base + 0.05, lon_base + 0.05, local_minus2h_c)
        stage_past = Stage(id="S1", name="Tag 1", date=today,
                           waypoints=[wp_p0, wp_p1])
        trip_past_id = f"tdd-822-ac2-past-{uuid.uuid4().hex[:6]}"
        trip_past = Trip(id=trip_past_id, name="AC2 Past", stages=[stage_past])
        trip_past.report_config = TripReportConfig(
            trip_id=trip_past_id, send_email=False, send_telegram=False,
            alert_on_changes=False,
        )
        uid_past = f"tdd-822-ac2p-{uuid.uuid4().hex[:6]}"
        _clean_user(uid_past)
        try:
            _save_trip_direct(trip_past, uid_past)
            past_coords: list = []

            def _past_frames(la: float, lo: float) -> list:
                past_coords.append((la, lo))
                return _wet_frames(la, lo)

            svc_past = TripAlertService(
                throttle_hours=2, user_id=uid_past,
                radar_service=RadarNowcastService(frame_source=_past_frames),
            )
            svc_past.clear_radar_throttle(trip_past_id)
            count_past = svc_past.check_radar_alerts()
            assert count_past == 0, (
                f"AC-2(c): Nach allen Segmenten darf KEIN Alert gesendet werden, war {count_past}"
            )
        finally:
            _clean_user(uid_past)

    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-3: Nowcast an Segment-Koordinaten (RED: waypoints[0] statt start_point)
# --------------------------------------------------------------------------

@freeze_time(UHR_WELLINGTON, tick=True)
def test_ac3_nowcast_called_at_segment_coordinates():
    """AC-3: get_nowcast wird mit active.start_point.lat/lon aufgerufen, NICHT
    mit stage.waypoints[0]-Koordinaten (wenn diese abweichen).

    Trip: 3 Waypoints.
      wp0: (WP0_LAT, WP0_LON) ← waypoints[0] — alter Pfad
      wp1: (SEG_LAT, SEG_LON) ← start_point Segment-2 (aktiv) — neuer Pfad
      wp2: (SEG_END_LAT, SEG_END_LON)

    Zeiten:
      Segment-1 (wp0→wp1): [now-2h, now-0.5h] → vorbei
      Segment-2 (wp1→wp2): [now-0.5h, now+1.5h] → aktiv

    Nachweis: recorded_coords[0] muss ein Punkt AUF Segment 2 sein, NICHT
    (WP0_LAT, WP0_LON). Genau 1 get_nowcast-Call pro Trip-Lauf.

    🔴 Angepasst mit #2017 (Verfeinerungskette #656 → #822 → #2017): geprueft
    wurde bisher exakte Gleichheit mit `active.start_point` = (SEG_LAT,
    SEG_LON). Seit #2017 ist der Messpunkt die zur Mitte des Vorwarnfensters
    (`jetzt + RADAR_ONSET_THRESHOLD_MIN // 2`) interpolierte Position zwischen
    SEG und SEG_END. Die #822-Aussage bleibt: der Punkt stammt aus dem
    AKTIVEN Segment, nicht aus `waypoints[0]` — er liegt auf der Strecke
    SEG→SEG_END und ist von WP0 weit entfernt. Fuer den Vorschau-Fall
    (Wanderer noch nicht losgelaufen) liefert #2017 unveraendert
    `start_point`; hier ist das Segment aktiv, deshalb greift die
    Verfeinerung.

    Hinweis: _save_trip_direct umgeht Naismith Compute-on-Save (Issue #802).
    Die Ortszeit-Umrechnung macht seit #1667 S1 der Helfer; die Koordinaten
    liegen seither in Neuseeland (Begründung an der Konstanten-Definition).
    """
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    uid = f"tdd-822-ac3-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        today = stage_date(WP0_LAT, WP0_LON)

        # Seg 1: [now-2h, now-30m] → vorbei; Seg 2: [now-30m, now+90m] → aktiv.
        # #1667 S1: der Helfer rechnet die Ortszeit selbst (der frühere manuelle
        # utcoffset-Aufschlag entfällt) und klemmt das Fenster auf den
        # Etappentag — damit entfällt auch die alte Einschränkung "nur sicher
        # wenn now.hour >= 2".
        local_minus2h, local_minus30m, local_plus90m = active_window_offsets(
            WP0_LAT, WP0_LON, -120, -30, 90
        )

        wp0 = _make_waypoint("WP0", WP0_LAT, WP0_LON, local_minus2h)
        wp1 = _make_waypoint("WP1", SEG_LAT, SEG_LON, local_minus30m)
        wp2 = _make_waypoint("WP2", SEG_END_LAT, SEG_END_LON, local_plus90m)

        stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1, wp2])
        trip_id = f"tdd-822-ac3-trip-{uuid.uuid4().hex[:6]}"
        trip = Trip(id=trip_id, name="AC3 Trip", stages=[stage])
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=False, send_telegram=False,
            alert_on_changes=False,
        )
        _save_trip_direct(trip, uid)

        recorded_coords: list[tuple[float, float]] = []
        call_count = [0]

        def _recording_wet_frames(lat: float, lon: float) -> list:
            call_count[0] += 1
            recorded_coords.append((lat, lon))
            return _wet_frames(lat, lon)

        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_recording_wet_frames),
        )
        svc.clear_radar_throttle(trip_id)
        # s. AC-2: Bezugszeitpunkt unmittelbar vor dem Lauf, Uhr laeuft mit.
        now_ref = datetime.now(timezone.utc)
        svc.check_radar_alerts()

        assert call_count[0] == 1, (
            f"AC-3: get_nowcast muss genau 1× aufgerufen werden, war {call_count[0]}"
        )

        from app.loader import load_all_trips

        trip_von_platte = next(
            t for t in load_all_trips(user_id=uid) if t.id == trip_id
        )
        active, p, (expected_lat, expected_lon, _h) = _erwartete_messposition(
            trip_von_platte, now_ref, _alarm_offset_minuten(),
        )
        actual_lat, actual_lon = recorded_coords[0]

        assert abs(expected_lat - SEG_LAT) > 0.01, (
            f"Testvoraussetzung: der interpolierte Punkt (lat "
            f"{expected_lat:.4f}) muss sich vom Segment-Startpunkt SEG_LAT="
            f"{SEG_LAT:.4f} messbar unterscheiden (p={p:.4f})"
        )

        # Nachweis: Koordinaten = interpolierter Punkt AUF Segment 2
        # (SEG→SEG_END), NICHT SEG_LAT/SEG_LON (Startpunkt, #822-Stand) und
        # erst recht nicht WP0_LAT/WP0_LON (waypoints[0], vor #822).
        assert abs(actual_lat - expected_lat) < 0.002, (
            f"AC-3/#2017: get_nowcast mit lat={actual_lat:.4f}; erwartet der "
            f"interpolierte Punkt lat={expected_lat:.4f} (p={p:.4f} zwischen "
            f"SEG_LAT={SEG_LAT:.4f} und SEG_END_LAT={SEG_END_LAT:.4f}). "
            f"lat=SEG_LAT waere der ALTE Messpunkt (Segment-Startpunkt), "
            f"lat=WP0_LAT={WP0_LAT:.4f} der noch aeltere (waypoints[0])."
        )
        assert abs(actual_lon - expected_lon) < 0.002, (
            f"AC-3/#2017: get_nowcast mit lon={actual_lon:.4f}; erwartet "
            f"lon={expected_lon:.4f} (interpoliert, p={p:.4f}). "
            f"lon=SEG_LON={SEG_LON:.4f} waere der ALTE Messpunkt, "
            f"lon=WP0_LON={WP0_LON:.4f} der noch aeltere."
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-4: Mail-Body enthält Segment-Label + Cooldown-Text (RED)
# --------------------------------------------------------------------------

def test_ac4_mail_body_contains_segment_label_and_cooldown():
    """AC-4: Der generierte Alert-Body (via check_radar_alerts + mail_sink DI-Seam) muss:
    - Segment-Label enthalten (aus build_segment_label)
    - GENAU EINE „Quelle:"-Zeile — keine Dopplung durch format_now_text + Body-Builder
    - Human-readable Source-Label, NICHT den rohen Key (z.B. „Radar (DWD)" statt „radar")
    - km-Wert arithmetisch konsistent zur Haversine-Distanz der Test-Waypoints (~13 km)
    - Cooldown-Text „Du erhältst diese Warnung höchstens einmal in N Stunde(n)"

    Kein SMTP nötig (mail_sink fängt Body ab). Kein Mock.
    """
    import math
    from app.config import Settings
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    uid = f"tdd-822-ac4-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        now = datetime.now(timezone.utc)
        lat, lon = 51.50, 0.00  # lon=0 → tz_for_coords returns Europe/London (BST in summer)
        # #1940 AC-6: der Etappentag ist der ORTStag, nicht das Serverdatum.
        # Mit ``now.date()`` liefen Etappendatum und die aus dem Helfer
        # stammenden Ankunftszeiten ab 23:00 UTC auseinander (London UTC+1
        # zeigt dann schon auf den Folgetag), die Etappe wurde nicht gefunden
        # und es entstand gar kein Alarm — dieser Test war taeglich
        # 23:00-00:00 UTC rot. Alle uebrigen Stellen dieser Datei nehmen
        # stage_date() bereits.
        today = stage_date(lat, lon)
        lat1, lon1 = lat + 0.10, lon + 0.10
        # #1667 S1: Ortszeit-Umrechnung und Tagesgrenzen-Klemmung im Helfer.
        arr0, arr1 = active_window_offsets(lat, lon, -60, 60)

        # Haversine-Distanz WP0→WP1 (für km-Plausibilitäts-Check)
        R = 6371.0
        dlat = math.radians(lat1 - lat)
        dlon = math.radians(lon1 - lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat)) * math.cos(math.radians(lat1)) * math.sin(dlon / 2) ** 2
        expected_km = R * 2 * math.asin(math.sqrt(a))  # ≈ 13.1 km

        wp0 = _make_waypoint("WP0", lat, lon, arr0)
        wp1 = _make_waypoint("WP1", lat1, lon1, arr1)
        stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
        trip_id = f"tdd-822-ac4-trip-{uuid.uuid4().hex[:6]}"
        trip = Trip(id=trip_id, name="AC4 Trip", stages=[stage])
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            alert_on_changes=False,
        )
        _save_trip_direct(trip, uid)

        captured: list[dict] = []

        def _sink(subject: str, body: str) -> None:
            captured.append({"subject": subject, "body": body})

        svc = TripAlertService(
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            settings=Settings(
                smtp_host="test.invalid", smtp_user="u", smtp_pass="p",
                mail_to="x@example.com",
            ),
            mail_sink=_sink,
        )
        svc.clear_radar_throttle(trip_id)
        svc.check_radar_alerts()

        assert len(captured) >= 1, (
            "AC-4: Mail-Sink nicht aufgerufen — kein Alert ausgelöst."
        )
        body = captured[0]["body"]

        # F003a — genau EINE „Quelle:"-Zeile (keine Dopplung)
        quelle_count = body.count("Quelle:")
        assert quelle_count == 1, (
            f"AC-4 F003a: Body muss genau 1× 'Quelle:' enthalten, hat {quelle_count}.\n"
            f"Body:\n{body}"
        )

        # F003b — human-readable Source-Label, NICHT roher Key
        assert "Radar (DWD)" in body, (
            f"AC-4 F003b: Body muss 'Radar (DWD)' enthalten (nicht rohen Key 'radar').\n"
            f"Body:\n{body}"
        )
        assert "radar\n" not in body and not body.endswith("radar.") and "Quelle: radar" not in body, (
            f"AC-4 F003b: Body enthält noch rohen Source-Key 'radar'.\nBody:\n{body}"
        )

        # Segment-Label — Issue #1744 A1: die Zeile „Wo & wann" nennt die
        # Etappen-Kennung („Segment 1"), dieselbe Sprache wie Betreff und
        # amtliche Warnung. Vorher stand hier die km-Spanne.
        assert "Segment 1" in body, (
            f"AC-4: Body muss die betroffene Etappe nennen.\nBody:\n{body}"
        )

        # F003c — km-Wert arithmetisch konsistent (Haversine ±2 km Toleranz).
        # Issue #1744 A1: seit die Mail den Ort als Etappen-Kennung nennt, taucht
        # der km-Wert dort nicht mehr auf. Die Zusicherung bleibt trotzdem
        # bestehen — sie haengt jetzt an der QUELLE, die der Alarmpfad selbst
        # liest (`trip_alert.py:1099-1100`: `active.{start,end}_point.
        # distance_from_start_km` aus `resolve_current_segment`), statt an ihrem
        # frueheren Abdruck im Mailtext.
        from services.trip_segments import resolve_current_segment
        _res = resolve_current_segment(trip, datetime.now(timezone.utc), today)
        assert _res is not None, "AC-4 F003c: kein aktives Segment aufloesbar."
        actual_end_km = _res[0].end_point.distance_from_start_km
        assert abs(actual_end_km - expected_km) < 2.0, (
            f"AC-4 F003c: km-Endwert {actual_end_km:.1f} weicht mehr als 2 km von "
            f"Haversine-Distanz {expected_km:.1f} ab."
        )

        # Cooldown-Text
        assert "Du erhältst diese Warnung höchstens einmal in" in body, (
            f"AC-4: Cooldown-Text fehlt.\nBody:\n{body}"
        )
        # Default cooldown = 2h → „2 Stunden"
        assert "2 Stunden" in body, (
            f"AC-4: Default-Cooldown soll '2 Stunden' sein.\nBody:\n{body}"
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-5: format_now_text mit tz-Parameter (RED: TypeError)
# --------------------------------------------------------------------------

def test_ac5_onset_time_in_tour_timezone():
    """AC-5: format_now_text(result, tz=<TourTZ>) formatiert Onset-Zeit in Tour-TZ.

    RED: format_now_text hat keinen `tz`-Parameter → TypeError (unexpected keyword).

    Nach Implementierung: Onset-Zeit in Europe/Berlin (UTC+2 im Sommer) statt Server-TZ.
    """
    from services.radar_service import RadarNowcastService, NowcastResult

    tour_tz = ZoneInfo("Europe/Berlin")

    result = NowcastResult(
        onset_minutes=10,
        intensity_label="Leichter Regen",
        source="radar",
        frames=[],
        is_convective=False,
    )

    svc = RadarNowcastService()

    # RED: format_now_text() got unexpected keyword argument 'tz'
    text = svc.format_now_text(result, tz=tour_tz)

    # Nach Implementierung: Onset-Zeit in Tour-TZ
    now_utc = datetime.now(timezone.utc)
    expected_dt = (now_utc + timedelta(minutes=10)).astimezone(tour_tz)
    expected_hhmm = expected_dt.strftime("%H:%M")

    assert expected_hhmm in text, (
        f"AC-5: Onset-Uhrzeit nicht in Tour-TZ formatiert. "
        f"Erwartet '{expected_hhmm}' (Europe/Berlin) im Text: '{text}'"
    )


# --------------------------------------------------------------------------
# AC-6: Cooldown-Anzeige aus Trip-Einstellung (RED)
# --------------------------------------------------------------------------

def test_ac6_cooldown_display_reflects_trip_setting():
    """AC-6: Dynamischer Cooldown-Text im Mail-Body via check_radar_alerts + mail_sink.

    trip.alert_cooldown_minutes=90 → Body enthält „90 Minuten"
    trip.alert_cooldown_minutes=None (default 2h) → Body enthält „2 Stunden"

    Kein SMTP (mail_sink), kein Mock.
    """
    from app.config import Settings
    from services.trip_alert import TripAlertService
    from services.radar_service import RadarNowcastService

    lat, lon = 51.50, 0.00  # lon=0 → tz_for_coords returns e.g. Europe/London
    today = stage_date(lat, lon)
    # #1667 S1: Ortszeit-Umrechnung und Tagesgrenzen-Klemmung im Helfer.
    arr0, arr1 = active_window_offsets(lat, lon, -60, 60)

    def _make_active_trip(trip_id: str, cooldown: int | None) -> Trip:
        wp0 = _make_waypoint("WP0", lat, lon, arr0)
        wp1 = _make_waypoint("WP1", lat + 0.10, lon + 0.10, arr1)
        stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
        t = Trip(id=trip_id, name="AC6 Trip", stages=[stage])
        if cooldown is not None:
            t = Trip(id=trip_id, name="AC6 Trip", stages=[stage],
                     alert_cooldown_minutes=cooldown)
        t.report_config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            alert_on_changes=False,
        )
        return t

    # Fall (a): alert_cooldown_minutes=90 → „90 Minuten"
    uid_90 = f"tdd-822-ac6a-{uuid.uuid4().hex[:6]}"
    _clean_user(uid_90)
    _ensure_real_user_dir(uid_90)
    try:
        trip_id_90 = f"tdd-822-ac6-90-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id_90, cooldown=90), uid_90)
        captured_90: list[dict] = []

        def _sink_90(subject: str, body: str) -> None:
            captured_90.append({"subject": subject, "body": body})

        svc_90 = TripAlertService(
            throttle_hours=2, user_id=uid_90,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            settings=Settings(
                smtp_host="test.invalid", smtp_user="u", smtp_pass="p",
                mail_to="x@example.com",
            ),
            mail_sink=_sink_90,
        )
        svc_90.clear_radar_throttle(trip_id_90)
        svc_90.check_radar_alerts()

        assert len(captured_90) >= 1, "AC-6(a): Kein Alert mit cooldown=90"
        body_90 = captured_90[0]["body"]
        assert "90 Minuten" in body_90, (
            f"AC-6(a): alert_cooldown_minutes=90 → Body soll '90 Minuten' enthalten.\n"
            f"Body:\n{body_90}"
        )
    finally:
        _clean_user(uid_90)

    # Fall (b): alert_cooldown_minutes=None, throttle_hours=2 → „2 Stunden"
    uid_2h = f"tdd-822-ac6b-{uuid.uuid4().hex[:6]}"
    _clean_user(uid_2h)
    _ensure_real_user_dir(uid_2h)
    try:
        trip_id_2h = f"tdd-822-ac6-2h-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id_2h, cooldown=None), uid_2h)
        captured_2h: list[dict] = []

        def _sink_2h(subject: str, body: str) -> None:
            captured_2h.append({"subject": subject, "body": body})

        svc_2h = TripAlertService(
            throttle_hours=2, user_id=uid_2h,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            settings=Settings(
                smtp_host="test.invalid", smtp_user="u", smtp_pass="p",
                mail_to="x@example.com",
            ),
            mail_sink=_sink_2h,
        )
        svc_2h.clear_radar_throttle(trip_id_2h)
        svc_2h.check_radar_alerts()

        assert len(captured_2h) >= 1, "AC-6(b): Kein Alert mit default-cooldown"
        body_2h = captured_2h[0]["body"]
        assert "2 Stunden" in body_2h, (
            f"AC-6(b): Default 2h-Cooldown → Body soll '2 Stunden' enthalten.\n"
            f"Body:\n{body_2h}"
        )
    finally:
        _clean_user(uid_2h)


# --------------------------------------------------------------------------
# AC-7: Throttle-Recording unverändert — REGRESSION-GUARD (#773)
# --------------------------------------------------------------------------

def test_ac7_throttle_recording_unchanged():
    """AC-7: REGRESSION-GUARD — Throttle-Semantik aus #773 bleibt nach #822-Refactor.

    Erster Lauf → Alert → radar_alert_throttle.json gesetzt.
    Zweiter Lauf innerhalb Fenster → kein zweiter Alert.

    #827-Update: Recording setzt Throttle nur bei tatsächlicher Zustellung.
    Trip hat send_email=True + Settings mit SMTP, damit Zustellung erfolgt.

    Dieser Test kann vor #822-Implementierung grün sein (Guard-Funktion).
    """
    from services.trip_alert import TripAlertService
    from app.config import Settings
    from services.radar_service import RadarNowcastService

    uid = f"tdd-822-ac7-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        # Aktives Segment: [now-1h, now+1h]
        # Island (lat=64, lon=-22): UTC+0 ganzjährig (kein DST).
        # _save_trip_direct nötig: save_trip recomputes arrival_calculated via Naismith
        # und würde die Zeiten überschreiben.
        # #1667 S1: Zeiten aus dem wanduhr-robusten Helfer.
        lat, lon = 64.0, -22.0
        today = stage_date(lat, lon)
        arr0, arr1 = active_window_offsets(lat, lon, -60, 60)
        wp0 = _make_waypoint("WP0", lat, lon, arr0)
        wp1 = _make_waypoint("WP1", lat + 0.05, lon + 0.05, arr1)
        stage = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
        trip_id = "tdd-822-ac7-trip"
        trip = Trip(id=trip_id, name="AC7 Trip", stages=[stage])
        # #827: send_email=True damit Zustellung möglich → Recording + Throttle greifen
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=True, send_telegram=False,
            alert_on_changes=False,
        )
        _save_trip_direct(trip, uid)

        # Settings mit SMTP damit can_send_email()=True
        settings = Settings(
            smtp_host="smtp.test.invalid",
            smtp_user="test@test.invalid",
            smtp_pass="testpass",
            mail_to="to@test.invalid",
        )
        mail_calls: list = []
        svc = TripAlertService(
            settings=settings,
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        svc.clear_radar_throttle(trip_id)

        # Erster Lauf
        count1 = svc.check_radar_alerts()

        assert count1 >= 1, (
            "AC-7: Erster Lauf muss mindestens einen Alert auslösen "
            "(aktives Segment + nasse Frames + send_email=True)"
        )
        # Issue #1213: Radar-Throttle-Quelle ist jetzt der gemeinsame
        # ThrottleStore (isolierter `get_data_dir(uid)`-Pfad, #1133) statt
        # der Legacy-Datei `radar_alert_throttle.json`.
        from services.throttle_store import ThrottleStore
        assert ThrottleStore(uid).last_sent("radar", trip_id) is not None, (
            "AC-7: ThrottleStore muss nach erstem Alert einen Radar-Timestamp haben"
        )

        # Zweiter Lauf innerhalb Throttle-Fenster (KEIN clear_radar_throttle)
        svc2 = TripAlertService(
            settings=settings,
            throttle_hours=2, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        count2 = svc2.check_radar_alerts()
        assert count2 == 0, (
            f"AC-7: Zweiter Lauf im Throttle-Fenster muss 0 Alerts liefern, war {count2}"
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-8: Mandantentrennung — REGRESSION-GUARD (#773)
# --------------------------------------------------------------------------

def test_ac8_mandantentrennung_isolated():
    """AC-8: REGRESSION-GUARD — Mandantentrennung bleibt nach #822-Refactor.

    Lauf unter uid_a berührt data/users/uid_b/ nicht.

    Dieser Test kann vor #822-Implementierung grün sein (Guard-Funktion).
    """
    from services.trip_alert import TripAlertService
    from app.loader import save_trip
    from services.radar_service import RadarNowcastService

    uid_a = f"tdd-822-ac8a-{uuid.uuid4().hex[:6]}"
    uid_b = f"tdd-822-ac8b-{uuid.uuid4().hex[:6]}"
    _clean_user(uid_a)
    _ensure_real_user_dir(uid_a)
    _clean_user(uid_b)
    _ensure_real_user_dir(uid_b)
    try:
        lat, lon = 51.5, 0.0  # UTC-Zone
        today = stage_date(lat, lon)
        # #1667 S1: Zeiten aus dem wanduhr-robusten Helfer.
        arr0, arr1 = active_window_offsets(lat, lon, -60, 60)

        def _make_trip_for(uid: str, trip_id: str) -> Trip:
            wp0 = _make_waypoint("WP0", lat, lon, arr0)
            wp1 = _make_waypoint("WP1", lat + 0.05, lon + 0.05, arr1)
            s = Stage(id="S1", name="Tag 1", date=today, waypoints=[wp0, wp1])
            t = Trip(id=trip_id, name=f"AC8 {uid}", stages=[s])
            t.report_config = TripReportConfig(
                trip_id=trip_id, send_email=False, send_telegram=False,
                alert_on_changes=False,
            )
            return t

        save_trip(_make_trip_for(uid_a, "trip-a"), user_id=uid_a)
        save_trip(_make_trip_for(uid_b, "trip-b"), user_id=uid_b)

        # Snapshot der Dateien unter uid_b VOR Lauf von uid_a
        dir_b = DATA_ROOT / uid_b
        files_before = {
            p: p.stat().st_mtime
            for p in dir_b.rglob("*")
            if p.is_file()
        }

        # Lauf unter uid_a
        svc_a = TripAlertService(
            throttle_hours=2, user_id=uid_a,
            radar_service=RadarNowcastService(frame_source=_wet_frames),
        )
        svc_a.clear_radar_throttle("trip-a")
        svc_a.check_radar_alerts()

        # Prüfen: Keine neuen oder veränderten Dateien unter uid_b
        for p in dir_b.rglob("*"):
            if not p.is_file():
                continue
            if p not in files_before:
                pytest.fail(
                    f"AC-8: Neue Datei unter uid_b nach Lauf von uid_a: "
                    f"{p.relative_to(DATA_ROOT)}"
                )
            if p.stat().st_mtime != files_before[p]:
                pytest.fail(
                    f"AC-8: Datei unter uid_b verändert nach Lauf von uid_a: "
                    f"{p.relative_to(DATA_ROOT)}"
                )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)


# ══════════════════════════════════════════════════════════════════════════
# Issue #2017 Scheibe B — Wiring des Messpunkts (AC-8 / AC-10 / AC-12)
#
# ADDITIV: keine der Testfunktionen oberhalb wird ersetzt. Die Bausteine
# kommen aus `tests/helpers/nowcast_gate_fixtures.py` (echte Trips auf der
# isolierten Datenwurzel, echter `frame_source`-DI-Seam, `mail_sink`-Zaehler)
# — dieselbe Ausstattung, die `test_radar_alert_segment_end_guard.py` und
# `test_radar_onset_threshold_variance.py` fuer denselben Pfad benutzen.
#
# 🔴 Gestellte Uhr, nicht Wanduhr: `make_trip()` baut seine Etappe aus
# HH:MM-Ortszeiten auf einem Kalendertag. Ein Zieloffset ueber Mitternacht
# haette kein aktives Segment mehr (und der Fall pruefte dann die
# Vorwaertssuche statt der Interpolation). Bezugszeitpunkt und Ort sind
# dieselben wie in den beiden Schwesterdateien: mittags, Reykjavik (UTC+0
# ganzjaehrig), damit die HH:MM-Angaben direkt aus der gestellten UTC-Zeit
# ablesbar sind.
# ══════════════════════════════════════════════════════════════════════════

from tests.helpers.nowcast_gate_fixtures import (  # noqa: E402
    CountingFrameSource, clean_uid, fresh_uid, make_trip, reset_radar_cache,
    save_trip, settings_email_only, write_user_tier,
)

_MITTAGS_2017 = "2026-08-11T12:00:00+00:00"


def _aufzeichnender_radar_dienst(frame_source):
    """Echte `RadarNowcastService`-UNTERKLASSE, die nur mitschreibt — kein
    Mock: `get_nowcast()` ruft `super()` auf, die gesamte Entscheidungslogik
    (Cache, Region, `_derive_result`) laeuft unveraendert, und alle uebrigen
    Methoden (`source_label()` u. a.) bleiben die echten.

    Warum nicht der vorhandene `frame_source`-Seam: der bekommt nur
    `(lat, lon)`. Die HOEHE (`elevation_m`, seit #1991 Teil der Abfrage) ist
    dort strukturell unsichtbar — genau sie soll aber mitwandern (#2017 AC-8).

    Klasse innerhalb der Funktion, weil `RadarNowcastService` erst zur
    Laufzeit importiert wird (Import-Reihenfolge dieser Datei).
    """
    from services.radar_service import RadarNowcastService

    class _Aufzeichnend(RadarNowcastService):
        def __init__(self, fs) -> None:
            super().__init__(frame_source=fs)
            self.calls: list[dict] = []

        def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
            self.calls.append({
                "lat": lat, "lon": lon, "elevation_m": elevation_m,
                "priority": priority,
            })
            return super().get_nowcast(
                lat, lon, elevation_m=elevation_m, priority=priority,
            )

    return _Aufzeichnend(frame_source)


def _alarm_lauf_2017(
    uid: str, trip_id: str, *, start: str, ende: str, onset_minutes: int = 8,
):
    """Ein echter `check_radar_alerts()`-Lauf unter gestellter Uhr.

    Liefert `(sent, mails, dienst, frames, trip, now_utc)` — `trip` ist das
    von der Platte GELESENE Objekt (dasselbe, mit dem der Pruefling arbeitet),
    damit die Erwartung nicht aus einer zweiten, evtl. abweichenden Fassung
    gerechnet wird.
    """
    from app.loader import load_all_trips
    from services.trip_alert import TripAlertService

    clean_uid(uid)
    with freeze_time(_MITTAGS_2017):
        now_utc = datetime.now(timezone.utc)
        write_user_tier(uid, "premium")
        save_trip(make_trip(trip_id, arrival_start=start, arrival_end=ende), uid)
        trip = next(t for t in load_all_trips(user_id=uid) if t.id == trip_id)

        reset_radar_cache()
        frames = CountingFrameSource(onset_minutes=onset_minutes)
        dienst = _aufzeichnender_radar_dienst(frames)
        mails: list = []
        svc = TripAlertService(
            settings=settings_email_only(), throttle_hours=2, user_id=uid,
            radar_service=dienst,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        sent = svc.check_radar_alerts()
        return sent, mails, dienst, frames, trip, now_utc


def test_2017_ac8_nowcast_an_interpolierter_position_mit_hoehe():
    """AC-8: `check_radar_alerts()` fragt den Nowcast an der zur Fenstermitte
    interpolierten Position ab — inklusive Hoehe — statt am Segment-Startpunkt.

    Given ein aktives Geh-Segment 11:00–15:00 (Reykjavik, UTC+0), gestellte
    Uhr 12:00 / When der Radar-Alarm-Pfad laeuft / Then traegt der
    `get_nowcast()`-Aufruf die Position zum Zeitpunkt
    `jetzt + RADAR_ONSET_THRESHOLD_MIN // 2` (Zeitanteil 87/240 ≈ 0,3625) und
    deren interpolierte Hoehe, nicht `active.start_point`.

    RED heute: `trip_alert.py` liest `lat/lon/elevation_m` unveraendert aus
    `active.start_point` (Zeile ~1259-1268).
    """
    uid = fresh_uid("2017-ac8")
    try:
        sent, _mails, dienst, _frames, trip, now_utc = _alarm_lauf_2017(
            uid, "trip-2017-ac8", start="11:00", ende="15:00",
        )
        assert dienst.calls, (
            f"Testvoraussetzung: get_nowcast wurde nicht aufgerufen "
            f"(sent={sent}) — ohne Abruf ist nichts zu pruefen"
        )
        active, p, (soll_lat, soll_lon, soll_hoehe) = _erwartete_messposition(
            trip, now_utc, _alarm_offset_minuten(),
        )
        sp = active.start_point

        # Nicht-Trivialitaet in allen drei Groessen.
        assert abs(soll_lat - sp.lat) > 0.01 and abs(soll_lon - sp.lon) > 0.01, (
            f"Testvoraussetzung: interpolierter Punkt ({soll_lat:.5f}, "
            f"{soll_lon:.5f}) und Startpunkt ({sp.lat:.5f}, {sp.lon:.5f}) "
            f"muessen sich messbar unterscheiden, p={p:.4f}"
        )
        assert soll_hoehe is not None and abs(soll_hoehe - sp.elevation_m) > 5.0, (
            f"Testvoraussetzung: interpolierte Hoehe {soll_hoehe} und "
            f"Start-Hoehe {sp.elevation_m} muessen sich unterscheiden"
        )

        ruf = dienst.calls[0]
        assert abs(ruf["lat"] - soll_lat) < 1e-6 and abs(ruf["lon"] - soll_lon) < 1e-6, (
            f"AC-8: get_nowcast an ({ruf['lat']:.5f}, {ruf['lon']:.5f}); "
            f"erwartet der zur Fenstermitte interpolierte Punkt "
            f"({soll_lat:.5f}, {soll_lon:.5f}), Zeitanteil p={p:.4f} zwischen "
            f"({sp.lat:.5f}, {sp.lon:.5f}) und "
            f"({active.end_point.lat:.5f}, {active.end_point.lon:.5f}). "
            f"Der Startpunkt ({sp.lat:.5f}, {sp.lon:.5f}) ist der Ort, den der "
            f"Wanderer zu diesem Zeitpunkt laengst verlassen hat."
        )
        assert ruf["elevation_m"] is not None, (
            "AC-8: die Abfrage muss eine Hoehe tragen (#1991) — sonst wird der "
            "neue Ort mit unbekannter Hoehe abgefragt"
        )
        # Toleranz 0,5 m: die Aufrufstelle darf auf ganze Meter normalisieren
        # (Docstring `position_at_time`), muss es aber nicht.
        assert abs(ruf["elevation_m"] - soll_hoehe) <= 0.5, (
            f"AC-8: get_nowcast mit elevation_m={ruf['elevation_m']}; erwartet "
            f"die MITGEWANDERTE Hoehe {soll_hoehe:.2f} m (interpoliert zwischen "
            f"{sp.elevation_m} m und {active.end_point.elevation_m} m). "
            f"{sp.elevation_m} m waere die Hoehe des verlassenen Startpunkts — "
            f"neuer Ort, alte Hoehe (#2017 Risiko 2)."
        )
    finally:
        clean_uid(uid)


def test_2017_ac10_spaeter_onset_wird_nicht_mehr_pauschal_unterdrueckt():
    """AC-10: der Segment-Ende-Guard aus #2009 ist entfernt — POSITIVNACHWEIS.

    Given ein aktives Segment, das in 20 Minuten endet, und ein Onset in 53
    Minuten (nach ALTEM Massstab also hinter `active.end_time`) / When
    `check_radar_alerts()` laeuft / Then wird der Alarm regulaer gesendet.

    Reine Abwesenheit des alten Tests genuegt ausdruecklich nicht: dieser Fall
    haelt fest, dass der Pfad die Meldung wirklich AUSGIBT, nicht nur, dass
    niemand mehr das Gegenteil prueft. Nach der Umstellung des Messpunkts
    liegt der Onset per Konstruktion dort, wo der Nutzer dann sein wird — der
    Guard verwuerfe damit KORREKTE Alarme (Verfallsbedingung im
    Kommentarblock `trip_alert.py` ueber `_segment_end`).

    RED heute: der Guard unterdrueckt genau diesen Fall (`sent == 0`); der
    Widerspruch zu `test_radar_alert_segment_end_guard.py::
    test_ac6_segment_end_guard_suppresses_late_onset` ist gewollt — jene Datei
    faellt in derselben Aenderung.
    """
    onset_minutes = 53  # erreichbarer Rasterwert, <= RADAR_ONSET_THRESHOLD_MIN
    uid = fresh_uid("2017-ac10")
    try:
        sent, mails, _dienst, _frames, _trip, _now = _alarm_lauf_2017(
            uid, "trip-2017-ac10", start="11:50", ende="12:20",
            onset_minutes=onset_minutes,
        )
        assert sent == 1, (
            f"AC-10: Segment endet in 20 Min, Onset liegt bei {onset_minutes} "
            f"Min — nach Entfernung des Segment-Ende-Guards MUSS der Alarm "
            f"regulaer ausgeloest werden, erhalten sent={sent}. sent=0 heisst: "
            f"der Guard (trip_alert.py, `_onset_dt > _segment_end`) lebt noch."
        )
        assert len(mails) == 1, (
            f"AC-10: erwartet genau EINE zugestellte Alarm-Mail, erhalten "
            f"{len(mails)} — der Alarm muss den Kanal wirklich erreichen, "
            f"nicht nur gezaehlt werden"
        )
    finally:
        clean_uid(uid)


def test_2017_ac12_genau_ein_get_nowcast_aufruf_je_lauf():
    """AC-12 (Budget-Invariante, Alarm-Pfad): genau EIN `get_nowcast()`-Aufruf
    pro Trip und Durchlauf — die Verlegung des Abrufpunkts erhoeht die Zahl
    der Abrufe nicht.

    Gezaehlt wird an ZWEI Naehten: am `get_nowcast()`-Seam (die Zusicherung
    selbst) und am `frame_source`-Seam (dort entstehen die realen Kosten).
    Der Kommentar `trip_alert.py` ("Genau EIN get_nowcast-Call pro Trip an
    Segment-Startpunkt") hielt das bisher nur als Prosa fest und verliert mit
    dieser Aenderung seinen Anker.

    RED heute nicht wegen der ZAHL — die stimmt bereits —, sondern weil der
    eine Aufruf am falschen Ort erfolgt. Beides gehoert in EINE Zusicherung:
    "ein Abruf, und zwar am neuen Messpunkt". Ein iteratives Nachfassen an der
    Onset-Position (Variante 2, in der Spec ausgeschlossen) risse die
    Zaehlung, ein unveraenderter Startpunkt die Ortsangabe.
    """
    uid = fresh_uid("2017-ac12")
    try:
        sent, _mails, dienst, frames, trip, now_utc = _alarm_lauf_2017(
            uid, "trip-2017-ac12", start="11:00", ende="15:00",
        )
        assert len(dienst.calls) == 1, (
            f"AC-12: erwartet genau EIN get_nowcast() je Trip und Lauf, "
            f"erhalten {len(dienst.calls)} (sent={sent}): {dienst.calls!r}"
        )
        assert frames.call_count == 1, (
            f"AC-12: erwartet genau EINEN echten Frame-Abruf (Kostenstelle), "
            f"erhalten {frames.call_count}"
        )
        _active, p, (soll_lat, soll_lon, _h) = _erwartete_messposition(
            trip, now_utc, _alarm_offset_minuten(),
        )
        ruf = dienst.calls[0]
        assert abs(ruf["lat"] - soll_lat) < 1e-6 and abs(ruf["lon"] - soll_lon) < 1e-6, (
            f"AC-12: der EINE Abruf muss am neuen Messpunkt erfolgen — "
            f"({ruf['lat']:.5f}, {ruf['lon']:.5f}) statt erwartet "
            f"({soll_lat:.5f}, {soll_lon:.5f}), p={p:.4f}"
        )
        assert ruf["priority"] == "polling", (
            f"AC-12: der Scheduler-Abruf bleibt drosselbar (`polling`), war "
            f"{ruf['priority']!r} — sonst umgeht die Verlegung das Budget-Gate"
        )
    finally:
        clean_uid(uid)
