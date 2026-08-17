"""TDD RED — Issue #1714: Ortsvergleich-Briefing vermerkt gezeigte amtliche
Warnungen nicht im Melde-Gedaechtnis (`official_alert:`-Namensraum).

SPEC: docs/specs/modules/fix_1714_compare_alert_briefing_reset.md (AC-1..AC-7)
Trip-Vorbild: `tests/tdd/test_alert_state_briefing_reset.py` (Issue #1614 Teil 1),
`record_official_alerts_reported` selbst bleibt unveraendert (bereits produktiv).

RED-Ursache (heute): `send_one_compare_preset`
(`services/scheduler_dispatch_service.py`) ruft `record_official_alerts_reported`
an keiner Stelle auf. Alle Tests unten muessen deshalb heute rot sein — entweder
weil der `official_alert:`-Eintrag im Melde-Gedaechtnis fehlt (AC-1, AC-5, AC-6),
oder weil der unabhaengige Checker eine unveraenderte Warnung erneut meldet
(AC-1 als Kern-Regressionsschutz).

Testpolitik: kein Mock-Theater. Alle Naehte sind entweder echte, kleine
Implementierungen desselben Protokolls (Vergleichs-Engine, Wetterquelle des
Δ-Anker-Schreibers, amtliche Warnquelle) oder echte Zustands-Dateien auf
Platte — Haus-Muster aus `test_compare_briefing_anchor_and_memory_reset.py`
und `test_compare_official_alert.py`.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
from app.user import SavedLocation
from services.official_alerts.models import OfficialAlert

from tests.helpers.compare_briefings import write_compare_briefings

TARGET_DATE = date.today()

_NOW = datetime.now(timezone.utc)
_VALID_FROM = _NOW - timedelta(hours=1)
_VALID_TO = _NOW + timedelta(hours=23, minutes=59)

# Versand-Sicherheit (#1477): `Settings(...)` faellt bei fehlenden Feldern
# still auf die Prod-`.env` im Worktree zurueck — alle Transport-Felder daher
# ausdruecklich auf unbrauchbare Werte gesetzt.
_NO_TRANSPORT_FIELDS: dict = {
    "smtp_host": "dummy.invalid", "smtp_user": "dummy", "smtp_pass": "dummy",
    "mail_to": "tdd-1714-dummy@example.invalid",
    "test_smtp_host": "dummy.invalid", "test_smtp_user": "dummy",
    "test_smtp_pass": "dummy", "test_mail_from": "tdd-1714-dummy@example.invalid",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}

_BROKEN_EMAIL_FIELDS: dict = {
    "smtp_host": "", "smtp_user": "", "smtp_pass": "",
    "mail_to": "tdd-1714-dummy@example.invalid",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}


def _settings_email_only() -> Settings:
    return Settings(**_NO_TRANSPORT_FIELDS)


def _settings_email_broken() -> Settings:
    """Echte, unvollstaendige SMTP-Konfiguration -- `EmailOutput` wirft den
    echten `OutputConfigError`, ohne je Netz zu benutzen (AC-4)."""
    settings = Settings(**_BROKEN_EMAIL_FIELDS)
    assert settings.can_send_email() is False
    assert settings.can_send_telegram() is False
    assert settings.can_send_sms() is False
    return settings


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _point(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float):
    """Echtes `PointWeatherData`-DTO (kein Mock)."""
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="tdd-1714",
    )


class _ScriptedWeatherSource:
    """Echte `LocationWeatherSource`-Implementierung (kein Mock) fuer den
    Δ-Anker-Schreiber, netzfrei."""

    def __init__(self, values: dict[str, float], names: dict[str, str]) -> None:
        self.values = dict(values)
        self._names = dict(names)
        self.fetch_calls: list[str] = []

    def fetch(self, point_id: str, lat: float, lon: float,
              start_hour: int | None = None, end_hour: int | None = None,
              target_date=None, tage_ab_ortstag=None):
        self.fetch_calls.append(point_id)
        return _point(point_id, self._names.get(point_id, point_id), lat, lon,
                      precip_sum_mm=self.values.get(point_id, 0.0))


def _preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    preset = {
        "id": preset_id, "name": preset_id, "location_ids": list(location_ids),
        "schedule": "daily", "weekday": 4, "profil": "ALLGEMEIN",
        "hour_from": 9, "hour_to": 16,
        "empfaenger": ["tdd-1714-dummy@example.invalid"],
        "letzter_versand": None, "top_ort_letzter_versand": None,
        "created_at": "2026-08-17T00:00:00Z", "kind": "vergleich",
    }
    preset.update(extra)
    return preset


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=22.0, wind_chill_c=21.0, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=0.0, cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


def _official_alert(*, hazard="thunderstorm", level=2, region="Testregion",
                     vf=None, vt=None) -> OfficialAlert:
    return OfficialAlert(
        source="test-1714", hazard=hazard, level=level, label="Testwarnung",
        valid_from=vf or _VALID_FROM, valid_to=vt or _VALID_TO,
        region_label=region,
    )


def _install_comparison_engine_seam(monkeypatch, alerts_by_loc: dict | None = None) -> None:
    """Ersetzt NUR die teure Upstream-Abhaengigkeit `ComparisonEngine.run`
    durch eine echte Unterklasse mit festen Werten — Haus-Muster aus
    `test_compare_briefing_anchor_and_memory_reset.py`. `alerts_by_loc`
    (#1714, neu) laesst je Ort steuern, welche amtlichen Warnungen im
    Briefing GEZEIGT werden — genau die Menge, die die neue Record-Logik
    ans Melde-Gedaechtnis melden soll."""
    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    alerts_by_loc = alerts_by_loc or {}
    original = ce_mod.ComparisonEngine

    class _FixedEngine(original):  # echte Unterklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=loc, score=90 - 5 * i, temp_max=22.0 + i, temp_min=12.0,
                        wind_max=11.0, gust_max=19.0, cloud_avg=35, sunny_hours=6,
                        official_alerts=list(alerts_by_loc.get(loc.id, [])),
                        hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for i, loc in enumerate(list(locations or []))
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _FixedEngine)


def _install_anchor_weather_seam(monkeypatch, source: _ScriptedWeatherSource) -> None:
    """Der Δ-Anker-Schreiber (`_write_compare_alert_snapshots`) baut sich seine
    Wetterquelle selbst (Netz). Hier wird die KLASSE im Quellmodul durch eine
    gleichwertige, netzfreie Implementierung ersetzt."""
    import services.compare_location_weather_source as clws_mod

    class _SourceFactory:
        def __new__(cls, *args, **kwargs):
            return source

    monkeypatch.setattr(clws_mod, "CompareLocationWeatherSource", _SourceFactory)


class _FakeOfficialAlertSource:
    """Echte Quelle (kein Mock), strukturelles Subtyping — Muster
    `test_compare_official_alert.py`."""

    def __init__(self, lat, lon, alerts):
        self._lat, self._lon, self._alerts = lat, lon, alerts
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-1714-source"

    def covers(self, lat, lon) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat, lon):
        self.fetch_calls += 1
        return list(self._alerts)


def _sources_backup():
    import services.official_alerts.base as b
    return b, list(b._REGISTERED_SOURCES)


def _memory_state(user_id: str, preset_id: str, loc_id: str) -> dict:
    from services.alert_state import AlertStateService

    return AlertStateService(user_id=user_id).load(f"{preset_id}:{loc_id}")


@pytest.fixture
def compare_env(tmp_path, monkeypatch):
    """Isoliertes Arbeitsverzeichnis (Muster
    `test_compare_briefing_anchor_and_memory_reset.py::compare_env`)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "users").mkdir(parents=True, exist_ok=True)
    return tmp_path


# ══════════════════════════════════ AC-1 ═════════════════════════════════════


def test_briefing_meldet_unveraenderte_amtliche_warnung_danach_nicht_erneut(
    compare_env, monkeypatch,
):
    """AC-1 — Kern-Regressionsschutz gegen den im Issue beschriebenen
    Doppelversand.

    GIVEN ein Compare-Briefing wurde erfolgreich mit einer amtlichen Warnung
          fuer einen Ort versendet.
    WHEN  der naechste Lauf von `compare_official_alert.py` fuer denselben
          Ort mit unveraenderter Warnung (gleiches Level) laeuft.
    THEN  meldet der Checker diese Warnung NICHT erneut als eigenstaendigen
          Alarm.
    """
    from app.loader import get_data_root, save_location
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-1714-ac1-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1714-ac1-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-1714-a", "Alpenort", 47.0, 11.0)
    save_location(loc, user_id=uid)
    write_compare_briefings(get_data_root() / "users" / uid, [_preset(preset_id, [loc.id])])

    alert = _official_alert()
    settings = _settings_email_only()
    _install_comparison_engine_seam(monkeypatch, {loc.id: [alert]})
    _install_anchor_weather_seam(monkeypatch, _ScriptedWeatherSource({loc.id: 5.0}, {loc.id: loc.name}))

    mail_calls: list = []
    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: mail_calls.append(subject),
    )
    assert mail_calls, "Vorbedingung: der Briefing-Versand muss ausgeloest werden"

    state = _memory_state(uid, preset_id, loc.id)
    assert any(k.startswith("official_alert:") for k in state), (
        f"Nach erfolgreichem Versand fehlt der official_alert:-Eintrag im "
        f"Melde-Gedaechtnis: {list(state)!r} (AC-1)"
    )

    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FakeOfficialAlertSource(loc.lat, loc.lon, [alert]))
        checker_mails: list = []
        sent = CompareOfficialAlertService(
            settings=settings, user_id=uid,
            mail_sink=lambda subject, body: checker_mails.append(subject),
        ).check_all_compare_presets()

        assert sent == 0, (
            f"Eine bereits im Briefing gemeldete, unveraenderte Warnung darf "
            f"der unabhaengige Checker nicht erneut als eigenen Alarm melden, "
            f"erhalten: {sent} Zustellung(en) (AC-1)"
        )
        assert checker_mails == [], f"Unerwarteter Alarm-Versand: {checker_mails!r} (AC-1)"
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)


# ══════════════════════════════════ AC-2 ═════════════════════════════════════


def test_eskalierte_warnung_wird_trotz_bereits_gemeldeter_unveraenderter_warnung_weiterhin_gemeldet(
    compare_env, monkeypatch,
):
    """AC-2 — Eskalations-Gegenprobe zu AC-1.

    GIVEN dieselbe Ausgangslage wie AC-1 (Warnung bereits im Melde-Gedaechtnis
          vermerkt).
    WHEN  die Warnung danach auf ein hoeheres Level eskaliert.
    THEN  meldet der Checker die eskalierte Warnung weiterhin als neuen
          Trigger — der neue Doppelversand-Schutz darf eine echte
          Verschaerfung nicht stumm schalten.
    """
    from app.loader import get_data_root, save_location
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-1714-ac2-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1714-ac2-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-1714-b", "Bergort", 47.5, 11.5)
    save_location(loc, user_id=uid)
    write_compare_briefings(get_data_root() / "users" / uid, [_preset(preset_id, [loc.id])])

    alert = _official_alert(level=2)
    settings = _settings_email_only()
    _install_comparison_engine_seam(monkeypatch, {loc.id: [alert]})
    _install_anchor_weather_seam(monkeypatch, _ScriptedWeatherSource({loc.id: 5.0}, {loc.id: loc.name}))

    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )
    state = _memory_state(uid, preset_id, loc.id)
    assert any(k.startswith("official_alert:") for k in state), (
        "Vorbedingung: der Briefing-Versand muss die Warnung vermerken"
    )

    escalated = _official_alert(level=3, vf=alert.valid_from, vt=alert.valid_to)

    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FakeOfficialAlertSource(loc.lat, loc.lon, [escalated]))
        checker_mails: list = []
        sent = CompareOfficialAlertService(
            settings=settings, user_id=uid,
            mail_sink=lambda subject, body: checker_mails.append(subject),
        ).check_all_compare_presets()

        assert sent == 1, (
            f"Eine echte Eskalation muss trotz bereits gemeldeter unveraenderter "
            f"Warnung weiterhin gemeldet werden, erhalten: {sent} (AC-2)"
        )
        assert len(checker_mails) == 1
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)


# ══════════════════════════════════ AC-3 ═════════════════════════════════════


def test_ad_hoc_abruf_schreibt_das_melde_gedaechtnis_amtlicher_warnungen_nicht(
    compare_env, monkeypatch,
):
    """AC-3 — Handversand (#1007) bleibt read-only fuers Melde-Gedaechtnis."""
    from app.loader import get_data_root, save_location
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-1714-ac3-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1714-ac3-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-1714-c", "Talort", 48.0, 12.0)
    save_location(loc, user_id=uid)
    write_compare_briefings(get_data_root() / "users" / uid, [_preset(preset_id, [loc.id])])

    alert = _official_alert()
    settings = _settings_email_only()
    _install_comparison_engine_seam(monkeypatch, {loc.id: [alert]})
    _install_anchor_weather_seam(monkeypatch, _ScriptedWeatherSource({loc.id: 5.0}, {loc.id: loc.name}))

    before = _memory_state(uid, preset_id, loc.id)
    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
        on_demand=True,
    )
    after = _memory_state(uid, preset_id, loc.id)

    assert after == before == {}, (
        f"Ein Handversand (on_demand=True) darf das Melde-Gedaechtnis nicht "
        f"anfassen (#1007), gefunden: {after!r} (AC-3)"
    )

    # Positive Gegenprobe (Muster Trip-Vorbild): derselbe Aufbau OHNE
    # Ad-hoc-Kennzeichen MUSS den Eintrag setzen. Ohne diese Gegenprobe waere
    # die leere Erwartung oben auch dann erfuellt, wenn die neue Record-Logik
    # ueberhaupt nie verdrahtet worden waere.
    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
        on_demand=False,
    )
    regular = _memory_state(uid, preset_id, loc.id)
    assert any(k.startswith("official_alert:") for k in regular), (
        f"Gegenprobe: der REGULAERE Versand (on_demand=False) muss die Warnung "
        f"vermerken, gefunden: {list(regular)!r} (AC-3)"
    )


# ══════════════════════════════════ AC-4 ═════════════════════════════════════


def test_fehlgeschlagener_versand_schreibt_das_melde_gedaechtnis_nicht(
    compare_env, monkeypatch,
):
    """AC-4 — ein gescheiterter Versand darf eine nie zugestellte Warnung
    nicht faelschlich als 'gemeldet' vermerken."""
    from app.loader import get_data_root, save_location
    from output.channels.base import OutputConfigError
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-1714-ac4-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1714-ac4-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-1714-d", "Fehlerort", 48.5, 12.5)
    save_location(loc, user_id=uid)
    write_compare_briefings(get_data_root() / "users" / uid, [_preset(preset_id, [loc.id])])

    alert = _official_alert()
    settings = _settings_email_broken()
    _install_comparison_engine_seam(monkeypatch, {loc.id: [alert]})
    _install_anchor_weather_seam(monkeypatch, _ScriptedWeatherSource({loc.id: 5.0}, {loc.id: loc.name}))

    with pytest.raises(OutputConfigError):
        send_one_compare_preset(
            _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
            all_locations_cache=[loc], target_date=TARGET_DATE, tage_ab_ortstag=0,
        )

    state = _memory_state(uid, preset_id, loc.id)
    assert not any(k.startswith("official_alert:") for k in state), (
        f"Ein gescheiterter Versand darf keinen official_alert:-Eintrag "
        f"hinterlassen: {list(state)!r} (AC-4)"
    )

    # Positive Gegenprobe: derselbe Ort/dieselbe Warnung, aber ein GELINGENDER
    # Versand MUSS den Eintrag setzen. Ohne sie waere die leere Erwartung oben
    # auch dann erfuellt, wenn die neue Record-Logik nie verdrahtet worden waere.
    working_settings = _settings_email_only()
    send_one_compare_preset(
        _preset(preset_id, [loc.id]), working_settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )
    regular = _memory_state(uid, preset_id, loc.id)
    assert any(k.startswith("official_alert:") for k in regular), (
        f"Gegenprobe: ein GELINGENDER Versand mit derselben Warnung muss den "
        f"Eintrag setzen, gefunden: {list(regular)!r} (AC-4)"
    )


# ══════════════════════════════════ AC-5 ═════════════════════════════════════


def test_zwei_nutzer_bleiben_im_melde_gedaechtnis_getrennt(compare_env, monkeypatch):
    """AC-5 — Mandantentrennung (CLAUDE.md-Pflicht)."""
    from app.loader import get_data_root, save_location
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid_a = f"tdd-1714-ac5-a-{uuid.uuid4().hex[:6]}"
    uid_b = f"tdd-1714-ac5-b-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1714-ac5-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-1714-e", "Zwillingsort", 46.9, 10.9)
    save_location(loc, user_id=uid_a)
    save_location(loc, user_id=uid_b)
    write_compare_briefings(get_data_root() / "users" / uid_a, [_preset(preset_id, [loc.id])])
    write_compare_briefings(get_data_root() / "users" / uid_b, [_preset(preset_id, [loc.id])])

    alert = _official_alert()
    settings = _settings_email_only()
    _install_comparison_engine_seam(monkeypatch, {loc.id: [alert]})
    _install_anchor_weather_seam(monkeypatch, _ScriptedWeatherSource({loc.id: 5.0}, {loc.id: loc.name}))

    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid_a, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )

    state_a = _memory_state(uid_a, preset_id, loc.id)
    state_b = _memory_state(uid_b, preset_id, loc.id)
    assert any(k.startswith("official_alert:") for k in state_a), (
        f"Vorbedingung: Nutzer A muss den Eintrag erhalten: {list(state_a)!r}"
    )
    assert state_b == {}, (
        f"Der erfolgreiche Versand fuer Nutzer A darf das Melde-Gedaechtnis von "
        f"Nutzer B nicht beruehren, gefunden: {state_b!r} (AC-5)"
    )


# ══════════════════════════════════ AC-6 ═════════════════════════════════════


def test_zwei_orte_im_preset_beeinflussen_sich_im_melde_gedaechtnis_nicht_gegenseitig(
    compare_env, monkeypatch,
):
    """AC-6 — R3-Analogie: kein Cross-Orts-Ueberschreiben."""
    from app.loader import get_data_root, save_location
    from output.renderers.alert.official_alerts import (
        official_alert_state_entry,
        official_alert_state_key,
    )
    from services.alert_state import AlertStateService
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-1714-ac6-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1714-ac6-{uuid.uuid4().hex[:6]}"
    loc_warn = _location("loc-1714-f1", "Warnort", 47.1, 11.1)
    loc_quiet = _location("loc-1714-f2", "Ruhigort", 47.2, 11.2)
    save_location(loc_warn, user_id=uid)
    save_location(loc_quiet, user_id=uid)
    write_compare_briefings(
        get_data_root() / "users" / uid,
        [_preset(preset_id, [loc_warn.id, loc_quiet.id])],
    )

    # Vorbestehender Melde-Gedaechtnis-Eintrag am ruhigen Ort, zu einer
    # ANDEREN Warnung gehoerend als die am Warnort gezeigte — darf nicht
    # angefasst werden (echtes Cross-Orts-Ueberschreiben, nicht nur ein
    # fremder State-Key).
    existing_alert = _official_alert(hazard="snow", level=1, region="Andere Region")
    existing_key = official_alert_state_key(existing_alert)
    existing_entry = official_alert_state_entry(existing_alert, "2026-08-01T00:00:00+00:00")
    AlertStateService(user_id=uid).save(
        f"{preset_id}:{loc_quiet.id}", {existing_key: dict(existing_entry)}
    )

    alert = _official_alert()
    settings = _settings_email_only()
    _install_comparison_engine_seam(monkeypatch, {loc_warn.id: [alert]})  # loc_quiet: []
    source = _ScriptedWeatherSource(
        {loc_warn.id: 5.0, loc_quiet.id: 3.0},
        {loc_warn.id: loc_warn.name, loc_quiet.id: loc_quiet.name},
    )
    _install_anchor_weather_seam(monkeypatch, source)

    send_one_compare_preset(
        _preset(preset_id, [loc_warn.id, loc_quiet.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc_warn, loc_quiet], target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )

    state_warn = _memory_state(uid, preset_id, loc_warn.id)
    state_quiet = _memory_state(uid, preset_id, loc_quiet.id)
    assert any(k.startswith("official_alert:") for k in state_warn), (
        f"Der Ort mit gezeigter Warnung muss einen Eintrag erhalten: {list(state_warn)!r}"
    )
    assert state_quiet == {existing_key: existing_entry}, (
        f"Der bestehende Eintrag des anderen Ortes darf nicht ueberschrieben "
        f"oder geloescht werden, gefunden: {state_quiet!r} (AC-6)"
    )


# ══════════════════════════════════ AC-7 ═════════════════════════════════════


def test_preset_ohne_gezeigte_warnungen_loest_keinen_schreibzugriff_aus(
    compare_env, monkeypatch,
):
    """AC-7 — Fail-soft No-Op, kein unnoetiger State-Write."""
    import services.alert_briefing_anchor as anchor_mod
    from app.loader import get_data_root, save_location
    from services.scheduler_dispatch_service import send_one_compare_preset

    uid = f"tdd-1714-ac7-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-1714-ac7-{uuid.uuid4().hex[:6]}"
    loc = _location("loc-1714-g", "Klarort", 47.3, 11.3)
    save_location(loc, user_id=uid)
    write_compare_briefings(get_data_root() / "users" / uid, [_preset(preset_id, [loc.id])])

    calls: list = []
    original = anchor_mod.record_official_alerts_reported

    def _spy(*, user_id, entity_id, alerts):
        calls.append((user_id, entity_id, list(alerts)))
        return original(user_id=user_id, entity_id=entity_id, alerts=alerts)

    monkeypatch.setattr(anchor_mod, "record_official_alerts_reported", _spy)

    settings = _settings_email_only()
    _install_comparison_engine_seam(monkeypatch, {})  # keine Warnungen an keinem Ort
    _install_anchor_weather_seam(monkeypatch, _ScriptedWeatherSource({loc.id: 5.0}, {loc.id: loc.name}))

    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )

    assert calls == [], (
        f"Ein Briefing ohne gezeigte amtliche Warnungen darf die Record-Funktion "
        f"kein einziges Mal aufrufen: {calls!r} (AC-7)"
    )
    state = _memory_state(uid, preset_id, loc.id)
    assert not any(k.startswith("official_alert:") for k in state), (
        f"Kein official_alert:-Eintrag erwartet: {list(state)!r} (AC-7)"
    )

    # Positive Gegenprobe: derselbe Aufbau MIT gezeigter Warnung MUSS die
    # Record-Funktion genau einmal aufrufen. Ohne sie waere `calls == []` auch
    # dann erfuellt, wenn der Spy nie einen echten Aufruf sehen wuerde (z.B.
    # weil die neue Record-Logik nie verdrahtet worden waere).
    _install_comparison_engine_seam(monkeypatch, {loc.id: [_official_alert()]})
    send_one_compare_preset(
        _preset(preset_id, [loc.id]), settings, uid, str(compare_env / "data"),
        all_locations_cache=[loc], target_date=TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: None,
    )
    assert len(calls) == 1, (
        f"Gegenprobe: ein Briefing MIT gezeigter Warnung muss die Record-Funktion "
        f"genau einmal aufrufen, gefunden: {calls!r} (AC-7)"
    )
