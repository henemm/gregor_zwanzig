"""Waechter #2982 -- die drei Aufrufer des Onset-Bausteins geben ihre
eigenen Eingaben (Zeitzone, Etappenkennung, roher Beginn, km-Spanne)
richtig hinein.

SPEC: docs/specs/modules/fix_2982_onset_event_baustein.md -- AC-1, AC-3,
AC-5 (Fix-Loop nach Adversary F001-F003).

Der Baustein selbst ist in ``test_onset_event_baustein.py`` bewacht; hier
geht es um die Stellen, an denen ein Aufrufer ihn mit FALSCHEN Eingaben
fuettern koennte, ohne dass der Golden-Master es sieht:

- F001 Replay (`validator_render_service._render_nowcast_replay`): die
  Zeitzone kommt aus den Trip-Koordinaten. Das Golden-Replay-Trip hat keine
  Koordinaten (UTC), dort ist die Zone unbeobachtbar -- hier liegt der Trip
  in Berlin und der Beginn nach Mitternacht Ortszeit, waehrend UTC noch am
  Vortag ist.
- F002 Trip-Versand (`TripAlertService.check_radar_alerts`): der echte Lauf
  baut aus Trip + NowcastResult das Versandbuendel `RadarAlertRequest`;
  geprueft werden Etappenkennung, roher `onset_minutes` (None bei laufendem
  Regen) und Zeitzone auf dem Buendel, das wirklich an den Versand geht.
- F003 Debug-Ausloeser (`build_debug_onset_alert_message`): Beginn am
  Folgetag in Berlin traegt Tageswort und Wochentagskuerzel der Ortszeit,
  die km-Spanne ist `0..distance_km`.

Kein Mock-Theater: echte Renderer, echter Endpunkt, echter
`check_radar_alerts()`-Lauf. Der einzige Abgriff in F002 ist ein Mitschnitt
am Versand-Einstieg, der das Buendel festhaelt und UNVERAENDERT an den
echten Versand weiterreicht (der Alarm geht real durch alle Kanaele).
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

BERLIN = ZoneInfo("Europe/Berlin")
# Fr 13.11.2026 22:30 UTC = 23:30 Berlin (Winterzeit). Beginn +45 Min =
# 23:15 UTC (UTC-Tag noch Freitag) = 00:15 Berlin am SAMSTAG.
UHR = "2026-11-13 22:30:00+00:00"
BERLIN_LAT, BERLIN_LON = 52.52, 13.40


# ───────────────────────── F001: Replay in Ortszeit ─────────────────────────


@pytest.fixture
def berlin_replay_trip():
    """Trip MIT Koordinaten in Berlin -- `_alert_tz_for_trip` liefert
    Europe/Berlin (im Gegensatz zum Golden-Replay-Trip ohne Wegpunkte)."""
    user_id = f"test_2982_replay_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-2982-replay-berlin"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Replay Berlin",
        "stages": [{
            "id": "S1", "name": "Tag 1", "date": "2026-11-14",
            "waypoints": [
                {"id": "WP0", "name": "Start", "lat": BERLIN_LAT, "lon": BERLIN_LON,
                 "elevation_m": 40.0, "distance_from_start_km": 0.0},
                {"id": "WP1", "name": "Ziel", "lat": 52.60, "lon": 13.40,
                 "elevation_m": 50.0, "distance_from_start_km": 9.0},
            ],
        }],
    }))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


def _frames(now: datetime, nass_ab: int, nass_bis: int) -> list[dict]:
    frames = [{"timestamp": (now + timedelta(minutes=5)).isoformat(),
               "precip_mm_h": 0.0, "is_convective": False}]
    frames += [{"timestamp": (now + timedelta(minutes=m)).isoformat(),
                "precip_mm_h": 3.0, "is_convective": False}
               for m in range(nass_ab, nass_bis + 1, 5)]
    frames.append({"timestamp": (now + timedelta(minutes=nass_bis + 5)).isoformat(),
                   "precip_mm_h": 0.0, "is_convective": False})
    return frames


@pytest.mark.real_data_root
def test_f001_replay_zeigt_beginn_in_ortszeit_des_trips(berlin_replay_trip):
    """AC-3/AC-5: Replay fuer einen Trip in Berlin, jetzt Fr 22:30 UTC,
    Beginn +45 Min. In Ortszeit ist das Samstag 00:15 -- die SMS traegt
    `@Sa0:15`, Telegram und Mail-Text `morgen 00:15`. In UTC laege der Beginn
    am selben Tag um 23:15 ohne Tagesbezug: genau das darf nicht erscheinen."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import validator

    app = FastAPI()
    app.include_router(validator.router)
    client = TestClient(app)
    user_id, trip_id = berlin_replay_trip
    with freeze_time(UHR):
        now = datetime.now(timezone.utc)
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview", params={"user_id": user_id},
            json={"nowcast_frames": {"source": "radar", "km_from": 0.0, "km_to": 4.0,
                                     "frames": _frames(now, 45, 60)}},
        )
    assert resp.status_code == 200, resp.text[:300]
    data = resp.json()
    assert data.get("onset_detected") is True, data

    sms = data["sms"]
    assert re.search(r"\bR[\d.]*@Sa0:15", sms), (
        f"F001: Beginn in Berliner Ortszeit (Sa 00:15) mit Wochentagskuerzel: {sms!r}"
    )
    assert "23:15" not in sms, f"F001: UTC-Uhrzeit im SMS-Text: {sms!r}"
    for feld in ("telegram", "email_plain"):
        text = data[feld]
        assert "morgen 00:15" in text, (
            f"F001: {feld} nennt den Beginn mit Tageswort in Ortszeit: {text!r}"
        )
        assert "23:15" not in text, f"F001: UTC-Uhrzeit in {feld}: {text!r}"


# ───────────────────────── F002: Trip-Versandbuendel ────────────────────────


@pytest.fixture
def radar_szenario():
    """Ein Nutzer + Trip (Tirol, Europe/Vienna) + Pruefstrecke ueber den
    echten `check_radar_alerts()`-Lauf (Aufbau aus #2480)."""
    from tests.tdd.test_radar_alarm_folgepunkte import _Szenario

    erzeugt: list = []

    def _bau(tag: str):
        s = _Szenario(f"2982-{tag}")
        erzeugt.append(s)
        return s

    yield _bau
    for s in erzeugt:
        s.aufraeumen()


@pytest.fixture
def versand_mitschnitt(monkeypatch):
    """Haelt jedes `RadarAlertRequest` fest, das der Trip-Radar-Pfad an den
    Versand gibt, und reicht es UNVERAENDERT an den echten
    `NotificationService.send_radar_alert` weiter (kein Ersatzverhalten)."""
    from services.notification_service import NotificationService

    echt = NotificationService.send_radar_alert
    gesehen: list = []

    def _mitschnitt(self, trip, *, request, **kw):
        gesehen.append(request)
        return echt(self, trip, request=request, **kw)

    monkeypatch.setattr(NotificationService, "send_radar_alert", _mitschnitt)
    return gesehen


def _erwartete_kennung(s) -> str:
    """Kennung der aktiven Etappe zur gestellten Uhr -- unabhaengig vom
    Pruefling aus der echten Segmentierung des Trips hergeleitet."""
    from output.renderers.alert.segments import normalize_segment_id
    from services.trip_day import trip_local_today
    from services.trip_segments import convert_trip_to_segments
    from tests.tdd.test_radar_alarm_folgepunkte import _UHR

    with freeze_time(_UHR):
        segmente = convert_trip_to_segments(s.trip, trip_local_today(s.trip, _UHR))
    aktiv = [seg for seg in segmente if seg.start_time <= _UHR <= seg.end_time]
    seg = aktiv[0] if aktiv else segmente[0]
    kennung = normalize_segment_id(seg.segment_id)
    assert kennung, "Testvoraussetzung: die aktive Etappe traegt eine Kennung"
    return kennung


def test_f002_kuenftiger_beginn_buendel_traegt_etappe_rohwert_und_ortszone(
    radar_szenario, versand_mitschnitt,
):
    """AC-1: Regen beginnt in 25 Min an Punkt 0. Das Versandbuendel traegt
    die Kennung der aktiven Etappe, `onset_minutes == 25`, die Ortszone
    Europe/Vienna und die Beginnzeit in Ortszeit."""
    from tests.tdd.test_radar_alarm_folgepunkte import _ORTSZEIT, _UHR, nass

    s = radar_szenario("kuenftig")
    lauf = s.lauf({0: nass(25, menge=3.0, ende=55)})
    assert lauf.triggered_count == 1, lauf
    assert len(versand_mitschnitt) == 1, versand_mitschnitt
    req = versand_mitschnitt[0]

    assert req.segment_id == _erwartete_kennung(s), (
        f"F002: Etappenkennung fehlt im Versandbuendel: {req.segment_id!r}"
    )
    assert req.onset_minutes == 25
    assert req.already_running is False
    assert req.tz == _ORTSZEIT, req.tz
    erwartet = (_UHR + timedelta(minutes=25)).astimezone(_ORTSZEIT).strftime("%H:%M")
    assert req.onset_time == erwartet, (req.onset_time, erwartet)


def test_f002_laufender_regen_buendel_traegt_rohes_none(
    radar_szenario, versand_mitschnitt,
):
    """AC-1/AC-4 (Issue #2050 S2b): laeuft der Regen bereits und gibt es
    keinen kuenftigen Beginn, bleibt `onset_minutes` im Buendel ROH `None`
    (nicht 0) -- die Normalisierung macht erst der Renderer-Baustein. Die
    Beginnzeit ist JETZT in Ortszeit, die Etappenkennung reist mit."""
    from tests.tdd.test_radar_alarm_folgepunkte import _ORTSZEIT, _UHR, nass

    s = radar_szenario("laufend")
    lauf = s.lauf({0: nass(None, laufend=True, menge=3.0, ende=30)})
    assert lauf.triggered_count == 1, lauf
    assert len(versand_mitschnitt) == 1, versand_mitschnitt
    req = versand_mitschnitt[0]

    assert req.already_running is True
    assert req.onset_minutes is None, (
        f"F002: roher Beginn bei laufendem Regen muss None bleiben, war "
        f"{req.onset_minutes!r}"
    )
    assert req.segment_id == _erwartete_kennung(s), (
        f"F002: Etappenkennung fehlt im Versandbuendel: {req.segment_id!r}"
    )
    assert req.tz == _ORTSZEIT, req.tz
    assert req.onset_time == _UHR.astimezone(_ORTSZEIT).strftime("%H:%M")


# ───────────────────────── F003: Debug-Ausloeser ────────────────────────────


def _debug_nachricht(km: float):
    from app.loader import load_trip
    from app.models import GPXPoint, TripSegment
    from services.radar_alert_service import build_debug_onset_alert_message
    from services.radar_service import NowcastResult

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        pfad = Path(tmp) / "trip-2982-debug.json"
        pfad.write_text(json.dumps({"id": "trip-2982-debug", "name": "Debug Trip",
                                    "stages": []}))
        trip = load_trip(pfad, user_id="test-2982-debug")
    jetzt = datetime.fromisoformat(UHR)
    active = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=BERLIN_LAT, lon=BERLIN_LON, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=52.60, lon=13.40, distance_from_start_km=km),
        start_time=jetzt, end_time=jetzt + timedelta(hours=2),
        duration_hours=2.0, distance_km=km, ascent_m=0.0, descent_m=0.0,
    )
    nc = NowcastResult(onset_minutes=45, intensity_label="Leichter Regen",
                       source="radar")
    with freeze_time(UHR):
        return build_debug_onset_alert_message(trip, active, nc, "Radar (DWD)")


def test_f003_debug_alarm_beginn_am_folgetag_in_ortszeit():
    """Staging-Debug-Ausloeser: Beginn +45 Min ab Fr 22:30 UTC liegt in
    Berlin am Samstag 00:15. Event und gerenderte Texte tragen Ortszeit,
    Tagesbezug und Wochentagskuerzel; km-Spanne 0..12."""
    from output.renderers.alert.render import render_email, render_sms, render_telegram

    msg = _debug_nachricht(12.0)
    (ev,) = msg.events
    assert (ev.onset_time, ev.onset_day_offset, ev.onset_weekday) == ("00:15", 1, "Sa")
    assert (ev.km_from, ev.km_to) == (0.0, 12.0)
    assert msg.stand_at == "23:30", msg.stand_at

    _html, plain = render_email(msg)
    telegram = render_telegram(msg)
    sms = render_sms(msg)
    sms = sms if isinstance(sms, str) else str(sms)
    for name, text in (("mail", plain), ("telegram", telegram)):
        assert "morgen 00:15" in text, f"{name}: {text!r}"
        assert "23:15" not in text, f"{name}: UTC-Uhrzeit: {text!r}"
        assert "km 0–12" in text, f"{name}: km-Spanne fehlt: {text!r}"
    assert re.search(r"@Sa0:15", sms), f"sms: {sms!r}"
