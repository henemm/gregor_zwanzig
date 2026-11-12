"""TDD RED — #2795 S3b Teil 1a: „Kanäle je Wettergröße“ entfällt im Alarmversand.

Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.3, AC-29.

Zielverhalten: Zielkanaele eines Alarms ergeben sich NUR aus der Kanal-Tabelle
(``alert_channels`` + ``alert_channel_thresholds``), fuer alle Metriken gleich.
Ein noch vorhandener Altschluessel ``alert_metric_channels`` wird IGNORIERT.

Szenario AC-29: Kanal-Tabelle E-Mail an (Dringlichkeit gering = LOW),
Telegram an (hoch = HIGH); Altschluessel begrenzt die Metrik ``gust`` auf
E-Mail.
* Alarm „hoch“ fuer ``gust``   -> E-Mail UND Telegram.
* Alarm „gering“ fuer ``gust`` -> nur E-Mail (Telegram-Schwelle HIGH).

Heute (#1895 Metrik-Arm in ``alert_channels.resolve_alert_channels``): der
Altschluessel verengt auf {email}, Telegram bekommt auch den „hoch“-Alarm nicht.

WO gemessen wird (Pruefort = Wirkort):
* Trip: am ECHTEN Versandweg ``TripAlertService._send_alert`` — dort wird
  aufgeloest (``_effective_alert_channels``) UND nach Schwelle gefiltert
  (``split_by_threshold``); aufgezeichnet wird an der Transport-Grenze
  (``send_deviation_alert``) — Muster
  ``tests/tdd/test_alert_metric_channel_reader.py`` (aufzeichnender
  Doppelgaenger, KEIN Patch auf den Aufloeser).
* Ortsvergleich: dieselbe Kette, die ``compare_alert.py`` faehrt —
  ``effective_alert_channels(preset, ..., metrics=[...])`` gefolgt von
  ``split_by_threshold`` mit ``preset["alert_channel_thresholds"]``. Zusaetzlich
  der Dispatcher ohne Schwelle (Kanalsatz unabhaengig vom Altschluessel).

Hinweis fuer GREEN: ``tests/tdd/test_alert_metric_channel_reader.py``,
``test_alert_metric_channel_keys.py``, ``test_alarm_abweichung_kette.py`` u. a.
sichern das ALTE Verhalten (Metrik-Arm wirkt) und werden mit dieser Scheibe
fachlich ueberholt; sie sind anzupassen/zu entfernen, nicht diese Tests.
"""
from __future__ import annotations

import json

import pytest

from app.loader import get_data_dir

ALT_NUR_EMAIL = {"gust": {"email": True, "telegram": False, "sms": False, "premium_sms": False}}
SCHWELLEN = {"email": "LOW", "telegram": "HIGH"}


def _tarif(user: str, tier: str = "premium") -> None:
    pfad = get_data_dir(user)
    pfad.mkdir(parents=True, exist_ok=True)
    (pfad / "user.json").write_text(json.dumps({"id": user, "tier": tier, "is_test_user": True}))


def _settings():
    from app.config import Settings

    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="tdd-stub-token", telegram_chat_id="99999",
        sms_gateway_url="http://127.0.0.1:1/api/sms",
        seven_api_key="tdd-stub-key", sms_to="+49000000000", sms_from=None,
    )


def _aenderung(summary_key: str, schwere: str):
    from app.models import ChangeSeverity, WeatherChange

    return WeatherChange(
        metric=summary_key, old_value=10.0, new_value=60.0, delta=50.0,
        threshold=20.0, severity=ChangeSeverity(schwere), direction="increase",
        segment_id="1",
    )


class _TripVersandRekorder:
    """Haelt den Kanalsatz fest, den der Produktivcode an den Transport gibt
    (nicht vorgegeben, sondern beobachtet); gibt ein echtes Ergebnis zurueck."""

    def __init__(self) -> None:
        self.abweichung: list[set[str]] = []

    def send_deviation_alert(self, **kw):
        from services.notification_service import NotificationResult

        kanaele = sorted(kw["effective_channels"])
        self.abweichung.append(set(kanaele))
        return NotificationResult(sent=bool(kanaele), sent_channels=list(kanaele))


def _trip(trip_id: str, *, altschluessel):
    """Kanal-Tabelle: E-Mail + Telegram an (alert_channels), Schwellen LOW/HIGH."""
    from app.models import TripReportConfig
    from tests.helpers.alert_log_fixtures import gust_alert_trip
    from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip

    trip = gust_alert_trip(trip_id)
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=True, send_sms=False,
        alert_on_changes=True, morning_time=morgen, evening_time=abend,
    )
    trip.alert_channels = {"email": True, "telegram": True, "sms": False, "premium_sms": False}
    trip.alert_channel_thresholds = dict(SCHWELLEN)
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    trip.alert_metric_channels = altschluessel
    return trip


def _trip_versand(trip, user_id: str, aenderungen) -> _TripVersandRekorder:
    from services.trip_alert import TripAlertService
    from tests.helpers.alert_log_fixtures import weather

    svc = TripAlertService(
        settings=_settings(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: None,
    )
    rekorder = _TripVersandRekorder()
    svc._notification_service = rekorder
    svc._send_alert(trip, [weather(1)], list(aenderungen))
    return rekorder


# ─────────────────────── Trip: am Versandweg ────────────────────────────────

def test_ac29_trip_alarm_hoch_geht_trotz_altschluessel_an_beide_kanaele():
    """AC-29 (Trip, „hoch“): Altschluessel begrenzt ``gust`` auf E-Mail — der
    Alarm „hoch“ geht trotzdem an E-Mail UND Telegram (Kanal-Tabelle).

    RED-Charakter: Fehlernachweis — heute {email}: der Metrik-Arm verengt.
    """
    user = "u2795-ac29-trip-hoch"
    _tarif(user)
    rek = _trip_versand(_trip("trip-2795-hoch", altschluessel=ALT_NUR_EMAIL), user,
                        [_aenderung("gust_max_kmh", "major")])
    assert rek.abweichung == [{"email", "telegram"}], (
        "AC-29: Alarm 'hoch' fuer gust muss nach der Kanal-Tabelle an E-Mail "
        f"und Telegram gehen, der Altschluessel hat keine Wirkung: {rek.abweichung!r}"
    )


def test_ac29_trip_alarm_gering_geht_nur_an_email():
    """AC-29 (Trip, „gering“): Telegram steht auf „hoch“ — ein Alarm „gering“
    geht nur an E-Mail.

    RED-Charakter: Regressionsschutz — heute gruen (zufaellig gleiches Ergebnis
    wie der Altschluessel); rot, wenn die Schwelle je Kanal nicht mehr greift.
    """
    user = "u2795-ac29-trip-gering"
    _tarif(user)
    rek = _trip_versand(_trip("trip-2795-gering", altschluessel=ALT_NUR_EMAIL), user,
                        [_aenderung("gust_max_kmh", "minor")])
    assert rek.abweichung == [{"email"}], (
        f"AC-29: Alarm 'gering' -> nur E-Mail (Telegram ab hoch): {rek.abweichung!r}"
    )


def test_ac29_trip_altschluessel_aendert_nichts_gegenueber_ohne():
    """AC-29 (Trip): derselbe Trip mit und ohne Altschluessel liefert fuer
    denselben Alarm denselben Kanalsatz — der Schluessel hat keine Wirkung.

    RED-Charakter: Fehlernachweis — heute {email} mit vs. {email, telegram} ohne.
    """
    user = "u2795-ac29-trip-gleich"
    _tarif(user)
    mit = _trip_versand(_trip("trip-2795-mit", altschluessel=ALT_NUR_EMAIL), user,
                        [_aenderung("gust_max_kmh", "major")])
    ohne = _trip_versand(_trip("trip-2795-ohne", altschluessel=None), user,
                         [_aenderung("gust_max_kmh", "major")])
    assert mit.abweichung == ohne.abweichung, (
        f"AC-29: Altschluessel darf nichts aendern — mit {mit.abweichung!r}, ohne {ohne.abweichung!r}"
    )


# ─────────────────────── Ortsvergleich ──────────────────────────────────────

def _vergleich(altschluessel) -> dict:
    p = {
        "id": "cp-2795-ac29", "kind": "vergleich", "name": "AC-29",
        "location_ids": ["loc-a"],
        "alert_channels": {"email": True, "telegram": True, "sms": False, "premium_sms": False},
        "alert_channel_thresholds": dict(SCHWELLEN),
    }
    if altschluessel is not None:
        p["alert_metric_channels"] = altschluessel
    return p


@pytest.mark.parametrize("dringlichkeit, erwartet", [
    ("HIGH", {"email", "telegram"}),
    ("LOW", {"email"}),
], ids=["hoch", "gering"])
def test_ac29_vergleich_kette_aufloesung_plus_schwelle(dringlichkeit, erwartet):
    """AC-29 (Orte): die Kette aus ``compare_alert.py`` —
    ``effective_alert_channels(preset, metrics=[gust])`` + ``split_by_threshold``
    mit den Preset-Schwellen. „hoch“ -> beide, „gering“ -> nur E-Mail.

    RED-Charakter: Fehlernachweis fuer „hoch“ (heute {email}),
    Regressionsschutz fuer „gering“.
    """
    from services.alert_channel_threshold import split_by_threshold
    from services.alert_channels import effective_alert_channels

    user = "u2795-ac29-vgl"
    _tarif(user)
    preset = _vergleich(ALT_NUR_EMAIL)
    kanaele = effective_alert_channels(preset, _settings(), user, metrics=["gust_max_kmh"])
    erlaubt, _ = split_by_threshold(kanaele, dringlichkeit, preset["alert_channel_thresholds"])
    assert erlaubt == erwartet, (
        f"AC-29 (Orte): Alarm {dringlichkeit} fuer gust -> {erwartet}, gemessen {erlaubt!r}"
    )


def test_ac29_vergleich_altschluessel_ohne_wirkung_im_dispatcher():
    """AC-29 (Orte): der Dispatcher liefert mit und ohne Altschluessel denselben
    Kanalsatz (Kanal-Tabelle {email, telegram}).

    RED-Charakter: Fehlernachweis — heute {email} mit Altschluessel.
    """
    from services.alert_channels import effective_alert_channels

    user = "u2795-ac29-vgl-disp"
    _tarif(user)
    mit = effective_alert_channels(_vergleich(ALT_NUR_EMAIL), _settings(), user, metrics=["gust_max_kmh"])
    ohne = effective_alert_channels(_vergleich(None), _settings(), user, metrics=["gust_max_kmh"])
    assert mit == ohne == {"email", "telegram"}, (
        f"AC-29 (Orte): Altschluessel ohne Wirkung erwartet — mit {mit!r}, ohne {ohne!r}"
    )


# ─────────────── Ortsvergleich: am ECHTEN Versandweg (compare_alert) ────────
# Helfer als Kopie aus tests/tdd/test_alert_metric_channel_reader.py (jene
# Datei sichert das alte Verhalten und kann mit dieser Scheibe entfallen).

_ORTE = {"loc-graz": ("Graz", 47.07, 15.44)}


def _punktwetter(point_id: str, name: str, lat: float, lon: float, **werte):
    from datetime import datetime, timezone

    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(**werte),
        fetched_at=datetime.now(timezone.utc), provider="tdd-2795-scripted",
    )


class _GeskripteteWetterquelle:
    """Deterministische Wetterquelle (kein Mock, kein Netz)."""

    def __init__(self, werte_je_ort: dict) -> None:
        self._werte = dict(werte_je_ort)

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None, **kw):
        return _punktwetter(point_id, point_id, lat, lon, **self._werte.get(point_id, {}))


class _VergleichVersandRekorder:
    def __init__(self) -> None:
        self.abweichung: list[set[str]] = []

    def send_multi_location_deviation_alert(self, **kw):
        from services.notification_service import NotificationResult

        kanaele = sorted(kw["effective_channels"])
        self.abweichung.append(set(kanaele))
        return NotificationResult(sent=bool(kanaele), sent_channels=list(kanaele))


def _lege_vergleich_an(user_id: str, preset_id: str, **preset_extra) -> None:
    from app.loader import get_data_root, save_location
    from app.user import SavedLocation
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from tests.helpers.compare_briefings import write_compare_briefings

    name, lat, lon = _ORTE["loc-graz"]
    save_location(SavedLocation(id="loc-graz", name=name, lat=lat, lon=lon, elevation_m=300),
                  user_id=user_id)
    preset = {
        "id": preset_id, "name": preset_id, "user_id": user_id,
        "location_ids": ["loc-graz"], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": [], "letzter_versand": None,
        "top_ort_letzter_versand": None, "created_at": "2026-09-22T00:00:00Z",
        "alert_cooldown_minutes": 0,
    }
    preset.update(preset_extra)
    write_compare_briefings(get_data_root() / "users" / user_id, [preset])
    CompareWeatherSnapshotService(user_id=user_id).save(
        preset_id, "loc-graz", _punktwetter("loc-graz", name, lat, lon, gust_max_kmh=10.0),
    )


def _vergleich_versand(monkeypatch, user_id: str) -> _VergleichVersandRekorder:
    import services.compare_alert as compare_alert_modul
    from services.compare_alert import CompareAlertService

    rekorder = _VergleichVersandRekorder()
    monkeypatch.setattr(compare_alert_modul, "notification_service_for_preset",
                        lambda *a, **kw: rekorder)
    CompareAlertService(
        settings=_settings(), user_id=user_id,
        weather_source=_GeskripteteWetterquelle({"loc-graz": {"gust_max_kmh": 95.0}}),
        mail_sink=lambda subject, body: None,
    ).check_all_compare_presets()
    return rekorder


@pytest.mark.parametrize("altschluessel", [ALT_NUR_EMAIL, None], ids=["mit-alt", "ohne-alt"])
def test_ac29_vergleich_versandweg_alarm_hoch_an_beide_kanaele(monkeypatch, altschluessel):
    """AC-29 (Orte) am ECHTEN Versandweg ``CompareAlertService`` ->
    ``send_multi_location_deviation_alert``: Boeen 10 -> 95 km/h (Dringlichkeit
    hoch), Kanal-Tabelle E-Mail (LOW) + Telegram (HIGH). Ergebnis mit UND ohne
    Altschluessel: {email, telegram}.

    RED-Charakter: Fehlernachweis fuer ``mit-alt`` (heute {email});
    ``ohne-alt`` ist die Positivkontrolle (heute gruen) und beweist, dass der
    Ausloeser wirklich „hoch“ ist.
    """
    user = "u2795-ac29-vgl-versand-" + ("alt" if altschluessel else "neu")
    _tarif(user)
    extra = {
        "alert_channels": {"email": True, "telegram": True, "sms": False, "premium_sms": False},
        "alert_channel_thresholds": dict(SCHWELLEN),
    }
    if altschluessel is not None:
        extra["alert_metric_channels"] = altschluessel
    _lege_vergleich_an(user, "cp-2795-versand", **extra)
    rek = _vergleich_versand(monkeypatch, user)
    assert rek.abweichung == [{"email", "telegram"}], (
        "AC-29 (Orte, Versandweg): Alarm 'hoch' -> E-Mail und Telegram, der "
        f"Altschluessel hat keine Wirkung: {rek.abweichung!r}"
    )
