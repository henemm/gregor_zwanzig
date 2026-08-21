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


def _sustained_moderate_rain_frames_ac8(lat: float, lon: float) -> list:
    """F008-Fix-Loop (2026-08-21, PO-Entscheid): realistische, DICHTE
    Frame-Serie im 5-Minuten-Raster -- KEIN Zwei-Frame-Konstrukt (daran
    haben wir schon zweimal Zeit verloren). Elf Frames von +5 bis +55 Min,
    durchgehend 3,9 mm/h (knapp UNTER der ehemaligen 4,0-mm/h-Untergrenze) --
    akkumuliert ~3,575 mm, weit ueber jede Ankuendigung von 1,0 mm."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=m), precip_mm_h=3.9)
        for m in range(5, 56, 5)
    ]


def _niesel_frames_ac9(lat: float, lon: float) -> list:
    """F008-Fix-Loop (2026-08-21): vier Frames im 15-Min-Raster (+5/+20/+35/
    +50 Min, 1,2 mm/h) -- akkumuliert exakt 1,1 mm. Erfuellt den Faktor
    gegen eine kleine Ankuendigung (0,5 mm -> Schwelle 1,0 mm), bleibt aber
    unter der absoluten Untergrenze von 2,0 mm."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=m), precip_mm_h=1.2)
        for m in (5, 20, 35, 50)
    ]


def _far_burst_masks_weak_near_rain_frames_f001(lat: float, lon: float) -> list:
    """Schwacher Nahregen (+5/+20/+35/+50 Min, 1,1 mm/h -> window_precip_mm
    ~1,008 mm) PLUS ein Starkregen-Ausbruch weit ausserhalb des 60-Min-
    Vergleichsfensters (+150 Min, 10,0 mm/h, noch im 180-Min-Nowcast-
    Fenster) -- der Ausbruch darf die Ueberholung fuer den Nahregen NICHT
    legitimieren (Adversary-Fund F001, 2026-08-21)."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    frames = [
        RadarFrame(timestamp=now + timedelta(minutes=m), precip_mm_h=1.1)
        for m in (5, 20, 35, 50)
    ]
    frames.append(RadarFrame(timestamp=now + timedelta(minutes=150), precip_mm_h=10.0))
    return frames


def _clean_15min_series_f002(lat: float, lon: float) -> list:
    """Zwei Frames frueh im Vergleichsfenster (+2/+17 Min, 6,0 mm/h) MIT
    Luecke bis zum Fensterende (60 Min) -- nur so wird die Kadenz-
    Deckelung ueberhaupt wirksam (Adversary-Fund F002: ein dichtes Raster
    ohne Fensterrand-Luecke liefert mit/ohne Deckelung zufaellig fast
    dasselbe Ergebnis). Referenzwert fuer den F002-Waechter."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=m), precip_mm_h=6.0)
        for m in (2, 17)
    ]


def _clean_15min_series_with_far_outlier_pair_f002(lat: float, lon: float) -> list:
    """Dieselbe saubere Serie PLUS zwei dicht beieinanderliegende, trockene
    Frames weit ausserhalb des 60-Min-Vergleichsfensters (+170/+171 Min,
    1 Min Abstand -- Providerwiederholung/Sidecar-Artefakt im 180-Min-
    Horizont, Adversary-Fund F002, 2026-08-21)."""
    frames = _clean_15min_series_f002(lat, lon)
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    frames.append(RadarFrame(timestamp=now + timedelta(minutes=170), precip_mm_h=0.0))
    frames.append(RadarFrame(timestamp=now + timedelta(minutes=171), precip_mm_h=0.0))
    return frames


def _two_near_frames_f006(lat: float, lon: float) -> list:
    """Zwei Frames FRUEH im Vergleichsfenster (+2/+17 Min, 6,0 mm/h) --
    Referenzserie fuer den F006-Waechter (Adversary-Runde 2, 2026-08-21):
    ohne weitere Frames deckelt die 15-Min-Obergrenze den letzten Frame auf
    3,0 mm. +2 statt +0 (wie F002): vermeidet, dass der erste Frame durch
    die Millisekunden-Drift zwischen Fixture-Erzeugung und `_derive_result`-
    `now` knapp aus dem Fenster faellt."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=m), precip_mm_h=6.0)
        for m in (2, 17)
    ]


def _two_near_frames_with_far_dry_frames_f006(lat: float, lon: float) -> list:
    """Dieselbe Serie PLUS drei voellig TROCKENE Frames weit ausserhalb des
    60-Min-Vergleichsfensters (+75/+135/+195 Min, 0,0 mm/h, 60-Min-Abstand
    zueinander -- Adversary-Fund F006: eine GLOBALE Kadenz-Schaetzung
    (Median von [15,60,60,60] = 60 Min) haette den letzten Nahregen-Frame
    faelschlich bis auf 60 Min hochgerechnet, obwohl die Stoerframes selbst
    keinen Regen enthalten und ausserhalb jedes bewerteten Fensters
    liegen)."""
    frames = _two_near_frames_f006(lat, lon)
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    for m in (75, 135, 195):
        frames.append(RadarFrame(timestamp=now + timedelta(minutes=m), precip_mm_h=0.0))
    return frames


def _single_isolated_frame_f007(lat: float, lon: float) -> list:
    """Genau EIN Frame im gesamten 180-Min-Horizont (+2 Min, 6,0 mm/h) --
    realistisch nach einer Drosselung/einem Teilausfall (Adversary-Fund
    F007). Es gibt keinen zweiten Zeitstempel, aus dem sich ein Abstand
    ableiten liesse -- die feste `_MAX_FRAME_COVERAGE`-Obergrenze muss
    trotzdem greifen, statt den Frame bis zum Fensterende zu strecken."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    return [RadarFrame(timestamp=now + timedelta(minutes=2), precip_mm_h=6.0)]


def _near_frame_with_sparse_far_frames_f003(lat: float, lon: float) -> list:
    """EIN Frame im Vergleichsfenster (+10 Min, 8,0 mm/h) PLUS drei
    gleichmaessig verteilte, trockene Frames weit ausserhalb (+100/+160/
    +220 Min, je 60 Min Abstand). Eine GLOBALE Kadenz-Schaetzung (egal ob
    Minimum ueber alle Abstaende [90,60,60] -> 60 Min, oder Median -> 60
    Min) wuerde den Nahregen-Frame bis zum Fensterende hochrechnen
    (window_precip_mm ~6,667 mm). Die nachbarschaftsbasierte Regel mit
    fester Obergrenze begrenzt ihn stattdessen auf 15 Min (~2,0 mm) --
    ein Rueckbau auf JEDE Form globaler Kadenz-Schaetzung wuerde hier
    auffliegen."""
    from providers.brightsky import RadarFrame
    now = datetime.now(timezone.utc)
    frames = [RadarFrame(timestamp=now + timedelta(minutes=10), precip_mm_h=8.0)]
    for m in (100, 160, 220):
        frames.append(RadarFrame(timestamp=now + timedelta(minutes=m), precip_mm_h=0.0))
    return frames


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
    from services import trip_alert as trip_alert_mod

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
            "AC-2: HEAVY_RAIN_THRESHOLD_MM_H bleibt als Modul-Konstante bestehen "
            "(weiterhin gelesen von intensity_to_text()), auch ohne Leser mehr in "
            "der Ueberholungsregel (F008-Fix-Loop, 2026-08-21)."
        )
        # Spitzenrate allein (6.0 mm/h) waere frueher die Untergrenze gewesen --
        # seit dem F008-Fix-Loop irrelevant fuer die Regel (beide Bedingungen
        # haengen jetzt an der MENGE). Faktor auf die Menge nicht erfuellt
        # (1.8 < 2 x 1.0 = 2.0) -> die Sperre darf NICHT brechen, unabhaengig
        # von der Spitzenrate.
        overtaking = (
            direct_result.window_precip_mm >= 2.0 * briefing_precip
            and direct_result.window_precip_mm >= trip_alert_mod._OVERTAKE_MIN_ABSOLUTE_MM
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
    from services import trip_alert as trip_alert_mod

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
        # Die korrekte, mengenbasierte Regel (F008-Fix-Loop: beide Bedingungen
        # haengen an der MENGE, nicht mehr an der Rate) darf hier NICHT ausloesen.
        correct_overtaking = (
            direct_result.window_precip_mm >= 2.0 * briefing_precip
            and direct_result.window_precip_mm >= trip_alert_mod._OVERTAKE_MIN_ABSOLUTE_MM
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


# --------------------------------------------------------------------------
# AC-8 (F008-Fix-Loop, PO-Entscheid 2026-08-21): anhaltender maessiger
# Regen loest aus
# --------------------------------------------------------------------------

def test_ac8_sustained_moderate_rain_breaks_suppression():
    """AC-8: Given Briefing kuendigt 1,0 mm an, Nowcast zeigt eine
    realistische, dichte Frame-Serie (5-Min-Raster, +5 bis +55 Min)
    durchgehend 3,9 mm/h -- knapp UNTER der ehemaligen 4,0-mm/h-Untergrenze,
    akkumuliert aber ~3,575 mm (ueber 2 x 1,0 mm = 2,0 mm UND ueber der
    absoluten Untergrenze 2,0 mm).
    When der Pruefzyklus laeuft.
    Then durchbricht der Nowcast die Sperre -- obwohl KEINE einzelne
    Starkregen-Spitze (>=4,0 mm/h) auftritt. Vor dem F008-Fix waere dieser
    Fall unterdrueckt geblieben, weil die alte Ratenschwelle anhaltenden,
    nicht-spitzen Regen strukturell aussperrte.
    """
    from services.radar_service import RadarNowcastService

    uid = f"tdd-2020-ac8-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-ac8-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        briefing_precip = 1.0
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(5): briefing_precip})

        radar_svc = RadarNowcastService(frame_source=_sustained_moderate_rain_frames_ac8)

        direct_result = radar_svc.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
        assert direct_result.max_rate_mm_h < 4.0, (
            "AC-8 Testkonstruktion: KEINE Einzelrate darf die ehemalige "
            f"4,0-mm/h-Untergrenze erreichen (war {direct_result.max_rate_mm_h}), "
            "sonst prueft der Test nicht den Menge-statt-Rate-Fall."
        )
        assert direct_result.window_precip_mm == pytest.approx(3.575, abs=0.05), (
            f"AC-8: akkumulierte Menge muss ~3,575 mm betragen "
            f"(war {direct_result.window_precip_mm})."
        )

        captured: list = []
        svc = _new_service(uid, radar_svc, captured)
        count = svc.check_radar_alerts()

        assert count >= 1, (
            f"AC-8: anhaltender maessiger Regen (~3,575 mm, ueber 2 x "
            f"{briefing_precip} mm = {2*briefing_precip} mm UND ueber der "
            f"absoluten Untergrenze) muss die Sperre durchbrechen, obwohl "
            f"keine Einzelrate die ehemalige Untergrenze erreicht. War count={count}."
        )
        assert len(captured) >= 1, "AC-8: mail_sink muss aufgerufen werden."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# AC-9 (F008-Fix-Loop, PO-Entscheid 2026-08-21): absolute Untergrenze
# gegen Nieselregen
# --------------------------------------------------------------------------

def test_ac9_absolute_floor_blocks_drizzle_even_when_factor_is_met():
    """AC-9: Given Briefing kuendigt 0,5 mm an (Faktor-Schwelle 1,0 mm),
    Nowcast akkumuliert real 1,1 mm -- der Faktor (2 x 0,5 mm = 1,0 mm)
    ist damit erfuellt.
    When der Pruefzyklus laeuft.
    Then bleibt die Sperre bestehen -- KEIN Alarm, weil 1,1 mm die absolute
    Relevanzgrenze von 2,0 mm unterschreitet. Ohne diese Untergrenze wuerde
    Nieselregen alarmieren, sobald die Ankuendigung nur klein genug war.
    """
    from services.radar_service import RadarNowcastService
    from services import trip_alert as trip_alert_mod

    uid = f"tdd-2020-ac9-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-ac9-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        briefing_precip = 0.5
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(5): briefing_precip})

        radar_svc = RadarNowcastService(frame_source=_niesel_frames_ac9)

        direct_result = radar_svc.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
        assert direct_result.window_precip_mm == pytest.approx(1.1, abs=0.02), (
            f"AC-9: akkumulierte Menge muss ~1,1 mm betragen "
            f"(war {direct_result.window_precip_mm})."
        )
        # Die Falle: der reine Faktor-Vergleich (ohne absolute Untergrenze)
        # haette HIER faelschlich ausgeloest.
        factor_only_would_trigger = (
            direct_result.window_precip_mm >= 2.0 * briefing_precip
        )
        assert factor_only_would_trigger is True, (
            "AC-9 Testkonstruktion: der Faktor allein muss hier erfuellt "
            "sein, sonst prueft der Test nicht die absolute Untergrenze."
        )
        assert direct_result.window_precip_mm < trip_alert_mod._OVERTAKE_MIN_ABSOLUTE_MM, (
            "AC-9 Testkonstruktion: die Menge muss UNTER der absoluten "
            f"Untergrenze ({trip_alert_mod._OVERTAKE_MIN_ABSOLUTE_MM} mm) bleiben."
        )

        captured: list = []
        svc = _new_service(uid, radar_svc, captured)
        count = svc.check_radar_alerts()

        assert count == 0, (
            f"AC-9: Menge (~1,1 mm) unterschreitet die absolute Untergrenze "
            f"({trip_alert_mod._OVERTAKE_MIN_ABSOLUTE_MM} mm), obwohl der Faktor-"
            f"Vergleich allein erfuellt waere -- die Sperre muss bestehen bleiben. "
            f"War count={count}."
        )
        assert len(captured) == 0, "AC-9: kein Versand erwartet."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# F001-Waechter (Fix-Loop, Adversary-Fund 2026-08-21): Rate- und Mengen-
# fenster muessen deckungsgleich sein
# --------------------------------------------------------------------------

def test_f001_late_unrelated_burst_must_not_legitimize_overtake_for_weak_near_rain():
    """F001: max_rate_mm_h MUSS aus demselben 60-Min-Vergleichsfenster
    stammen wie window_precip_mm, sonst legitimiert ein spaeter,
    unabhaengiger Starkregen-Ausbruch (+150 Min, ausserhalb des Vergleichs-
    fensters, noch im 180-Min-Nowcast-Fenster) die Ueberholung fuer ganz
    anderen, schwachen Nahregen.

    Given Briefing kuendigt 0,5 mm an (Faktor-Schwelle 1,0 mm), Nahregen der
    ersten Stunde erreicht knapp window_precip_mm ~1,008 mm (Faktor knapp
    erfuellt), Spitzenrate IM Vergleichsfenster bleibt bei 1,1 mm/h (unter
    der 4,0-mm/h-Untergrenze) -- erst ein spaeterer, unabhaengiger Ausbruch
    bei +150 Min erreicht 10,0 mm/h.
    When der Pruefzyklus laeuft.
    Then bleibt die Sperre bestehen -- kein Alarm.
    """
    from services.radar_service import RadarNowcastService
    from services import radar_service as radar_service_mod

    uid = f"tdd-2020-f001-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-f001-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        briefing_precip = 0.5
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(5): briefing_precip})

        radar_svc = RadarNowcastService(frame_source=_far_burst_masks_weak_near_rain_frames_f001)

        direct_result = radar_svc.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
        assert direct_result.window_precip_mm >= 2.0 * briefing_precip, (
            "F001 Testkonstruktion: die Menge im Vergleichsfenster muss die "
            f"Faktor-Untergrenze erfuellen (war {direct_result.window_precip_mm}), "
            "sonst haengt das Ergebnis nur an der Mengen-Bedingung."
        )
        assert direct_result.max_rate_mm_h < radar_service_mod.HEAVY_RAIN_THRESHOLD_MM_H, (
            f"F001: max_rate_mm_h MUSS aus dem 60-Min-Vergleichsfenster stammen "
            f"(dort max 1,1 mm/h), NICHT aus dem 180-Min-Nowcast-Fenster (dort "
            f"10,0 mm/h durch den spaeten Ausbruch). War max_rate_mm_h="
            f"{direct_result.max_rate_mm_h}."
        )

        captured: list = []
        svc = _new_service(uid, radar_svc, captured)
        count = svc.check_radar_alerts()

        assert count == 0, (
            f"F001: ein spaeter, unabhaengiger Starkregen-Ausbruch (+150 Min, "
            f"ausserhalb des Vergleichsfensters) darf die Ueberholung fuer den "
            f"schwachen Nahregen nicht legitimieren. War count={count}."
        )
        assert len(captured) == 0, "F001: kein Versand erwartet."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# F002-Waechter (Fix-Loop, Adversary-Fund 2026-08-21): ein ferner
# Ausreisser-Frame-Paar darf die Kadenz nicht global vergiften
# --------------------------------------------------------------------------

def test_f002_far_outlier_pair_must_not_poison_the_compare_window_amount():
    """F002: zwei dicht beieinanderliegende, aber weit ausserhalb des
    Vergleichsfensters liegende Frames (+170/+171 Min, 0 mm/h) duerfen die
    abgeleitete Kadenz nicht auf 1 Min verfaelschen -- das wuerde die Menge
    im 60-Min-Vergleichsfenster massiv unterzaehlen, obwohl die
    Stoerframes selbst keinen Regen enthalten und ausserhalb des
    bewerteten Fensters liegen.

    Given zwei Frames frueh im Vergleichsfenster mit Luecke bis zum
    Fensterende (window_precip_mm ~3,0 mm, Deckelung aktiv) UND dieselbe
    Serie plus die zwei Stoerframes.
    When get_nowcast() beide Serien direkt verarbeitet.
    Then bleibt window_precip_mm zwischen beiden Faellen praktisch
    unveraendert (Vergleich der beiden Werte gegeneinander, nicht gegen
    eine hart notierte Zahl).
    """
    from services.radar_service import RadarNowcastService

    radar_clean = RadarNowcastService(frame_source=_clean_15min_series_f002)
    radar_poisoned = RadarNowcastService(frame_source=_clean_15min_series_with_far_outlier_pair_f002)

    result_clean = radar_clean.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
    result_poisoned = radar_poisoned.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)

    # Absolutwert-Beleg fuer die Kadenz-Deckelung selbst (Adversary-Fund
    # F002): OHNE Deckelung wuerde der zweite Frame (+17 Min, keine
    # weiteren Frames bis Fensterende) bis zum vollen Fensterende
    # hochgerechnet und window_precip_mm auf ~5,8 mm statt ~3,0 mm springen
    # -- die reine Clean-vs-Poisoned-Gegenprobe unten wuerde das NICHT
    # fangen, weil beide Seiten gleichermassen betroffen waeren.
    assert result_clean.window_precip_mm == pytest.approx(3.0, abs=0.1), (
        f"F002: Mit wirksamer Kadenz-Deckelung muss window_precip_mm ~3,0 mm "
        f"betragen (war {result_clean.window_precip_mm})."
    )

    assert result_poisoned.window_precip_mm == pytest.approx(
        result_clean.window_precip_mm, rel=0.02
    ), (
        f"F002: zwei ferne, dicht beieinanderliegende Stoerframes duerfen die "
        f"Menge im Vergleichsfenster nicht verfaelschen. Sauber="
        f"{result_clean.window_precip_mm}, mit Stoerframes="
        f"{result_poisoned.window_precip_mm}."
    )


# --------------------------------------------------------------------------
# F003-Nachfolger (Fix-Loop 2, Adversary-Runde 2, 2026-08-21): globale
# Kadenz-Schaetzung ersatzlos entfernt (_infer_frame_cadence existiert
# nicht mehr) -- dieser Test bewacht die NEUE Zusicherung: die Deckung
# eines Frames haengt allein von seiner unmittelbaren Nachbarschaft ab,
# nie von einer ueber die volle Frame-Liste gebildeten Kennzahl.
# --------------------------------------------------------------------------

def test_f003_frame_coverage_derives_from_immediate_neighbor_not_global_estimate():
    """F003-Nachfolger: Ein Rueckbau auf eine globale Kadenz-Schaetzung
    (gleich ob Minimum oder Median) wuerde fuer diese Serie ein deutlich
    anderes Ergebnis liefern als die nachbarschaftsbasierte Regel.

    Given ein einzelner Nahregen-Frame (+10 Min, 8,0 mm/h) PLUS drei ferne,
          trockene Frames im 60-Min-Abstand (+100/+160/+220 Min).
    When get_nowcast() die Serie verarbeitet.
    Then bleibt window_precip_mm bei ~2,0 mm (15-Min-Obergrenze ab dem
         eigenen naechsten Nachbarn +100 Min) -- NICHT bei ~6,667 mm, wie es
         eine globale Kadenz (Minimum ODER Median der Abstaende [90,60,60]
         -> 60 Min, angewandt bis zum Fensterende) ergeben wuerde.
    """
    from services.radar_service import RadarNowcastService

    radar = RadarNowcastService(frame_source=_near_frame_with_sparse_far_frames_f003)
    result = radar.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)

    assert result.window_precip_mm == pytest.approx(2.0, abs=0.05), (
        f"F003-Nachfolger: nachbarschaftsbasierte Deckung (15-Min-Obergrenze "
        f"ab dem naechsten Frame bei +100 Min) muss ~2,0 mm ergeben (war "
        f"{result.window_precip_mm})."
    )
    assert result.window_precip_mm != pytest.approx(6.667, abs=0.3), (
        f"F003-Nachfolger: eine GLOBALE Kadenz-Schaetzung (Median/Minimum "
        f"der Abstaende [90,60,60] -> 60 Min) wuerde den einzelnen Nahregen-"
        f"Frame faelschlich bis zum Fensterende hochrechnen (~6,667 mm). War "
        f"{result.window_precip_mm}."
    )


# --------------------------------------------------------------------------
# F004-Waechter (Fix-Loop, Adversary-Fund 2026-08-21): Gleichheitsgrenze
# beider >=-Vergleiche
# --------------------------------------------------------------------------

def test_f004_exact_equality_at_both_thresholds_breaks_the_suppression():
    """F004: beide >=-Vergleiche in der Ueberholungsregel sind an der
    Gleichheitsgrenze ungetestet. Diese Konstruktion trifft
    window_precip_mm EXAKT auf 2 x briefing_precip UND EXAKT auf die
    absolute Untergrenze `_OVERTAKE_MIN_ABSOLUTE_MM` (2,0 mm) -- seit dem
    F008-Fix-Loop (2026-08-21) haengen BEIDE Bedingungen an derselben
    Groesse (window_precip_mm), nicht mehr an Menge UND Rate getrennt.
    Ein einzelner isolierter Frame (+2 Min, 8,0 mm/h), gedeckelt auf die
    15-Minuten-Obergrenze (0,25 h * 8,0 mm/h = 2,0 mm exakt, IEEE754-exakt
    da Potenz-von-2-Bruch), trifft beide Grenzen mit EINER Konstruktion.

    Given window_precip_mm == 2 x briefing_precip == _OVERTAKE_MIN_ABSOLUTE_MM.
    When der Pruefzyklus laeuft.
    Then durchbricht der Nowcast die Sperre (Spec-Wortlaut: `>=`, nicht `>`).
    """
    from providers.brightsky import RadarFrame
    from services.radar_service import RadarNowcastService
    from services import trip_alert as trip_alert_mod

    uid = f"tdd-2020-f004-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-f004-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)

        fixed_now = datetime.now(timezone.utc)

        def _frame_source(lat: float, lon: float) -> list:
            return [RadarFrame(timestamp=fixed_now + timedelta(minutes=2), precip_mm_h=8.0)]

        radar_svc = RadarNowcastService(frame_source=_frame_source, now_fn=lambda: fixed_now)
        direct_result = radar_svc.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
        assert direct_result.window_precip_mm == trip_alert_mod._OVERTAKE_MIN_ABSOLUTE_MM, (
            f"F004 Testkonstruktion: window_precip_mm muss exakt der absoluten "
            f"Untergrenze entsprechen (war {direct_result.window_precip_mm})."
        )
        # x/2.0 gefolgt von 2.0*x ist fuer IEEE754-Floats exakt (keine
        # Rundung) -- briefing_precip so gewaehlt, dass 2 x briefing_precip
        # window_precip_mm BITGENAU trifft, nicht nur ungefaehr.
        briefing_precip = direct_result.window_precip_mm / 2.0
        assert 2.0 * briefing_precip == direct_result.window_precip_mm

        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(2): briefing_precip})

        captured: list = []
        svc = _new_service(uid, radar_svc, captured)
        count = svc.check_radar_alerts()

        assert count >= 1, (
            f"F004: window_precip_mm == 2 x briefing_precip UND window_precip_mm "
            f"== _OVERTAKE_MIN_ABSOLUTE_MM (beide exakt an der Grenze) muessen "
            f"die Sperre nach Spec-Wortlaut (>=) durchbrechen. War count={count}."
        )
        assert len(captured) >= 1, "F004: mail_sink muss aufgerufen werden."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# F006-Waechter (Fix-Loop 2, Adversary-Runde 2, 2026-08-21): ferne,
# TROCKENE Frames duerfen window_precip_mm nicht nach OBEN verfaelschen
# --------------------------------------------------------------------------

def test_f006_far_dry_frames_must_not_inflate_the_window_amount():
    """F006: Frames ohne jeden Niederschlag, weit ausserhalb des 60-Min-
    Vergleichsfensters, duerfen die Menge INNERHALB des Fensters nicht
    veraendern -- weder nach oben noch nach unten. Ein globaler Median
    ueber [15,60,60,60] (=60 Min) haette den letzten Nahregen-Frame bis zu
    dieser (falschen) Kadenz hochgerechnet und window_precip_mm von 3,0 mm
    auf 6,0 mm verdoppelt (Adversary-Reproduktion, Runde 2).

    Given zwei Nahregen-Frame (+0/+15 Min, 6,0 mm/h) UND dieselbe Serie
          PLUS drei ferne, trockene Frames (+75/+135/+195 Min, 0,0 mm/h).
    When get_nowcast() beide Serien direkt verarbeitet.
    Then bleibt window_precip_mm zwischen beiden Faellen IDENTISCH (Vergleich
         gegeneinander, nicht gegen eine hart notierte Zahl) UND explizit
         nicht die verdoppelte Menge.
    """
    from services.radar_service import RadarNowcastService

    radar_clean = RadarNowcastService(frame_source=_two_near_frames_f006)
    radar_poisoned = RadarNowcastService(frame_source=_two_near_frames_with_far_dry_frames_f006)

    result_clean = radar_clean.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)
    result_poisoned = radar_poisoned.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)

    assert result_clean.window_precip_mm == pytest.approx(3.0, abs=0.1), (
        f"F006 Testkonstruktion: window_precip_mm muss ohne die Fernframes "
        f"~3,0 mm betragen (war {result_clean.window_precip_mm})."
    )
    assert result_poisoned.window_precip_mm == pytest.approx(
        result_clean.window_precip_mm, abs=0.1
    ), (
        f"F006: drei ferne, TROCKENE Frames duerfen window_precip_mm nicht "
        f"veraendern. Sauber={result_clean.window_precip_mm}, mit "
        f"Fernframes={result_poisoned.window_precip_mm}."
    )
    assert result_poisoned.window_precip_mm != pytest.approx(6.0, abs=0.2), (
        "F006: die verdoppelte Menge (globale Median-Kadenz von 60 Min) "
        f"darf nicht auftreten (war {result_poisoned.window_precip_mm})."
    )


def test_f006_far_dry_frames_must_not_trigger_a_real_send():
    """F006 End-to-End: dieselbe Serie darf ueber den echten Versandpfad
    (`check_radar_alerts()`) keinen Alarm ausloesen -- die Adversary-
    Reproduktion zeigte genau das (`count=1` statt `count=0`) mit der
    globalen Median-Kadenz.

    Given Briefing kuendigt 2,0 mm an (Faktor-Schwelle 4,0 mm) UND die
          F006-Serie mit den drei fernen, trockenen Frames.
    When check_radar_alerts() laeuft.
    Then bleibt die Sperre bestehen -- kein Alarm (window_precip_mm bleibt
         unter der Faktor-Schwelle).
    """
    from services.radar_service import RadarNowcastService

    uid = f"tdd-2020-f006-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    _ensure_real_user_dir(uid)
    try:
        trip_id = f"tdd-2020-f006-{uuid.uuid4().hex[:6]}"
        _save_trip_direct(_make_active_trip(trip_id), uid)
        briefing_precip = 2.0
        _write_snapshot(uid, trip_id, segment_id=1, hourly_precip={_onset_hour(2): briefing_precip})

        radar_svc = RadarNowcastService(frame_source=_two_near_frames_with_far_dry_frames_f006)

        captured: list = []
        svc = _new_service(uid, radar_svc, captured)
        count = svc.check_radar_alerts()

        assert count == 0, (
            f"F006: drei ferne, trockene Frames duerfen keinen echten Alarm "
            f"auf einer sonst unter der Faktor-Schwelle bleibenden Menge "
            f"ausloesen. War count={count}."
        )
        assert len(captured) == 0, "F006: kein Versand erwartet."
    finally:
        _clean_user(uid)


# --------------------------------------------------------------------------
# F007-Waechter (Fix-Loop 2, Adversary-Runde 2, 2026-08-21): ein einzelner,
# isolierter Frame darf nicht bis zum Fensterende hochgerechnet werden
# --------------------------------------------------------------------------

def test_f007_single_isolated_frame_is_bounded_by_max_frame_coverage():
    """F007: Liefert die Frame-Quelle insgesamt nur EINEN Frame (z. B. nach
    Drosselung/Teilausfall), darf dieser nicht bis zum 60-Min-Fensterende
    hochgerechnet werden (das waere ~5,8 mm -- der in Runde 2 gefundene,
    bislang unbewachte Rueckfall-Bug). Die feste `_MAX_FRAME_COVERAGE`-
    Obergrenze (15 Min) muss stattdessen greifen.

    Given genau ein Frame im gesamten Horizont (+2 Min, 6,0 mm/h).
    When get_nowcast() die Serie verarbeitet.
    Then bleibt window_precip_mm bei ~1,5 mm (15-Min-Deckelung ab +2 Min),
         NICHT bei ~5,8 mm (Hochrechnung bis zum Fensterende).
    """
    from services.radar_service import RadarNowcastService

    radar = RadarNowcastService(frame_source=_single_isolated_frame_f007)
    result = radar.get_nowcast(LAT, LON, elevation_m=ELEVATION_M)

    assert result.window_precip_mm == pytest.approx(1.5, abs=0.05), (
        f"F007: ein isolierter Frame muss auf ~1,5 mm gedeckelt sein "
        f"(15-Min-Obergrenze, war {result.window_precip_mm})."
    )
    assert result.window_precip_mm != pytest.approx(5.8, abs=0.3), (
        f"F007: die Hochrechnung bis zum Fensterende (~5,8 mm) darf nicht "
        f"mehr auftreten (war {result.window_precip_mm})."
    )
