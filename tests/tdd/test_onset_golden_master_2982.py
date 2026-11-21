"""Golden-Master #2982 -- die Alarmtexte des Alarm-Beginns (OnsetEvent) bleiben
beim Umbau auf EINEN Baustein byte-identisch.

SPEC: docs/specs/modules/fix_2982_onset_event_baustein.md -- AC-1, AC-2, AC-3, AC-4.

Eingefroren wurde der Stand VOR dem Umbau (Commit 3fc72959a) in
``tests/golden/onset_2982/golden.json``: je Fall das gebaute ``OnsetEvent``
(alle Felder) und die Texte aller vier Kanaele -- Betreff, E-Mail HTML und
Klartext, Telegram, Kurznachricht (SMS; Premium-SMS und Telegram-Kurzstil
senden denselben Kurztext, ``notification_service._dispatch_alert_message``).

Faelle (je laufend und kuenftig):
- Ortsvergleich-Buendel mit zwei Orten in verschiedenen Zeitzonen
  (Europe/Berlin, Europe/Lisbon), Beginn nach Mitternacht Ortszeit, und der
  Ein-Ort-Fall (AC-2, AC-4: Reihenfolge laufend zuerst).
- Replay (echter API-Endpunkt ``alert-preview`` mit ``nowcast_frames``) und
  Vorschau (echter Endpunkt mit ``onset``-Payload) (AC-3).
- Trip-Versand: echter ``NotificationService.send_radar_alert`` mit voll
  belegtem ``RadarAlertRequest`` (AC-1). Erfasst wird die an den Versand
  uebergebene ``AlertMessage`` ueber eine Unterklasse, die nur den
  Transportschritt ersetzt (Naht wie ``mail_sink``) -- gerendert wird danach
  mit den echten Renderern.

Diese Tests sind VOR dem Umbau gruen (sie frieren ihn ein) und muessen
NACH dem Umbau unveraendert gruen sein. Die Golden-Datei wird nie
nachgezogen, um einen roten Fall gruen zu machen.

Einzige bewusste Nachfuehrung: #3254 (freigegebene Spec
``fix_3254_regenende_deckungsgrenze.md``) -- in den beiden Replay-Faellen
verschiebt sich NUR die Ende-Uhrzeit um 5 Min auf die Deckungsgrenze des
letzten nassen Frames (00:40 -> 00:45, 23:10 -> 23:15); alle anderen Zeichen
unveraendert.

Kein Mock: echte Renderer, echte Bauwege, gestellte Uhr (freezegun).
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

pytestmark = pytest.mark.real_data_root

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "golden" / "onset_2982" / "golden.json"

# Fr 13.11.2026 22:30 UTC = 23:30 Berlin = 22:30 Lissabon.
UHR = "2026-11-13 22:30:00+00:00"
BERLIN = SimpleNamespace(lat=52.52, lon=13.40, timezone="Europe/Berlin")
LISSABON = SimpleNamespace(lat=38.72, lon=-9.14, timezone="Europe/Lisbon")


@pytest.fixture(autouse=True)
def _feste_herkunft(monkeypatch):
    """Herkunfts-Fusszeile auf festen Platzhalter (Muster
    test_multi_location_onset_alert.py), sonst bricht das Golden je Commit."""
    from src.output.renderers.email import helpers as helpers_mod

    monkeypatch.setattr(helpers_mod, "_DEPLOYED_COMMIT", "gitrev0")


# ───────────────────────────── Hilfen ─────────────────────────────────────


def _jsonable(value):
    if dataclasses.is_dataclass(value):
        return {f.name: _jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def texte(msg) -> dict:
    from output.renderers.alert.render import (
        render_email, render_sms, render_subject, render_telegram,
    )

    html, plain = render_email(msg)
    return {
        "events": _jsonable(msg.events),
        "subject": render_subject(msg),
        "email_html": html,
        "email_plain": plain,
        "telegram": render_telegram(msg),
        "sms": render_sms(msg, limit=140),
    }


def _nc(**kw):
    from services.radar_service import NowcastResult

    basis = dict(onset_minutes=45, intensity_label="Mäßiger Regen", source="radar")
    basis.update(kw)
    return NowcastResult(**basis)


def _nc_kuenftig():
    return _nc(
        onset_minutes=45, onset_precip_mm=2.4, event_end_minutes=95,
        source_reach_minutes=120,
    )


def _nc_laufend():
    return _nc(
        onset_minutes=None, already_running=True, intensity_label="Leichter Regen",
        onset_precip_mm=0.8, event_end_minutes=30, convective_checked=False,
    )


# ───────────────────────── Ortsvergleich ──────────────────────────────────


def fall_vergleich_zwei_orte() -> dict:
    from app.ampel import resolve_ampel
    from output.renderers.alert.project import to_multi_location_onset_alert_message

    with freeze_time(UHR):
        msg = to_multi_location_onset_alert_message(
            [("Hütte Berlin", BERLIN, _nc_kuenftig()),
             ("Lissabon", LISSABON, _nc_laufend())],
            tz=ZoneInfo("UTC"), stand_at="22:30", cooldown_display="2 Stunden",
            ampel=resolve_ampel(None),
        )
    return texte(msg)


def fall_vergleich_ein_ort_kuenftig() -> dict:
    from app.ampel import resolve_ampel
    from output.renderers.alert.project import to_multi_location_onset_alert_message

    with freeze_time(UHR):
        msg = to_multi_location_onset_alert_message(
            [("Hütte Berlin", BERLIN, _nc_kuenftig())],
            tz=ZoneInfo("UTC"), stand_at="23:30", ampel=resolve_ampel(None),
        )
    return texte(msg)


def fall_vergleich_ein_ort_laufend() -> dict:
    from app.ampel import resolve_ampel
    from output.renderers.alert.project import to_multi_location_onset_alert_message

    with freeze_time(UHR):
        msg = to_multi_location_onset_alert_message(
            [("Lissabon", LISSABON, _nc_laufend())],
            tz=ZoneInfo("UTC"), stand_at="22:30", ampel=resolve_ampel(None),
        )
    return texte(msg)


# ───────────────────────── Replay und Vorschau ────────────────────────────


def _api_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import validator

    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


def _mit_trip(fn):
    user_id = f"test_2982_gm_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-2982-gm"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Golden-Trip", "stages": [],
    }))
    try:
        return fn(_api_client(), user_id, trip_id)
    finally:
        shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


def _preview_texte(data: dict) -> dict:
    return {k: data.get(k) for k in ("subject", "email_html", "email_plain", "telegram", "sms")}


def _replay(nass_ab: int, nass_bis: int) -> dict:
    def run(client, user_id, trip_id):
        with freeze_time(UHR):
            now = datetime.now(timezone.utc)
            frames = [{"timestamp": (now + timedelta(minutes=m)).isoformat(),
                       "precip_mm_h": 3.0, "is_convective": False}
                      for m in range(nass_ab, nass_bis + 1, 5)]
            frames.append({"timestamp": (now + timedelta(minutes=nass_bis + 5)).isoformat(),
                           "precip_mm_h": 0.0, "is_convective": False})
            if nass_ab > 0:
                frames.insert(0, {"timestamp": (now + timedelta(minutes=5)).isoformat(),
                                  "precip_mm_h": 0.0, "is_convective": False})
            resp = client.post(
                f"/api/trips/{trip_id}/alert-preview", params={"user_id": user_id},
                json={"nowcast_frames": {"source": "radar", "km_from": 2.0, "km_to": 6.0,
                                         "segment_id": "2", "frames": frames}},
            )
        assert resp.status_code == 200, resp.text[:300]
        data = resp.json()
        assert data.get("onset_detected") is True, data
        return _preview_texte(data)

    return _mit_trip(run)


def fall_replay_kuenftig() -> dict:
    # Beginn +95 Min = 00:05 UTC Samstag (Tagesbezug), Ende danach.
    return _replay(95, 130)


def fall_replay_laufend() -> dict:
    return _replay(0, 40)


def fall_vorschau_payload() -> dict:
    onset = {
        "onset_minutes": 40, "onset_time": "00:10", "km_from": 3.0, "km_to": 9.5,
        "is_convective": True, "intensity_label": "Starker Regen",
        "source_label": "Radar (DWD)", "cooldown_display": "2 Stunden",
        "segment_id": "3", "onset_precip_mm": 6.5, "onset_day_offset": 1,
        "onset_weekday": "Sa", "event_end_time": "01:20", "event_end_day_offset": 1,
        "event_end_weekday": "Sa", "event_ongoing_beyond_horizon": False,
        "source_reach_time": "01:30", "source_reach_day_offset": 1,
        "location_sharpness_limit_time": "00:00", "location_sharpness_limit_day_offset": 1,
        "km_measured": True,
        "rain_zones": [{"km_from": 3.0, "km_to": 5.0, "onset_minutes": 40,
                        "event_end_minutes": 110},
                       {"km_from": 7.0, "km_to": 9.5, "onset_minutes": 55}],
        "convective_checked": False,
    }

    def run(client, user_id, trip_id):
        with freeze_time(UHR):
            resp = client.post(
                f"/api/trips/{trip_id}/alert-preview", params={"user_id": user_id},
                json={"onset": onset},
            )
        assert resp.status_code == 200, resp.text[:300]
        return _preview_texte(resp.json())

    return _mit_trip(run)


# ───────────────────────── Trip-Versand ───────────────────────────────────


def _trip():
    from datetime import time

    from app.trip import Stage, Trip, Waypoint

    stages = [
        Stage(id=f"ST{i + 1}", name=f"Etappe {i + 1}", date=date(2026, 11, 12 + i),
              start_time=time(8, 0),
              waypoints=[
                  Waypoint(id=f"W{i + 1}a", name="Start", lat=47.0, lon=11.0, elevation_m=1000),
                  Waypoint(id=f"W{i + 1}b", name="Ziel", lat=47.05, lon=11.05, elevation_m=1500),
              ])
        for i in range(3)
    ]
    return Trip(id="trip-2982-gm", name="GM Trip", stages=stages)


def _request(laufend: bool):
    from services.notification_service import RadarAlertRequest
    from services.rain_extent import RainZone

    return RadarAlertRequest(
        onset_minutes=None if laufend else 35,
        already_running=laufend,
        onset_time="22:30" if laufend else "00:05",
        onset_day_offset=0 if laufend else 1,
        onset_weekday=None if laufend else "Sa",
        km_from=12.0, km_to=18.5, km_measured=True,
        rain_zones=[RainZone(km_from=12.0, km_to=14.0, onset_minutes=0 if laufend else 35,
                             event_end_minutes=80)],
        convective_checked=not laufend, gap_km=(15.5,) if laufend else (),
        segment_id="2", is_convective=not laufend,
        intensity_label="mäßiger Regen", source_label="Radar (DWD)",
        briefing_context="nicht im Briefing angekündigt",
        segment_date=date(2026, 11, 13),
        onset_precip_mm=3.2,
        event_end_time="23:50", event_end_day_offset=0 if laufend else 1,
        event_end_weekday=None if laufend else "Sa",
        event_ongoing_beyond_horizon=laufend,
        source_reach_time="01:30", source_reach_day_offset=1,
        location_sharpness_limit_time="23:30", location_sharpness_limit_day_offset=0,
        tz=ZoneInfo("Europe/Vienna"),
    )


def _versand(laufend: bool) -> dict:
    from app.config import Settings
    from services.notification_service import NotificationService

    class _VersandErfasser(NotificationService):
        """Ersetzt NUR den Transportschritt: haelt die fertig gebaute
        AlertMessage fest, statt sie zu versenden (Naht wie `mail_sink`)."""

        erfasst = None

        def _dispatch_alert_message(self, alert_msg, effective_channels, **kw):
            type(self).erfasst = alert_msg
            return None

    svc = _VersandErfasser(settings=Settings(), user_id=f"test_2982_gm_{uuid.uuid4().hex[:6]}")
    with freeze_time(UHR):
        svc.send_radar_alert(
            _trip(), request=_request(laufend), source="Radar (DWD)",
            cooldown_display="2 Stunden", effective_channels={"email"},
        )
    assert _VersandErfasser.erfasst is not None
    return texte(_VersandErfasser.erfasst)


def fall_trip_versand_kuenftig() -> dict:
    return _versand(False)


def fall_trip_versand_laufend() -> dict:
    return _versand(True)


FAELLE = {
    "vergleich_zwei_orte": fall_vergleich_zwei_orte,
    "vergleich_ein_ort_kuenftig": fall_vergleich_ein_ort_kuenftig,
    "vergleich_ein_ort_laufend": fall_vergleich_ein_ort_laufend,
    "replay_kuenftig": fall_replay_kuenftig,
    "replay_laufend": fall_replay_laufend,
    "vorschau_payload": fall_vorschau_payload,
    "trip_versand_kuenftig": fall_trip_versand_kuenftig,
    "trip_versand_laufend": fall_trip_versand_laufend,
}


def _golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("fall", sorted(FAELLE))
def test_golden_master_byte_identisch(fall):
    """AC-1/AC-2/AC-3: jeder Kanaltext und jedes gebaute Event ist
    byte-identisch zum eingefrorenen Stand vor dem Umbau."""
    erwartet = _golden()[fall]
    ist = FAELLE[fall]()
    assert ist.keys() == erwartet.keys()
    for kanal in erwartet:
        assert ist[kanal] == erwartet[kanal], f"{fall}/{kanal} weicht vom Vorher-Stand ab"


def test_ac4_laufend_zuerst_und_ohne_beginnzeit():
    """AC-4: im Buendel steht der laufende Ort zuerst, und alle drei Pfade
    zeigen "laeuft bereits" (Event-Flag gesetzt) -- belegt am Golden."""
    g = _golden()
    zwei = g["vergleich_zwei_orte"]["events"]
    assert [e["location_label"] for e in zwei] == ["Lissabon", "Hütte Berlin"]
    assert zwei[0]["already_running"] is True
    assert g["vergleich_ein_ort_laufend"]["events"][0]["already_running"] is True
    assert g["trip_versand_laufend"]["events"][0]["already_running"] is True
    assert g["replay_laufend"]["sms"] != g["replay_kuenftig"]["sms"]
