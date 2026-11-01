"""Alarm-Bausteine der Orchestrierung in der Nutzersprache (Issue #2672).

SPEC: docs/specs/modules/i18n_p9b_scheduler_orchestrierung_2672.md

Trip-Abweichungsalarm („verglichen mit gestern …“) und die drei
Ortsvergleich-Alarmdienste (Abweichung, Radar, amtlich) reichen die Sprache
ihres Nutzers durch -- je Dienstobjekt aus ``user.json``. Echte Dienste ueber
die vorhandenen Naehte (``mail_sink``, ``weather_source``, ``radar_service``,
echte Warnquelle in der echten Registry); Uhr eingefroren. Erwartungen aus dem
Katalog, Gegenprobe mit einem deutschen Nutzer im selben Prozess.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from i18n import t, tn
from tests.helpers import nowcast_gate_fixtures as ng

JETZT = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
LAT, LON = 47.07, 15.44  # Graz, Europe/Vienna (UTC+1 am 29.10.)


def _nutzer(user_id: str, lang: str) -> None:
    from app.loader import get_data_dir

    ng.clean_uid(user_id)
    ng.write_user_tier(user_id, "premium")
    pfad = get_data_dir(user_id) / "user.json"
    profil = json.loads(pfad.read_text())
    profil["language"] = lang
    pfad.write_text(json.dumps(profil))


# --------------------------------------------------------------- Trip-Δ


def test_trip_abweichung_nennt_den_vergleichszeitpunkt_in_nutzersprache():
    """Δ-Anker von gestern: „compared with yesterday 06:00“ bzw. „verglichen
    mit gestern 06:00 Uhr“ -- Tageswort aus ``format_reference_at(lang)``."""
    from services.trip_alert import TripAlertService
    from tests.helpers.alert_log_fixtures import gust_alert_trip, settings_email_only, weather

    texte = {}
    with freeze_time(JETZT):
        for lang in ("en", "de"):
            uid = f"p9b-trip-delta-{lang}"
            _nutzer(uid, lang)
            alt = weather(1, gust_max_kmh=20.0)
            alt.fetched_at = JETZT - timedelta(hours=30)  # gestern 07:00 Ortszeit
            post: list = []
            svc = TripAlertService(settings=settings_email_only(), user_id=uid, throttle_hours=0,
                                   mail_sink=lambda subject, body: post.append(body))
            assert svc.check_and_send_alerts(
                gust_alert_trip(f"trip-delta-{lang}"), [alt],
                fresh_weather=[weather(1, gust_max_kmh=60.0)],
            ) is True
            texte[lang] = post[0]
    for lang, text in texte.items():
        referenz = t("alarm.zeit.gestern_uhr", lang, zeit="07:00")
        assert t("alarm.mail.verglichen", lang, referenz=referenz) in text, text[-600:]


# ------------------------------------------------------- Ortsvergleich


def _ort_und_preset(uid: str, **extra) -> str:
    from app.loader import save_location
    from app.user import SavedLocation
    from tests.helpers.briefing_zeiten import briefing_zeiten_iso
    from tests.helpers.compare_briefings import write_compare_briefings
    from utils.timezone import first_resolvable_tz

    save_location(SavedLocation(id="loc-1", name="Testort", lat=LAT, lon=LON, elevation_m=353),
                  user_id=uid)
    zone = first_resolvable_tz(
        [SavedLocation(id="p", name="p", lat=LAT, lon=LON, elevation_m=0)])
    morgen, abend = briefing_zeiten_iso(zone)
    preset_id = f"cp-{uid}"
    from app.loader import get_data_root

    write_compare_briefings(get_data_root() / "users" / uid, [{
        "id": preset_id, "name": "Graz", "location_ids": ["loc-1"], "schedule": "daily",
        "profil": "ALLGEMEIN", "created_at": "2026-10-01T00:00:00Z",
        "morning_time": morgen, "evening_time": abend, **extra,
    }])
    return preset_id


class _Wetter:
    """Deterministische ``LocationWeatherSource`` (kein Mock)."""

    def __init__(self, precip: float) -> None:
        self._precip = precip

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              elevation_m=None, user_id=None):
        from app.models import SegmentWeatherSummary
        from services.point_weather import PointWeatherData

        return PointWeatherData(
            id=point_id, name=point_id, lat=lat, lon=lon, timeseries=None,
            aggregated=SegmentWeatherSummary(precip_sum_mm=self._precip),
            fetched_at=datetime.now(timezone.utc), provider="test-scripted")


def test_ortsvergleich_abweichung_nennt_den_vergleichszeitpunkt_in_nutzersprache():
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    texte = {}
    for lang in ("en", "de"):
        uid = f"p9b-cmp-delta-{lang}"
        with freeze_time(JETZT - timedelta(hours=20)):  # gestern 17:00 Ortszeit (< 26 h)
            _nutzer(uid, lang)
            preset_id = _ort_und_preset(uid)
            CompareWeatherSnapshotService(user_id=uid).save(
                preset_id, "loc-1", _Wetter(2.0).fetch("loc-1", LAT, LON))
        with freeze_time(JETZT):
            post: list = []
            CompareAlertService(
                settings=ng.settings_email_only(), user_id=uid, weather_source=_Wetter(30.0),
                mail_sink=lambda subject, body: post.append(body),
            ).check_all_compare_presets()
        assert post, lang
        texte[lang] = post[0]
    for lang, text in texte.items():
        referenz = t("alarm.zeit.gestern_uhr", lang, zeit="17:00")
        assert t("alarm.mail.verglichen", lang, referenz=referenz) in text, text[-600:]


def _nasse_frames(lat: float, lon: float) -> list:
    from providers.brightsky import RadarFrame

    return [RadarFrame(timestamp=datetime.now(timezone.utc) + timedelta(minutes=8),
                       precip_mm_h=0.6, is_convective=False)]


@pytest.mark.parametrize("cooldown,dauer", [(120, ("stunden", 2)), (45, ("minuten", 45))])
def test_ortsvergleich_radar_cooldown_in_nutzersprache(cooldown, dauer):
    from services.compare_radar_alert import CompareRadarAlertService

    texte = {}
    with freeze_time(JETZT):
        for lang in ("en", "de"):
            uid = f"p9b-cmp-radar-{lang}-{cooldown}"
            _nutzer(uid, lang)
            _ort_und_preset(uid, radar_alert_enabled=True, alert_cooldown_minutes=cooldown)
            post: list = []
            gesendet = CompareRadarAlertService(
                settings=ng.settings_email_only(), user_id=uid,
                radar_service=ng.radar_service(_nasse_frames),
                mail_sink=lambda subject, body: post.append(body),
            ).check_all_compare_presets()
            assert gesendet == 1, lang
            texte[lang] = post[0]
    for lang, text in texte.items():
        satz = t("alarm.regen.cooldown", lang, praefix=t("alarm.radar.cooldown_praefix", lang),
                 dauer=tn(f"alarm.dauer.{dauer[0]}", dauer[1], lang))
        assert satz in text


class _Warnquelle:
    """Echte amtliche Quelle in der echten Registry (kein Mock)."""

    name = "p9b-quelle"

    def covers(self, lat, lon) -> bool:
        return abs(lat - LAT) < 0.05 and abs(lon - LON) < 0.05

    def fetch(self, lat, lon):
        from services.official_alerts import OfficialAlert

        jetzt = datetime.now(timezone.utc)
        return [OfficialAlert(source=self.name, hazard="thunderstorm", level=3, label="Gewitter",
                              valid_from=jetzt - timedelta(hours=1),
                              valid_to=jetzt + timedelta(hours=23), region_label="Testregion")]


def test_ortsvergleich_amtliche_warnung_in_nutzersprache():
    import services.official_alerts.base as basis
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    sicherung = list(basis._REGISTERED_SOURCES)
    basis._REGISTERED_SOURCES.clear()
    texte = {}
    try:
        register_official_alert_source(_Warnquelle())
        with freeze_time(JETZT):
            for lang in ("en", "de"):
                uid = f"p9b-cmp-amtlich-{lang}"
                _nutzer(uid, lang)
                _ort_und_preset(uid)
                post: list = []
                CompareOfficialAlertService(
                    settings=ng.settings_email_only(), user_id=uid,
                    mail_sink=lambda subject, body: post.append(body),
                ).check_all_compare_presets()
                assert post, lang
                texte[lang] = post[0]
    finally:
        basis._REGISTERED_SOURCES.clear()
        basis._REGISTERED_SOURCES.extend(sicherung)
    for lang, text in texte.items():
        assert t("versand.kontext.ortsvergleich", lang) in text
    assert t("versand.kontext.ortsvergleich", "de") not in texte["en"]
