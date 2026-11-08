"""TDD RED -- Farbpaar im Alarmtext aller vier Kanaele, DE und EN
(Issue #2793 S2b, Spec feat_2793_s2_alarm_stufenwechsel.md §4; AC-18).

Der Alarm laeuft ueber den echten Trip-Einstieg und die echten vier
Kanal-Ausgaenge (``tests/helpers/kanal_fake_transporte.py``); gelesen wird,
was am Draht ankommt: die E-Mail (Klartext-Teil), die Telegram-Nachricht
(Stil „rich"), die SMS und die Premium-SMS. Die Telegram-Kurzform sendet
denselben Text wie die SMS (``render_sms``), ihr Token ist damit mitgeprueft.

Kein ``Mock()``/``patch()``/``MagicMock``.
"""
from __future__ import annotations

import email
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.loader import get_data_dir
from app.models import MetricConfig, TripReportConfig, UnifiedWeatherDisplayConfig
from app.trip import Stage, Trip, Waypoint

from tests.helpers.alert_log_fixtures import LAT, LON, weather
from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.kanal_fake_transporte import KanalRig, kanal_auswahl, premium_profil_schreiben
from tests.helpers.ortstag import ortstag
from tests.tdd._gsm7_charset import assert_gsm7_clean

# (alt, neu, SMS-Token, Satz DE, Satz EN)
_FAELLE = {
    "verschaerfung": (40.0, 55.0, "G40->55:Y>O",
                      "Böen von gelb auf orange gestiegen: 40 km/h → 55 km/h",
                      "Gusts rose from yellow to orange: 40 km/h → 55 km/h"),
    "entwarnung": (55.0, 35.0, "G55->35:O>Y",
                   "Entwarnung Böen: von orange auf gelb zurückgegangen (55 km/h → 35 km/h)",
                   "All clear Gusts: back from orange to yellow (55 km/h → 35 km/h)"),
}
_BEZUG = {"de": "verglichen mit", "en": "compared with"}


@pytest.fixture
def rig(monkeypatch):
    r = KanalRig(monkeypatch)
    yield r
    r.stoppen()


def _trip(trip_id: str) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=ortstag(LAT, LON),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="Ampel", stages=[stage], official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id, metrics=[MetricConfig(metric_id="gust", enabled=True)],
            ampel={"template": "allgemein", "metrics": {"gust": {"alarm_ab": "orange"}}},
        ),
    )
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=True,
        morning_time=morgen, evening_time=abend,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    trip.alert_channels = kanal_auswahl("email", "telegram", "sms", "premium_sms")
    return trip


def _lauf(rig: KanalRig, lang: str, alt: float, neu: float) -> dict[str, str]:
    from services.trip_alert import TripAlertService

    uid = f"tdd-2793-txt-{lang}-{uuid.uuid4().hex[:6]}"
    jetzt = datetime.now(timezone.utc)
    premium_profil_schreiben(uid, reply_at=jetzt - timedelta(minutes=5))
    pfad = get_data_dir(uid) / "user.json"
    profil = json.loads(pfad.read_text())
    profil["language"] = lang
    pfad.write_text(json.dumps(profil))
    TripAlertService(
        settings=rig.settings(premium_reply_at=jetzt - timedelta(minutes=5)),
        user_id=uid, throttle_hours=0,
    ).check_and_send_alerts(
        _trip(f"trip-{lang}"), [weather(1, gust_max_kmh=alt)],
        fresh_weather=[weather(1, gust_max_kmh=neu)],
    )
    texte = {}
    for kanal in ("sms", "premium_sms"):
        assert rig.angenommen[kanal], f"{kanal} nicht zugestellt: {rig!r}"
        texte[kanal] = rig.angenommen[kanal][-1]["text"]
    assert rig.angenommen["telegram"], f"Telegram nicht zugestellt: {rig!r}"
    texte["telegram"] = rig.angenommen["telegram"][-1]["text"]
    assert rig.angenommen["email"], f"E-Mail nicht zugestellt: {rig!r}"
    nachricht = email.message_from_string(rig.angenommen["email"][-1]["roh"])
    texte["email"] = next(
        teil.get_payload(decode=True).decode()
        for teil in nachricht.walk() if teil.get_content_type() == "text/plain"
    )
    return texte


@pytest.mark.parametrize("fall", sorted(_FAELLE))
@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac18_farbpaar_in_allen_vier_kanaelen(rig, fall, lang):
    """AC-18 GIVEN Boeen-Verschaerfung 40 -> 55 (gelb -> orange) bzw.
    Entwarnung 55 -> 35 / WHEN der Alarm in allen vier Kanaelen zugestellt wird
    (DE und EN) / THEN nennen E-Mail und Telegram Farbpaar, Werte und den Bezug
    aufs Briefing; SMS und Premium-SMS tragen das Token mit ``:{X}>{Y}`` in
    GSM-7 innerhalb der Laengengrenzen, in beiden Sprachen gleich."""
    alt, neu, token, satz_de, satz_en = _FAELLE[fall]
    texte = _lauf(rig, lang, alt, neu)
    satz = satz_de if lang == "de" else satz_en

    for kanal in ("email", "telegram"):
        assert satz in texte[kanal], f"{kanal}/{lang}: {satz!r} fehlt in {texte[kanal]!r}"
        assert _BEZUG[lang] in texte[kanal], f"{kanal}/{lang}: Bezug fehlt: {texte[kanal]!r}"

    for kanal, grenze in (("sms", 140), ("premium_sms", 153)):
        text = texte[kanal]
        assert token in text, f"{kanal}/{lang}: Token {token!r} fehlt in {text!r}"
        assert len(text) <= grenze, f"{kanal}/{lang}: {len(text)} > {grenze}: {text!r}"
        assert_gsm7_clean(text, f"{kanal}/{lang}")


def test_kontrolle_alle_vier_kanaele_werden_beliefert(rig):
    """Kontrolle (vor und nach S2b gruen): 20 -> 60 km/h (gruen -> rot) erreicht
    alle vier Draehte -- ohne diese Kontrolle bewiese ein roter AC-18 nur einen
    Aufbaufehler."""
    texte = _lauf(rig, "de", 20.0, 60.0)
    assert set(texte) == {"email", "telegram", "sms", "premium_sms"}
