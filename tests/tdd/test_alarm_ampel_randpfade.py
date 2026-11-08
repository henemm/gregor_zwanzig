"""Randpfade des Ampel-Alarms (Issue #2793 S2b, Fix-Loop 1 nach Adversary F001-F007).

SPEC: docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md (v1.2, §1-§4)
ACs: AC-11, AC-12, AC-18 (Randfaelle), §1 Aktivierung, §2 Tabelle/Protokoll,
§3 Reihenfolge, §4 Gewitter-Token.

Jede Zusicherung wird dort gemessen, wo sie fuer den Nutzer WIRKT: ueber den
echten Trip- bzw. Vergleichs-Einstieg, an der zugestellten Mail (HTML und
Text), am Draht der SMS-/Premium-SMS-Gegenstelle
(``tests/helpers/kanal_fake_transporte.py``), am Alarm-Protokoll und am rohen
Eingangs-Datensatz (``data/users/<uid>/alert_input``). Keine Hilfsfunktion
wird direkt befragt.

Kein ``Mock()``/``patch()``/``MagicMock``; Persistenz unter der
pytest-isolierten Datenwurzel (#1133). Jede Kennung ist ein frischer Nutzer.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.loader import get_data_dir, save_location
from app.models import MetricConfig, ThunderLevel, TripReportConfig, UnifiedWeatherDisplayConfig
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import (
    LAT, LON, clean_compare_user, compare_data_root, read_log, settings_email_only, weather,
)
from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.kanal_fake_transporte import KanalRig, kanal_auswahl, premium_profil_schreiben
from tests.helpers.ortstag import ortstag
from tests.tdd._gsm7_charset import assert_gsm7_clean

# Farbwerte des Mail-Kopfs (Urteils-Plakette), aus den Design-Tokens.
from output.renderers.email.design_tokens import G_DANGER, G_SUCCESS


def _uid(tag: str) -> str:
    return f"tdd-2793-rp-{tag}-{uuid.uuid4().hex[:6]}"


def _ampel(alarm_ab: dict[str, str], template: str = "allgemein") -> dict:
    return {"template": template,
            "metrics": {mid: {"alarm_ab": ab} for mid, ab in alarm_ab.items()}}


def _trip(trip_id: str, *, alarm_ab: dict[str, str] | None = None,
          metrics: tuple[str, ...] = (), abgewaehlt: tuple[str, ...] = (),
          levels: dict[str, str] | None = None, ohne_wetter_reiter: bool = False) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=ortstag(LAT, LON),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    display_config = None
    if not ohne_wetter_reiter:
        display_config = UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id=cid, enabled=True) for cid in metrics]
            + [MetricConfig(metric_id=cid, enabled=False) for cid in abgewaehlt],
            metric_alert_levels=levels,
            ampel=_ampel(alarm_ab or {}),
        )
    trip = Trip(
        id=trip_id, name="Rand-Trip", stages=[stage], official_warnings=None, corridors=[],
        display_config=display_config,
    )
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=True,
        morning_time=morgen, evening_time=abend,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    return trip


def _profil(uid: str, lang: str = "de") -> None:
    """Tarif premium (sonst greift beim zweiten Alarm das Tageslimit)."""
    pfad = get_data_dir(uid) / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    profil = json.loads(pfad.read_text()) if pfad.exists() else {}
    profil.update({"tier": "premium", "language": lang})
    pfad.write_text(json.dumps(profil))


def _trip_lauf(uid: str, trip: Trip, alt: dict, neu: dict) -> list[tuple[str, str]]:
    """Ein Alarm-Lauf ueber den echten Trip-Einstieg; ``(Betreff, Klartext)``."""
    from services.trip_alert import TripAlertService

    if not (get_data_dir(uid) / "user.json").exists():
        _profil(uid)
    mails: list[tuple[str, str]] = []
    TripAlertService(
        settings=settings_email_only(), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body, **_kw: mails.append((subject, body)),
    ).check_and_send_alerts(trip, [weather(1, **alt)], fresh_weather=[weather(1, **neu)])
    return mails


def _alarm_eintraege(uid: str) -> list[dict]:
    log = read_log(uid)
    return [e for e in log["entries"] + log["not_delivered"] if (e.get("changes_count") or 0) > 0]


_PLAKETTE = re.compile(r"background:(#[0-9a-fA-F]{6});color:#ffffff;")


def _plakette(html: str) -> str:
    """Hintergrundfarbe der Urteils-Plakette im Mail-Kopf."""
    treffer = _PLAKETTE.search(html)
    assert treffer, f"keine Urteils-Plakette im Mail-Kopf: {html!r}"
    return treffer.group(1)


@pytest.fixture
def rig(monkeypatch):
    r = KanalRig(monkeypatch)
    yield r
    r.stoppen()


def _rig_lauf(rig: KanalRig, lang: str, trip: Trip, alt: dict, neu: dict) -> dict[str, str]:
    """Alarm-Lauf gegen die echten Kanal-Ausgaenge; Text je Kanal."""
    import email as email_mod

    from services.trip_alert import TripAlertService

    uid = _uid(f"rig-{lang}")
    jetzt = datetime.now(timezone.utc)
    premium_profil_schreiben(uid, reply_at=jetzt - timedelta(minutes=5))
    _profil(uid, lang)
    TripAlertService(
        settings=rig.settings(premium_reply_at=jetzt - timedelta(minutes=5)),
        user_id=uid, throttle_hours=0,
    ).check_and_send_alerts(trip, [weather(1, **alt)], fresh_weather=[weather(1, **neu)])
    texte: dict[str, str] = {}
    for kanal in ("sms", "premium_sms", "telegram"):
        if kanal in (trip.alert_channels or {}) and trip.alert_channels[kanal]:
            assert rig.angenommen[kanal], f"{kanal} nicht zugestellt: {rig!r}"
            texte[kanal] = rig.angenommen[kanal][-1]["text"]
    if rig.angenommen["email"]:
        nachricht = email_mod.message_from_string(rig.angenommen["email"][-1]["roh"])
        for teil in nachricht.walk():
            if teil.get_content_type() == "text/plain":
                texte["email"] = teil.get_payload(decode=True).decode()
            elif teil.get_content_type() == "text/html":
                texte["html"] = teil.get_payload(decode=True).decode()
    return texte


# ═══════════ F001 — D4 (Nullgradgrenze) behaelt sein Melde-Gedaechtnis ═══════

def test_d4_nullgradgrenze_meldet_denselben_fall_kein_zweites_mal():
    """AC-12 / §1 D4: GIVEN Nullgradgrenze „standard" (Δ 400 m), Lauf 1 meldet
    den Fall 3000 -> 2550 m / WHEN Lauf 2 dieselben Werte liefert (Melde-
    Gedaechtnis fortgeschrieben) / THEN keine zweite Meldung -- wie vor S2."""
    uid = _uid("d4-dedup")
    trip = _trip("trip-d4dd", metrics=("freezing_level",), levels={"freezing_level": "standard"})
    anker, neu = {"freezing_level_m": 3000}, {"freezing_level_m": 2550}
    assert _trip_lauf(uid, trip, anker, neu), "Voraussetzung: Lauf 1 meldet die Nullgradgrenze."
    assert _trip_lauf(uid, trip, anker, neu) == [], "D4: derselbe Fall darf nicht erneut melden."
    assert len(_alarm_eintraege(uid)) == 1, _alarm_eintraege(uid)


# ══════════ F002 — Gewitter behaelt sein Stufen-Token ohne Farbpaar ══════════

_FARBPAAR = re.compile(r":[GYOR-]>[GYOR-]")


@pytest.mark.parametrize("lang", ["de", "en"])
def test_gewitter_verschaerfung_sms_und_premium_sms_ohne_farbpaar(rig, lang):
    """§4: GIVEN Gewitter „Alarm ab Orange" (Allgemein: mittel = orange) /
    WHEN die Stufe von „keins" auf „mittel" steigt / THEN tragen SMS und
    Premium-SMS das Gewitter-Token ``TH:…->M`` OHNE Farbpaar ``:X>Y``."""
    trip = _trip(f"trip-th-{lang}", alarm_ab={"thunder": "orange"}, metrics=("thunder",))
    trip.alert_channels = kanal_auswahl("sms", "premium_sms")
    texte = _rig_lauf(rig, lang, trip, {"thunder_level_max": ThunderLevel.NONE},
                      {"thunder_level_max": ThunderLevel.MED})
    for kanal in ("sms", "premium_sms"):
        text = texte[kanal]
        assert re.search(r"TH:\S*->M", text), f"{kanal}/{lang}: Gewitter-Token fehlt: {text!r}"
        assert not _FARBPAAR.search(text), f"{kanal}/{lang}: Gewitter mit Farbpaar: {text!r}"
        assert_gsm7_clean(text, f"{kanal}/{lang}")


# ═══════════ F003 — Tagestief-Entwarnung nennt die Kaelteseite ═══════════════

_TAGESTIEF = {"de": ("Tagestief", "Tageshöchst"), "en": ("Daily low", "Daily high")}


@pytest.mark.parametrize("lang", ["de", "en"])
def test_tagestief_entwarnung_orange_auf_gruen_nennt_tagestief_und_o_g(rig, lang):
    """AC-11 / §4: GIVEN Temperatur „Alarm ab Orange", Allgemein (unten orange
    < -5) / WHEN das Tagestief von -7 auf 1 °C steigt (orange -> gruen) /
    THEN eine Entwarnung, deren Mail das Tagestief nennt (nicht das
    Tageshoechst) und deren SMS das Farbpaar ``:O>G`` traegt."""
    trip = _trip(f"trip-tt-{lang}", alarm_ab={"temperature": "orange"},
                 metrics=("temperature",))
    trip.alert_channels = kanal_auswahl("email", "sms")
    texte = _rig_lauf(rig, lang, trip, {"temp_min_c": -7.0}, {"temp_min_c": 1.0})
    richtig, falsch = _TAGESTIEF[lang]
    assert "email" in texte, f"Entwarnung nicht per Mail zugestellt: {rig!r}"
    assert richtig in texte["email"], texte["email"]
    assert falsch not in texte["email"], texte["email"]
    assert ":O>G" in texte["sms"], texte["sms"]


# ═══════════ F004 — Sprung auf der Unterseite heisst: der Wert faellt ════════

def test_tagestief_faellt_um_sprung_schwelle_innerhalb_orange_alarmiert():
    """§2 Sprung (unten: faellt): GIVEN Temperatur „Alarm ab Orange", Tagestief
    -6 °C (orange) / WHEN es auf -12 °C faellt (weiter orange, Sprung 6 >= 5) /
    THEN Alarm „weiter orange, großer Sprung", der das Tagestief nennt."""
    uid = _uid("tt-sprung")
    trip = _trip("trip-tts", alarm_ab={"temperature": "orange"}, metrics=("temperature",))
    mails = _trip_lauf(uid, trip, {"temp_min_c": -6.0}, {"temp_min_c": -12.0})
    assert mails, "Kaeltesprung innerhalb Orange muss alarmieren."
    assert "Tagestief weiter orange, großer Sprung" in mails[-1][1], mails[-1][1]


def test_tagestief_steigt_um_sprung_schwelle_innerhalb_orange_bleibt_stumm():
    """§2 Gegenstueck: -12 -> -6 °C (weiter orange, Erwaermung 6) ist kein
    Sprung zum Schlechteren und keine Entwarnung -> kein Alarm."""
    uid = _uid("tt-warm")
    trip = _trip("trip-ttw", alarm_ab={"temperature": "orange"}, metrics=("temperature",))
    assert _trip_lauf(uid, trip, {"temp_min_c": -12.0}, {"temp_min_c": -6.0}) == []
    assert _alarm_eintraege(uid) == []


# ═══════════ F005 — fehlender Ankerwert ergibt kein Ereignis ═════════════════

def test_anker_ohne_boeenwert_neuwert_rot_alarmiert_nicht():
    """§2 (nur Werte mit Aussage): GIVEN Boeen „Alarm ab Orange", der Anker hat
    keinen Boeenwert / WHEN die Prognose 70 km/h (rot) liefert / THEN kein
    Alarm -- „keine Aussage" ist nicht „gruen"."""
    uid = _uid("anker-none")
    trip = _trip("trip-an", alarm_ab={"gust": "orange"}, metrics=("gust",))
    assert _trip_lauf(uid, trip, {"gust_max_kmh": None}, {"gust_max_kmh": 70.0}) == []
    assert _alarm_eintraege(uid) == []


# ═══════════ F006 — Aktivierung: abgewaehlt bleibt still, Ergaenzung nur im Vergleich

def test_abgewaehltes_tagestief_alarmiert_nicht():
    """§1 Aktivierung: GIVEN Temperatur aktiv, aber das Tagestief
    (``temperature_cold``) ausdruecklich abgewaehlt, „Alarm ab Orange" /
    WHEN das Tagestief von 1 auf -7 °C faellt (gruen -> orange) / THEN kein
    Alarm (Gegenstueck mit aktivem Tagestief: AC-11 meldet)."""
    uid = _uid("tt-ab")
    trip = _trip("trip-ttab", alarm_ab={"temperature": "orange"}, metrics=("temperature",),
                 abgewaehlt=("temperature_cold",))
    assert _trip_lauf(uid, trip, {"temp_min_c": 1.0}, {"temp_min_c": -7.0}) == []
    assert _alarm_eintraege(uid) == []


def test_abgewaehltes_tagestief_laesst_tageshoechst_weiter_alarmieren():
    """Kontrolle zum Test davor: dieselbe Abwahl schaltet nur die Kaelteseite
    ab; das Tageshoechst 27 -> 32 °C (Allgemein: gruen -> orange) alarmiert
    weiter -- sonst bewiese der stumme Test davor nur einen Aufbaufehler."""
    uid = _uid("tt-ab-kontrolle")
    trip = _trip("trip-ttabk", alarm_ab={"temperature": "orange"}, metrics=("temperature",),
                 abgewaehlt=("temperature_cold",))
    mails = _trip_lauf(uid, trip, {"temp_max_c": 27.0}, {"temp_max_c": 32.0})
    assert mails and "Tageshöchst" in mails[-1][1], mails


def test_trip_ohne_wetter_reiter_ergaenzt_keine_ampel_metrik():
    """§1 Aktivierung: GIVEN ein Trip ohne Wetter-Reiter (``display_config``
    fehlt, keine Vergleichs-Ergaenzung) / WHEN Boeen 40 -> 55 (gelb ->
    orange, Vorgabe Allgemein „Alarm ab Orange") / THEN kein Alarm."""
    uid = _uid("ohne-reiter")
    trip = _trip("trip-or", ohne_wetter_reiter=True)
    assert _trip_lauf(uid, trip, {"gust_max_kmh": 40.0}, {"gust_max_kmh": 55.0}) == []
    assert _alarm_eintraege(uid) == []


class _Quelle:
    """Deterministische ``LocationWeatherSource`` (DI-Naht, kein Mock)."""

    def __init__(self, **summary) -> None:
        self._summary = summary

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              elevation_m=None, user_id=None, target_date=None):
        from app.models import SegmentWeatherSummary
        from services.point_weather import PointWeatherData

        return PointWeatherData(
            id=point_id, name="Vergleichsort", lat=lat, lon=lon, timeseries=None,
            aggregated=SegmentWeatherSummary(**self._summary),
            fetched_at=datetime.now(timezone.utc), provider="tdd-2793-rp",
        )


def test_vergleich_ohne_wetter_reiter_ergaenzt_die_ampel_metrik():
    """§1 / #1971 Gegenstueck: GIVEN ein Alt-Vergleich OHNE ``active_metrics``
    (Vergleichs-Ergaenzung aktiv) / WHEN Boeen 40 -> 55 (gelb -> orange) /
    THEN Alarm -- die Ergaenzung gilt nur hier, nicht im Trip (Test davor)."""
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = _uid("cmp-ohne-reiter")
    preset_id = "cp-2793-rp"
    try:
        clean_compare_user(uid)
        save_location(
            SavedLocation(id="loc-a", name="Vergleichsort", lat=LAT, lon=LON, elevation_m=1000),
            user_id=uid,
        )
        write_compare_briefings(compare_data_root() / uid, [{
            "id": preset_id, "name": "Vergleich Rand", "user_id": uid,
            "location_ids": ["loc-a"], "schedule": "daily", "weekday": 4,
            "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
            "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
            "alert_cooldown_minutes": 0,
            "display_config": {"ampel": _ampel({"gust": "orange"})},
        }])
        _profil(uid)
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-a", _Quelle(gust_max_kmh=40.0).fetch("loc-a", LAT, LON),
        )
        mails: list = []
        CompareAlertService(
            settings=settings_email_only(), user_id=uid,
            weather_source=_Quelle(gust_max_kmh=55.0),
            mail_sink=lambda subject, body, **_kw: mails.append((subject, body)),
        ).check_all_compare_presets()
        assert mails, "Alt-Vergleich ohne active_metrics: Ergaenzung muss alarmieren."
        assert "von gelb auf orange gestiegen" in mails[-1][1], mails[-1][1]
    finally:
        clean_compare_user(uid)


# ═══════════ F007 — Protokoll-Schwelle, Mail-Kopf, Reihenfolge ═══════════════

def _eingangs_datensaetze(uid: str) -> list[dict]:
    ordner = get_data_dir(uid) / "alert_input"
    return [json.loads(p.read_text()) for p in sorted(ordner.glob("forecast_change_trip_*.json"))]


def test_protokoll_traegt_die_sprung_schwelle_als_threshold():
    """§2 letzter Punkt (ADR-0013 Nachtrag): GIVEN eine Boeen-Verschaerfung
    40 -> 55 / WHEN der Alarm zugestellt wird / THEN vermerkt der rohe
    Eingangs-Datensatz des Alarms ``threshold`` = Sprung-Schwelle 20 km/h
    (Spalte „standard"), nicht 0."""
    uid = _uid("thr")
    trip = _trip("trip-thr", alarm_ab={"gust": "orange"}, metrics=("gust",))
    assert _trip_lauf(uid, trip, {"gust_max_kmh": 40.0}, {"gust_max_kmh": 55.0})
    datensaetze = _eingangs_datensaetze(uid)
    assert datensaetze, "kein Eingangs-Datensatz zum Alarm geschrieben"
    changes = datensaetze[-1]["payload"]["changes"]
    gust = [c for c in changes if c["metric"] == "gust_max_kmh"]
    assert gust and gust[0]["threshold"] == 20.0, changes


def _mail_html(rig: KanalRig, trip: Trip, alt: dict, neu: dict) -> tuple[str, str]:
    """Zugestellte Mail am SMTP-Draht: ``(Klartext, HTML)``."""
    trip.alert_channels = kanal_auswahl("email")
    texte = _rig_lauf(rig, "de", trip, alt, neu)
    assert "html" in texte and "email" in texte, f"Mail nicht zugestellt: {rig!r}"
    return texte["email"], texte["html"]


@pytest.mark.parametrize("alt,neu,farbe", [
    (55.0, 35.0, G_SUCCESS),   # Entwarnung orange -> gelb
    (40.0, 55.0, G_DANGER),    # Verschaerfung gelb -> orange
])
def test_einzelereignis_plakette_gruen_bei_entwarnung_rot_bei_alarm(rig, alt, neu, farbe):
    """§3/§4: die Urteils-Plakette im Mail-Kopf ist bei einer Entwarnung
    (orange -> gelb) gruen, bei einer Verschaerfung (gelb -> orange) rot."""
    trip = _trip("trip-pl1", alarm_ab={"gust": "orange"}, metrics=("gust",))
    _plain, html = _mail_html(rig, trip, {"gust_max_kmh": alt}, {"gust_max_kmh": neu})
    assert _plakette(html) == farbe, html


def test_gemischte_meldung_mit_einer_verschaerfung_hat_rote_plakette(rig):
    """Mehrere Ereignisse: Entwarnung Boeen (orange -> gelb) UND Verschaerfung
    Niederschlag (gelb -> orange) in einer Mail -> Plakette rot."""
    trip = _trip("trip-pl2", alarm_ab={"gust": "orange", "precipitation": "orange"},
                 metrics=("gust", "precipitation"))
    plain, html = _mail_html(rig, trip,
                             {"gust_max_kmh": 55.0, "precip_sum_mm": 2.0},
                             {"gust_max_kmh": 35.0, "precip_sum_mm": 6.0})
    assert "Entwarnung Böen" in plain and "von gelb auf orange gestiegen: 2,0 mm" in plain, plain
    assert _plakette(html) == G_DANGER, html


def test_nur_entwarnungen_in_einer_meldung_haben_gruene_plakette(rig):
    """Mehrere Ereignisse, alle Entwarnung (Boeen orange -> gelb, Niederschlag
    orange -> gelb) -> Plakette gruen."""
    trip = _trip("trip-pl3", alarm_ab={"gust": "orange", "precipitation": "orange"},
                 metrics=("gust", "precipitation"))
    plain, html = _mail_html(rig, trip,
                             {"gust_max_kmh": 55.0, "precip_sum_mm": 6.0},
                             {"gust_max_kmh": 35.0, "precip_sum_mm": 2.0})
    assert plain.count("Entwarnung") >= 2, plain
    assert _plakette(html) == G_SUCCESS, html


# ═══════════ F302/F303 (Fix-Loop 4) — Mehrfachmeldung: Farbpaar je Ereignis ═══
#
# Ein Lauf, zwei Ampel-Ereignisse: Verschaerfung Boeen 40 -> 55 (gelb ->
# orange) und Entwarnung Niederschlag 6 -> 2 mm (orange -> gelb), beide
# „Alarm ab Orange" in der Vorlage „Allgemein". Gelesen wird am Draht.

_MEHRFACH_ALT = {"gust_max_kmh": 40.0, "precip_sum_mm": 6.0}
_MEHRFACH_NEU = {"gust_max_kmh": 55.0, "precip_sum_mm": 2.0}
_MEHRFACH_SAETZE = {
    "de": ("Böen von gelb auf orange gestiegen: 40 km/h → 55 km/h",
           "von orange auf gelb zurückgegangen (6,0 mm → 2,0 mm)"),
    "en": ("Gusts rose from yellow to orange: 40 km/h → 55 km/h",
           "back from orange to yellow (6.0 mm → 2.0 mm)"),
}
_ENTWARNUNG = {"de": "Entwarnung", "en": "All clear"}
_H1_AENDERUNGEN = {"de": "2 Änderungen seit dem Briefing", "en": "2 changes since the briefing"}
_H1_SCHWELLE = {"de": "Werte über der Alarm-Schwelle", "en": "values above the alert threshold"}


def _mehrfach_trip(trip_id: str) -> Trip:
    return _trip(trip_id, alarm_ab={"gust": "orange", "precipitation": "orange"},
                 metrics=("gust", "precipitation"))


@pytest.mark.parametrize("lang", ["de", "en"])
def test_f302_telegram_mehrfachmeldung_traegt_farbpaar_je_ereignis(rig, lang):
    """AC-18 / §4 (Fix-Loop 4, F302): GIVEN Verschaerfung Boeen gelb ->
    orange UND Entwarnung Niederschlag orange -> gelb in einem Lauf / WHEN der
    Alarm per Telegram (rich) zugestellt wird / THEN traegt die Nachricht am
    Draht fuer JEDES Ereignis seinen eigenen Farbsatz (Farbpaar und Werte), in
    DE und EN -- nicht die alte Δ-Zeile ``Böen 40→55 km/h`` ohne Farbe."""
    trip = _mehrfach_trip(f"trip-tg2-{lang}")
    trip.alert_channels = kanal_auswahl("telegram")
    texte = _rig_lauf(rig, lang, trip, _MEHRFACH_ALT, _MEHRFACH_NEU)
    text = texte["telegram"]
    verschaerfung, entwarnung = _MEHRFACH_SAETZE[lang]
    assert verschaerfung in text, f"telegram/{lang}: Verschaerfung ohne Farbpaar: {text!r}"
    assert entwarnung in text, f"telegram/{lang}: Entwarnung ohne Farbpaar: {text!r}"
    assert _ENTWARNUNG[lang] in text, f"telegram/{lang}: Entwarnung nicht benannt: {text!r}"
    assert "40→55" not in text and "6→2 mm" not in text, (
        f"telegram/{lang}: alte Δ-Zeile ohne Farbpaar: {text!r}")


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("alt,neu", [
    (_MEHRFACH_ALT, _MEHRFACH_NEU),                                  # gemischt
    ({"gust_max_kmh": 55.0, "precip_sum_mm": 6.0},
     {"gust_max_kmh": 35.0, "precip_sum_mm": 2.0}),                  # nur Entwarnungen
], ids=["gemischt", "nur_entwarnungen"])
def test_f303_mail_ueberschrift_mehrerer_ampel_ereignisse_nennt_aenderungen(rig, lang, alt, neu):
    """§4 (Fix-Loop 4, F303): GIVEN zwei Ampel-Ereignisse in einer Meldung
    (gemischt bzw. zwei Entwarnungen) / WHEN die Mail zugestellt wird /
    THEN lautet die Ueberschrift „2 Änderungen seit dem Briefing" und nie
    „N Werte über der Alarm-Schwelle" -- das Schwellen-Urteil entfaellt fuer
    Ampel-Ereignisse, eine Entwarnung liegt gerade NICHT ueber der Schwelle."""
    trip = _mehrfach_trip(f"trip-h1-{lang}")
    trip.alert_channels = kanal_auswahl("email")
    texte = _rig_lauf(rig, lang, trip, alt, neu)
    assert "email" in texte, f"Mail nicht zugestellt: {rig!r}"
    plain = texte["email"]
    erste_zeile = next(z for z in plain.splitlines() if z.strip())
    assert erste_zeile.strip() == _H1_AENDERUNGEN[lang], plain
    assert _H1_SCHWELLE[lang] not in plain, plain
    assert _H1_SCHWELLE[lang] not in texte["html"], texte["html"]


# ═══════════ F304 (Fix-Loop 4) — UV folgt der Aktivierung im Reiter Wetter ═════

@pytest.mark.parametrize("abgewaehlt", [(), ("uv_index",)], ids=["fehlt", "abgewaehlt"])
def test_f304_uv_nicht_aktiv_alarmiert_nicht_trotz_alarm_ab_orange(abgewaehlt):
    """§1 Aktivierung (Fix-Loop 4, F304): GIVEN UV „Alarm ab Orange", im
    Reiter Wetter aber nicht aktiv (fehlt bzw. ``enabled=False``), Boeen aktiv
    / WHEN der UV-Index von 2 (gruen) auf 7 (orange) springt / THEN kein
    Alarm. Gegenstueck mit aktivem UV: ``test_f101_verschaerfung_je_ampel_
    quelle_ueber_den_trip[uv_index]`` meldet."""
    uid = _uid(f"uv-{len(abgewaehlt)}")
    trip = _trip(f"trip-uv-{len(abgewaehlt)}", alarm_ab={"uv_index": "orange", "gust": "orange"},
                 metrics=("gust",), abgewaehlt=abgewaehlt)
    alt = {"uv_index_max": 2.0, "gust_max_kmh": 20.0}
    assert _trip_lauf(uid, trip, alt, {"uv_index_max": 7.0, "gust_max_kmh": 20.0}) == []
    assert _alarm_eintraege(uid) == []


def test_f304_kontrolle_aktive_boeen_im_selben_aufbau_alarmieren():
    """Kontrolle zum Test davor: im selben Aufbau (UV nicht aktiv) alarmiert
    die aktive Boee gelb -> orange -- sonst bewiese der stumme UV-Test nur
    einen Aufbaufehler."""
    uid = _uid("uv-kontrolle")
    trip = _trip("trip-uv-k", alarm_ab={"uv_index": "orange", "gust": "orange"},
                 metrics=("gust",))
    mails = _trip_lauf(uid, trip, {"uv_index_max": 2.0, "gust_max_kmh": 40.0},
                       {"uv_index_max": 2.0, "gust_max_kmh": 55.0})
    assert mails and "Böen von gelb auf orange gestiegen" in mails[-1][1], mails


def test_reihenfolge_nach_farbe_der_neuen_stufe():
    """§3 (mehrere Ereignisse): GIVEN Boeen gelb -> orange (40 -> 55) und
    Niederschlag gruen -> rot (0 -> 12) / WHEN beide in einer Mail stehen /
    THEN steht der Niederschlag (neu rot) vor den Boeen (neu orange) --
    geordnet nach der NEUEN Farbe, nicht nach der Anker-Farbe."""
    trip = _trip("trip-ord", alarm_ab={"gust": "orange", "precipitation": "orange"},
                 metrics=("gust", "precipitation"))
    mails = _trip_lauf(_uid("ord"), trip,
                       {"gust_max_kmh": 40.0, "precip_sum_mm": 0.0},
                       {"gust_max_kmh": 55.0, "precip_sum_mm": 12.0})
    assert mails, "Meldung mit zwei Verschaerfungen erwartet"
    text = mails[-1][1]
    regen = text.find("von grün auf rot gestiegen: 0,0 mm → 12,0 mm")
    boeen = text.find("Böen von gelb auf orange gestiegen")
    assert regen >= 0 and boeen >= 0, text
    assert regen < boeen, f"Reihenfolge falsch (Niederschlag rot zuerst erwartet): {text!r}"
