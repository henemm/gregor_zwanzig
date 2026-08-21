"""TDD RED — Issue #2020 Scheibe 1: Nowcast-Sperre bricht bei Mengen-Ueberholung.

Der Radar-Nowcast-Alarm eines Trips bleibt heute stumm, sobald das Morgen-Briefing fuer
die Onset-Stunde irgendeinen Regenwert >= 0,5 mm genannt hat -- unabhaengig davon, wie
stark die aktuelle Vorhersage diesen Wert inzwischen uebersteigt (`trip_alert.py`,
`check_radar_alerts()`, binaerer Check `_briefing_announced and not result.is_convective`).
Diese Scheibe ersetzt die binaere Sperre durch eine Ueberholungs-Pruefung: Menge
(`window_precip_mm`) gegen Menge (`_briefing_precip`), Spitzenrate (`max_rate_mm_h`) nur
noch als Relevanz-Untergrenze (`HEAVY_RAIN_THRESHOLD_MM_H`).

SPEC: docs/specs/modules/fix_2020_alarm_ausloesung.md

RED-Treiber (Verhaltenstreiber -- heute rot, weil die Faehigkeit fehlt):
- AC-1: Ueberholung (Menge UND Rate erfuellt) muss die Sperre brechen -> Alarm wird
        versendet. Heute blockt die binaere Sperre unabhaengig von den Werten -> count=0,
        erwartet >=1 -> AssertionError.
- AC-3: Monotonie -- ein mindestens gleich starker Nowcast (Menge UND Rate >=) darf nie
        eine schwaechere Meldung ergeben als ein schwaecherer Lauf. Heute blockt die
        binaere Sperre beide Laeufe -> count1=0, erwartet >=1 -> AssertionError.
- AC-6: Sichtbarkeit -- eine bestehen bleibende Sperre muss einen `alert_log`-Eintrag
        (`REASON_NOWCAST`, `gate_reason` benennt die Briefing-Ankuendigung) hinterlassen.
        Heute schreibt dieser Zweig nur `logger.debug` -- `read_undelivered()` liefert
        nichts -> AssertionError.

RED-Treiber (Fehlalarm-Waechter -- heute rot, weil sie die NEUE Oberflaeche direkt
benutzen; ein naiver "kein Alarm"-Test waere hier trivial gruen, weil die binaere
Sperre ohnehin alles blockt, und bewaechte damit nichts):
- AC-2: `window_precip_mm`/`max_rate_mm_h` existieren als Felder auf `NowcastResult`
        noch nicht -> `AttributeError` beim direkten Zugriff.
- AC-4: dieselbe `AttributeError` UND ein expliziter Beleg, dass ein reiner
        Ratenvergleich (ohne Mengen-Pruefung) an dieser Stelle faelschlich ausgeloest
        haette -- die Konstruktion faengt eine kuenftige Regression auf reinen
        Ratenvergleich.

Guard-Tests (Regressionswaechter -- heute bereits gruen):
- AC-5: Konvektiver Sicherheits-Override (#883) bleibt als eigenstaendige Bedingung
        erhalten, auch wenn die neue Ueberholungs-Bedingung NICHT erfuellt ist.
- AC-7: Kein Briefing-Wert (kein Snapshot) -> Verhalten unveraendert, Alarm feuert wie
        zuvor, kein `REASON_NOWCAST`-Eintrag mit `briefing_announced:`-Grund.

Mock-Regel: KEIN Mock()/patch()/MagicMock.
- frame_source (DI-Seam von RadarNowcastService) liefert deterministische Radar-Frames.
- TripAlertService(mail_sink=...) faengt E-Mail-Inhalt ab ohne SMTP.
- Briefing-Snapshot wird direkt als JSON auf Disk geschrieben (Vorbild: #818/#883).
- Unterdrueckungs-Protokoll wird ueber die echte Leseschnittstelle
  `alert_log.read_undelivered()` gelesen, kein Dateiinhalt-Check.

Vorbilder: tests/tdd/test_issue_818_radar_briefing_integration.py,
tests/tdd/test_issue_883_acute_danger_override.py,
tests/tdd/test_nowcast_suppression_logging.py
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date as date_type, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint

from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

# Island: UTC+0 ganzjaehrig (kein DST) -> arrival_calculated-Zeiten = UTC-Zeiten.
LAT, LON = 64.0, -22.0
ELEVATION_M = 100.0


# --------------------------------------------------------------------------
# Frame-Fabriken (DI-Seam, kein Mock) -- eine je Szenario
# --------------------------------------------------------------------------

def _hourlong_rain_frame_source(rate: float, *, convective: bool = False):
    """4 Frames im 15-Min-Raster ueber die volle Vergleichsstunde bei
    konstanter Rate -- Naeherung fuer "durchgehend X mm/h" (AC-1/AC-3)."""
    def _source(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        now = datetime.now(timezone.utc)
        return [
            RadarFrame(timestamp=now + timedelta(minutes=m), precip_mm_h=rate, is_convective=convective)
            for m in (5, 20, 35, 50)
        ]
    return _source


def _spike_then_moderate_frames_ac2(lat: float, lon: float) -> list:
    """Spitze 6.0 mm/h (erste 10 Min, zwei 5-Min-Frames) + abklingender
    Regen (~0.96 mm/h, zehn weitere 5-Min-Frames) im GLEICHMAESSIGEN
    5-Minuten-Raster (RADOLAN-Kadenz) ueber die volle Vergleichsstunde,
    OHNE Stille am Fensterende -> ~1.8 mm gesamt.

    Deckt sich mit dem illustrativen AC-2-Beispiel der Spec (Briefing 1,0 mm,
    Faktor-Schwelle 2,0 mm, real ~1,8 mm -- Faktor nicht erfuellt).

    Issue #2020 (Team-Lead-Review 2026-08-21): die fruehere 2-Frame-Fassung
    (Spitze bei +2 Min, EIN Frame bei +12 Min, danach keine weiteren Frames)
    baute implizit auf der inzwischen abgeschafften Ueber-Extrapolation auf
    -- der letzte Frame wurde bis zum Fensterende (60 Min) hochgerechnet,
    obwohl real ab Minute 12 gar keine Daten mehr vorlagen. Eine echte
    Quelle liefert bei 48 Minuten anhaltendem (wenn auch abklingendem)
    Regen weiterhin Frames im Produktivraster -- diese Fassung bildet das
    nach: durchgehende Kadenz, `_infer_frame_cadence()` leitet daraus 5 Min
    ab, kein Frame wird ueber sein eigenes Intervall hinaus gestreckt.
    """
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    offsets = [2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57]
    rates = [6.0, 6.0] + [0.96] * 10
    return [
        RadarFrame(timestamp=now + timedelta(minutes=m), precip_mm_h=r)
        for m, r in zip(offsets, rates)
    ]


def _burst_then_dry_frames_ac4(lat: float, lon: float) -> list:
    """10-Min-Schauer mit 4.5 mm/h Spitze, danach trocken -> ~0.75 mm gesamt.

    Deckt sich mit dem AC-4-Beispiel der Spec (Briefing 2,0 mm, Faktor-Schwelle
    4,0 mm, real ~0,75 mm -- unterschreitet sogar die Ankuendigung).
    """
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=1), precip_mm_h=4.5),
        RadarFrame(timestamp=now + timedelta(minutes=11), precip_mm_h=0.0),
    ]


def _convective_low_amount_frames_ac5(lat: float, lon: float) -> list:
    """Konvektiv (Gewitter/Hagel), aber Gesamtmenge bleibt UNTER dem
    Ueberholungs-Faktor -- der Alarm darf nur wegen der Konvektion feuern,
    nicht wegen einer (hier absichtlich fehlenden) Mengen-Ueberholung."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0, is_convective=True),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0, is_convective=True),
    ]


def _light_rain_no_overtake_frames_ac6(lat: float, lon: float) -> list:
    """Leichter, nicht-konvektiver Regen ohne jede Ueberholungs-Chance --
    die Sperre muss bestehen bleiben und dabei protokolliert werden."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=1.0),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=1.0),
    ]


def _wet_frames_ac7(lat: float, lon: float) -> list:
    """Einfache Regen-Frames -- kein Briefing-Bezug noetig fuer AC-7."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=4.0),
        RadarFrame(timestamp=now + timedelta(minutes=20), precip_mm_h=8.0),
    ]


def _onset_hour(offset_min: int) -> int:
    """UTC-Stunde des Onsets -- muss zum ersten nassen Frame des jeweiligen
    Szenarios passen, sonst findet `_briefing_precip_for_onset` den
    Stundenwert nicht (Race bei XX:55-XX:59 wie in den Vorbilddateien)."""
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_min)).hour


# --------------------------------------------------------------------------
# Trip-/Snapshot-Setup (direkt auf Disk, umgeht Naismith Compute-on-Save)
# Vorbild: test_issue_883_acute_danger_override.py
# --------------------------------------------------------------------------

def _make_active_trip(trip_id: str) -> Trip:
    """2-Waypoint-Trip mit aktivem Segment (now-1h .. now+2h), UTC+0 (Island)."""
    arr0, arr1 = active_window_offsets(LAT, LON, -60, 120)
    wp0 = Waypoint(
        id="WP0", name="Start", lat=LAT, lon=LON, elevation_m=ELEVATION_M,
        arrival_calculated=arr0,
    )
    wp1 = Waypoint(
        id="WP1", name="Ziel", lat=LAT + 0.05, lon=LON + 0.05, elevation_m=200.0,
        arrival_calculated=arr1,
    )
    stage = Stage(id="S1", name="Tag 1", date=stage_date(LAT, LON), waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name=f"Test {trip_id}", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False,
        alert_on_changes=False,
    )
    return trip


def _save_trip_direct(trip: Trip, user_id: str) -> None:
    """Schreibt Trip-JSON direkt -- Issue #1133: `get_briefings_dir()` folgt
    dem isolierten Daten-Root, denselben Pfad, unter dem
    `app.loader.load_all_trips()` liest."""
    from app.loader import get_briefings_dir
    trips_dir = get_briefings_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)
    stage = trip.stages[0]
    wp_list = []
    for wp in stage.waypoints:
        d: dict = {"id": wp.id, "name": wp.name, "lat": wp.lat, "lon": wp.lon}
        if wp.elevation_m is not None:
            d["elevation_m"] = wp.elevation_m
        if wp.arrival_calculated is not None:
            d["arrival_calculated"] = wp.arrival_calculated
        wp_list.append(d)
    data = {
        "id": trip.id,
        "name": trip.name,
        "stages": [{
            "id": stage.id, "name": stage.name,
            "date": stage.date.isoformat(), "waypoints": wp_list,
        }],
        "report_config": {
            "trip_id": trip.id, "send_email": True, "send_telegram": False,
        },
    }
    (trips_dir / f"{trip.id}.json").write_text(json.dumps(data, indent=2))


def _write_snapshot(user_id: str, trip_id: str, segment_id, hourly_precip: dict) -> None:
    """Minimaler Briefing-Snapshot mit stuendlicher precip_1h_mm (naive UTC-
    Zeitstempel). Issue #1667 S1: Stundenraster ueber ZWEI Tage, damit der
    Test auch in den letzten 5 Minuten des UTC-Tages traegt."""
    from app.loader import get_snapshots_dir

    today = date_type.today()
    snapshots_dir = get_snapshots_dir(user_id)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)

    tagesbeginn = now_utc.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    hourly = []
    for stunde in range(48):
        ts_naive = tagesbeginn + timedelta(hours=stunde)
        hourly.append({
            "ts": ts_naive.strftime("%Y-%m-%dT%H:%M:%S"),
            "precip_1h_mm": float(hourly_precip.get(ts_naive.hour, 0.0)),
        })

    snapshot = {
        "trip_id": trip_id,
        "target_date": today.isoformat(),
        "snapshot_at": now_utc.isoformat(),
        "provider": "openmeteo",
        "segments": [{
            "segment_id": segment_id,
            "start_time": (now_utc - timedelta(hours=1)).isoformat(),
            "end_time": (now_utc + timedelta(hours=2)).isoformat(),
            "start_lat": LAT, "start_lon": LON, "start_elevation_m": ELEVATION_M,
            "start_distance_from_start_km": 0.0,
            "end_lat": LAT + 0.05, "end_lon": LON + 0.05, "end_elevation_m": 200.0,
            "end_distance_from_start_km": 5.0,
            "distance_km": 5.0, "ascent_m": 100.0, "descent_m": 0.0, "duration_hours": 3.0,
            "aggregated": {"t2m_c_max": 20.0, "t2m_c_min": 15.0},
            "hourly": hourly,
        }],
    }
    filepath = snapshots_dir / f"{trip_id}_{today.isoformat()}.json"
    filepath.write_text(json.dumps(snapshot, indent=2))


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


def _ensure_real_user_dir(uid: str) -> None:
    """Issue #1133: trip_alert.py/alert_log.py schreiben weiterhin ueber die
    relative "data/users/..."-Konstruktion und setzen die Existenz des
    Nutzerverzeichnisses voraus."""
    (DATA_ROOT / uid).mkdir(parents=True, exist_ok=True)


def _dummy_settings() -> Settings:
    """Egress-Guard (#1697): deterministisch sendefaehig, ohne echtes SMTP zu
    beruehren -- `mail_sink` faengt jeden Versuch ab."""
    return Settings(
        smtp_host="test.invalid", smtp_user="u", smtp_pass="p",
        mail_to="x@example.com",
    )


def _new_service(uid: str, radar_svc, captured: list):
    from services.trip_alert import TripAlertService
    return TripAlertService(
        throttle_hours=2, user_id=uid, radar_service=radar_svc,
        settings=_dummy_settings(),
        mail_sink=lambda subject, body: captured.append((subject, body)),
    )


# --------------------------------------------------------------------------
# AC-1 (Verhaltenstreiber): Ueberholung durchbricht die Sperre
# --------------------------------------------------------------------------

def test_ac1_overtaking_amount_and_rate_breaks_the_suppression():
    """AC-1: Given Briefing kuendigt 1,0 mm fuer die Onset-Stunde an UND der
    aktuelle Nowcast sagt durchgehend 12 mm/h fuer die kommende Stunde voraus
    (Menge weit ueber dem 2x-Faktor, Rate weit ueber der 4,0-mm/h-Untergrenze).
    When check_radar_alerts() laeuft.
    Then durchbricht der Nowcast die Sperre und ein Alarm wird TATSAECHLICH
    versendet (nicht nur eine Boolesche Zwischenvariable).

    RED: die binaere Sperre blockt heute jeden angekuendigten, nicht-
    konvektiven Fall unabhaengig von der Ueberholungs-Menge -> count=0.
    """
    from services.radar_service import RadarNowcastService

    uid = f"tdd-2020-ac1-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-ac1-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        briefing_precip = 1.0
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(5): briefing_precip})

        radar_svc = RadarNowcastService(frame_source=_hourlong_rain_frame_source(12.0))
        captured: list = []
        svc = _new_service(uid, radar_svc, captured)

        count = svc.check_radar_alerts()

        assert count >= 1, (
            f"AC-1: Briefing kuendigte {briefing_precip} mm an, der Nowcast sagt "
            f"durchgehend 12 mm/h voraus (weit ueber Faktor 2x und Untergrenze "
            f"4,0 mm/h). Der Alarm MUSS trotz Ankuendigung feuern. War count={count}. "
            f"RED: Ueberholungs-Pruefung noch nicht implementiert."
        )
        assert len(captured) >= 1, "AC-1: mail_sink muss aufgerufen werden (Ueberholungs-Alarm)."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-2 (Fehlalarm-Waechter): Menge entscheidet, nicht allein die Rate
# --------------------------------------------------------------------------

def test_ac2_high_peak_rate_without_enough_amount_keeps_suppression():
    """AC-2: Given Briefing kuendigt 1,0 mm an, der Nowcast erreicht kurzzeitig
    6,0 mm/h (ueber der 4,0-mm/h-Untergrenze), akkumuliert aber im gesamten
    Stundenfenster nur ~1,8 mm (unter 2x1,0 mm = 2,0 mm).
    When derselbe Pruefzyklus laeuft.
    Then bleibt die Sperre bestehen -- die Untergrenze allein reicht nicht.

    RED: `window_precip_mm`/`max_rate_mm_h` existieren auf `NowcastResult`
    noch nicht -> AttributeError beim direkten Zugriff. Ein naiver
    "assert count==0"-Test waere heute TRIVIAL gruen (die binaere Sperre
    blockt ohnehin alles) und bewaechte nichts -- deshalb der direkte
    Feld-Nachweis zuerst.
    """
    from services.radar_service import RadarNowcastService
    from services import radar_service as radar_service_mod

    uid = f"tdd-2020-ac2-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-ac2-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        briefing_precip = 1.0
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(2): briefing_precip})

        radar_svc = RadarNowcastService(frame_source=_spike_then_moderate_frames_ac2)

        direct_result = radar_svc.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
        assert direct_result.max_rate_mm_h == pytest.approx(6.0, abs=0.01), (
            f"AC-2: Spitzenrate muss 6.0 mm/h betragen "
            f"(war {getattr(direct_result, 'max_rate_mm_h', 'FEHLT')})."
        )
        assert direct_result.window_precip_mm == pytest.approx(1.8, abs=0.05), (
            f"AC-2: akkumulierte Menge im 60-Min-Vergleichsfenster muss ~1.8 mm "
            f"betragen (war {getattr(direct_result, 'window_precip_mm', 'FEHLT')})."
        )
        assert radar_service_mod.HEAVY_RAIN_THRESHOLD_MM_H == pytest.approx(4.0), (
            "AC-2: HEAVY_RAIN_THRESHOLD_MM_H muss als Modul-Konstante existieren "
            "und denselben Wert tragen wie intensity_to_text()."
        )
        # Untergrenze allein erfuellt (6.0 >= 4.0), Faktor auf die MENGE nicht
        # (1.8 < 2 x 1.0 = 2.0) -> die Sperre darf NICHT brechen.
        overtaking = (
            direct_result.window_precip_mm >= 2.0 * briefing_precip
            and direct_result.max_rate_mm_h >= radar_service_mod.HEAVY_RAIN_THRESHOLD_MM_H
        )
        assert overtaking is False, (
            "AC-2 Testkonstruktion: die Menge muss den Faktor UNTERSCHREITEN, "
            "obwohl die Rate die Untergrenze erfuellt -- sonst prueft der Test nichts."
        )

        captured: list = []
        svc = _new_service(uid, radar_svc, captured)
        count = svc.check_radar_alerts()

        assert count == 0, (
            f"AC-2: Menge (~1.8 mm) bleibt unter dem Faktor (2 x {briefing_precip} mm "
            f"= {2*briefing_precip} mm) -- die Sperre muss bestehen bleiben, obwohl die "
            f"Spitzenrate allein die Untergrenze erfuellt. War count={count}."
        )
        assert len(captured) == 0, "AC-2: kein Versand erwartet."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-3 (Verhaltenstreiber): Monotonie
# --------------------------------------------------------------------------

def test_ac3_stronger_or_equal_nowcast_never_alarms_less_than_a_weaker_one():
    """AC-3: Given ein Lauf 1 durchbricht die Sperre bereits (Menge UND Rate
    erfuellen die Ueberholung) fuer einen festen angekuendigten Wert.
    When ein zweiter, unabhaengiger Lauf mit demselben angekuendigten Wert
    eine window_precip_mm >= Lauf 1 UND max_rate_mm_h >= Lauf 1 liefert.
    Then durchbricht auch Lauf 2 die Sperre -- der TATSAECHLICHE Alarm-
    Versand, nicht nur eine Boolesche Zwischenvariable.

    RED: die binaere Sperre blockt heute BEIDE Laeufe unabhaengig von den
    Werten -> count1=0, erwartet >=1.
    """
    from services.radar_service import RadarNowcastService

    briefing_precip = 1.0

    # -- Lauf 1: schwaecherer, aber bereits ueberholender Nowcast --
    uid1 = f"tdd-2020-ac3a-{uuid.uuid4().hex[:6]}"
    _clean_user(uid1)
    _ensure_real_user_dir(uid1)
    # -- Lauf 2: mindestens gleich starker Nowcast, unabhaengiger Trip --
    uid2 = f"tdd-2020-ac3b-{uuid.uuid4().hex[:6]}"
    _clean_user(uid2)
    _ensure_real_user_dir(uid2)
    try:
        trip_id1 = f"tdd-2020-ac3a-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id1), uid1)
        _write_snapshot(uid1, trip_id1, segment_id=1, hourly_precip={_onset_hour(5): briefing_precip})

        trip_id2 = f"tdd-2020-ac3b-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id2), uid2)
        _write_snapshot(uid2, trip_id2, segment_id=1, hourly_precip={_onset_hour(5): briefing_precip})

        radar1 = RadarNowcastService(frame_source=_hourlong_rain_frame_source(12.0))
        radar2 = RadarNowcastService(frame_source=_hourlong_rain_frame_source(15.0))

        result1 = radar1.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
        result2 = radar2.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)

        assert result2.window_precip_mm >= result1.window_precip_mm, (
            "AC-3 Testkonstruktion: Lauf 2 muss mindestens dieselbe akkumulierte "
            f"Menge liefern wie Lauf 1 (Lauf1={getattr(result1, 'window_precip_mm', 'FEHLT')}, "
            f"Lauf2={getattr(result2, 'window_precip_mm', 'FEHLT')})."
        )
        assert result2.max_rate_mm_h >= result1.max_rate_mm_h, (
            "AC-3 Testkonstruktion: Lauf 2 muss mindestens dieselbe Spitzenrate "
            f"liefern wie Lauf 1 (Lauf1={getattr(result1, 'max_rate_mm_h', 'FEHLT')}, "
            f"Lauf2={getattr(result2, 'max_rate_mm_h', 'FEHLT')})."
        )

        captured1: list = []
        svc1 = _new_service(uid1, radar1, captured1)
        count1 = svc1.check_radar_alerts()
        assert count1 >= 1, (
            f"AC-3: Lauf 1 (12 mm/h durchgehend) muss die Sperre bereits durchbrechen "
            f"(war count1={count1}). RED: Ueberholungs-Pruefung fehlt noch."
        )

        captured2: list = []
        svc2 = _new_service(uid2, radar2, captured2)
        count2 = svc2.check_radar_alerts()
        assert count2 >= 1, (
            f"AC-3: Lauf 2 (>= Lauf 1 in Menge UND Rate) darf NIE schwaecher "
            f"ausfallen als Lauf 1 (war count2={count2}, count1={count1})."
        )
    finally:
        _clean_user(uid1)
        _clean_user(uid2)


# --------------------------------------------------------------------------
# AC-4 (Fehlalarm-Waechter): Spitzenrate allein loest NIE aus
# --------------------------------------------------------------------------

def test_ac4_high_peak_rate_alone_never_triggers_the_overtake():
    """AC-4: Given Briefing kuendigt 2,0 mm an, der Nowcast zeigt einen
    10-minuetigen Schauer mit 4,5 mm/h Spitze (ueber der Untergrenze), danach
    bleibt das Stundenfenster trocken -> real nur ~0,75 mm (unter 2x2,0=4,0 mm
    UND unter der Ankuendigung selbst).
    When der Pruefzyklus laeuft.
    Then bleibt die Sperre bestehen -- kein Alarm, OBWOHL ein reiner
    Ratenvergleich (ohne Mengen-Pruefung) hier faelschlich ausgeloest haette.
    Dieser Fall MUSS rot werden, falls die Implementierung je wieder auf
    einen reinen Ratenvergleich zurueckgebaut wird.

    RED: `window_precip_mm`/`max_rate_mm_h` existieren noch nicht ->
    AttributeError.
    """
    from services.radar_service import RadarNowcastService
    from services import radar_service as radar_service_mod

    uid = f"tdd-2020-ac4-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-ac4-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        briefing_precip = 2.0
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(1): briefing_precip})

        radar_svc = RadarNowcastService(frame_source=_burst_then_dry_frames_ac4)

        direct_result = radar_svc.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
        assert direct_result.max_rate_mm_h == pytest.approx(4.5, abs=0.01), (
            f"AC-4: Spitzenrate muss 4.5 mm/h betragen "
            f"(war {getattr(direct_result, 'max_rate_mm_h', 'FEHLT')})."
        )
        assert direct_result.window_precip_mm == pytest.approx(0.75, abs=0.05), (
            f"AC-4: akkumulierte Menge im 60-Min-Vergleichsfenster muss ~0.75 mm "
            f"betragen (war {getattr(direct_result, 'window_precip_mm', 'FEHLT')})."
        )

        # Die Falle: ein reiner Ratenvergleich (Faktor 2 gegen die Ankuendigung,
        # ohne Mengen-Pruefung) haette HIER faelschlich ausgeloest.
        naive_rate_only_would_trigger = (
            direct_result.max_rate_mm_h >= 2.0 * briefing_precip
            and direct_result.max_rate_mm_h >= radar_service_mod.HEAVY_RAIN_THRESHOLD_MM_H
        )
        assert naive_rate_only_would_trigger is True, (
            "AC-4 Testkonstruktion: dieser Fall muss ausgerechnet den reinen "
            "Ratenvergleich in die Irre fuehren, sonst prueft der Test die "
            "Regression nicht, vor der die Spec warnt."
        )
        # Die korrekte, mengenbasierte Regel darf hier NICHT ausloesen.
        correct_overtaking = (
            direct_result.window_precip_mm >= 2.0 * briefing_precip
            and direct_result.max_rate_mm_h >= radar_service_mod.HEAVY_RAIN_THRESHOLD_MM_H
        )
        assert correct_overtaking is False, (
            "AC-4 Testkonstruktion: die mengenbasierte Regel darf hier nicht "
            "ausloesen -- sonst waere die Konstruktion kein Fehlalarm-Fall."
        )

        captured: list = []
        svc = _new_service(uid, radar_svc, captured)
        count = svc.check_radar_alerts()

        assert count == 0, (
            f"AC-4: Menge (~0.75 mm) bleibt weit unter dem Faktor (2 x {briefing_precip} "
            f"mm = {2*briefing_precip} mm) -- die Sperre muss bestehen bleiben, obwohl "
            f"die Spitzenrate allein ausgeloest haette. War count={count}."
        )
        assert len(captured) == 0, "AC-4: kein Versand erwartet."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-5 (Regressionswaechter): Konvektiv-Override bleibt unangetastet
# --------------------------------------------------------------------------

def test_ac5_convective_override_still_breaks_suppression_without_overtake():
    """AC-5: GUARD (heute bereits gruen). Given `is_convective=True` UND die
    Ueberholungs-Bedingung ist NICHT erfuellt (Menge bleibt unter dem Faktor).
    When der Pruefzyklus laeuft.
    Then durchbricht der Alarm die Sperre trotzdem -- die bestehende
    konvektive Bedingung (#883) gilt unveraendert als EIGENSTAENDIGE
    Bedingung neben der neuen Ueberholungs-Pruefung.
    """
    from services.radar_service import RadarNowcastService

    uid = f"tdd-2020-ac5-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-ac5-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        briefing_precip = 5.0
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(5): briefing_precip})

        radar_svc = RadarNowcastService(frame_source=_convective_low_amount_frames_ac5)

        direct_result = radar_svc.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
        assert direct_result.is_convective is True, (
            "AC-5 Testkonstruktion: der Nowcast muss konvektiv sein."
        )

        captured: list = []
        svc = _new_service(uid, radar_svc, captured)
        count = svc.check_radar_alerts()

        assert count >= 1, (
            f"AC-5 GUARD: konvektive Gefahr muss die Sperre unabhaengig von der "
            f"Ueberholungs-Menge durchbrechen (war count={count})."
        )
        assert len(captured) >= 1, "AC-5: mail_sink muss aufgerufen werden (Konvektiv-Override)."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-6 (Verhaltenstreiber): Sichtbarkeit der bestehenden Sperre im Protokoll
# --------------------------------------------------------------------------

def test_ac6_remaining_suppression_creates_alert_log_entry():
    """AC-6: Given die Sperre bleibt bestehen (weder Ueberholung noch
    Konvektion).
    When check_radar_alerts() durchlaeuft.
    Then entsteht ein `alert_log`-Eintrag ueber `append_suppressed_entry()`
    mit `reason=REASON_NOWCAST` und einem `gate_reason`, der die Briefing-
    Ankuendigung als Ursache benennt -- gelesen ueber die echte
    Protokoll-Leseschnittstelle `read_undelivered()`, kein Dateiinhalt-Check.

    RED: dieser Unterdrueckungs-Zweig schreibt heute nur `logger.debug`,
    keinen Protokoll-Eintrag -> `read_undelivered()` liefert nichts.
    """
    from services import alert_log
    from services.radar_service import RadarNowcastService

    uid = f"tdd-2020-ac6-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-ac6-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        briefing_precip = 5.0
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(5): briefing_precip})

        radar_svc = RadarNowcastService(frame_source=_light_rain_no_overtake_frames_ac6)
        captured: list = []
        svc = _new_service(uid, radar_svc, captured)

        count = svc.check_radar_alerts()
        assert count == 0, (
            f"AC-6 Vorbedingung: leichter Regen ohne Ueberholung darf nicht feuern "
            f"(war count={count})."
        )

        incidents = alert_log.read_undelivered(uid, entity_id=trip_id, entity_type="trip")
        nowcast_incidents = [i for i in incidents if i.trigger == alert_log.REASON_NOWCAST]
        assert nowcast_incidents, (
            f"AC-6: erwarte mindestens einen `not_delivered`-Eintrag mit "
            f"reason={alert_log.REASON_NOWCAST!r} fuer Trip {trip_id!r}. "
            f"Gefunden: {incidents!r}. RED: dieser Unterdrueckungs-Zweig "
            f"protokolliert heute nur per logger.debug."
        )
        gate_reasons = {r for i in nowcast_incidents for r in i.reasons}
        assert any(r.startswith("briefing_announced:") for r in gate_reasons), (
            f"AC-6: der gate_reason muss die Briefing-Ankuendigung als Ursache "
            f"benennen (Praefix 'briefing_announced:'). Gefunden: {gate_reasons!r}."
        )
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-7 (Regressionswaechter): kein Briefing-Wert -> Verhalten unveraendert
# --------------------------------------------------------------------------

def test_ac7_missing_briefing_value_leaves_behavior_unchanged():
    """AC-7: GUARD (heute bereits gruen). Given `_briefing_precip_for_onset()`
    liefert None (kein Snapshot).
    When der Pruefzyklus laeuft.
    Then bleibt das Verhalten unveraendert -- `_briefing_announced` ist von
    vornherein False, die Ueberholungs-Pruefung wird gar nicht erst
    ausgewertet, der Alarm feuert wie vor dieser Aenderung, und es entsteht
    KEIN `briefing_announced:`-Protokoll-Eintrag fuer diese Ursache.
    """
    from services import alert_log
    from services.radar_service import RadarNowcastService

    uid = f"tdd-2020-ac7-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-ac7-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        # Kein _write_snapshot -> WeatherSnapshotService.load_dated liefert None.

        radar_svc = RadarNowcastService(frame_source=_wet_frames_ac7)
        captured: list = []
        svc = _new_service(uid, radar_svc, captured)

        count = svc.check_radar_alerts()

        assert count >= 1, (
            f"AC-7 GUARD: ohne Briefing-Schnappschuss muss der Alarm wie zuvor "
            f"feuern (Fallback: kein Snapshot = nicht unterdruecken). War count={count}."
        )
        assert len(captured) >= 1, "AC-7: mail_sink muss aufgerufen werden."

        incidents = alert_log.read_undelivered(uid, entity_id=trip_id, entity_type="trip")
        gate_reasons = {r for i in incidents for r in i.reasons}
        assert not any(r.startswith("briefing_announced:") for r in gate_reasons), (
            f"AC-7: ohne Briefing-Wert darf kein 'briefing_announced:'-Grund "
            f"protokolliert werden. Gefunden: {gate_reasons!r}."
        )
    finally:
        _clean_user(uid)
