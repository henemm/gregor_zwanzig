"""TDD RED — Issue #1258 Scheibe S1 (AC-7, AC-8): `official_warnings.sources`
filtert amtliche Warnungen im Ortsvergleich VOR der Alarmentscheidung.

Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md,
Sektion „Implementation Details" Nr. 1+3 + AC-7/AC-8.

Quellen-Vokabular verifiziert gegen den Code (Known-Limitation-Hinweis der
Spec, „exaktes String-Vokabular ... anhand OfficialAlertSource.name
verifizieren"): `OfficialAlert.source` UND `OfficialAlertSource.name`
tragen bei allen 5 registrierten Quellen denselben String (s.
src/services/official_alerts/{vigilance,geosphere_warn}.py `name`-Property
== dort gesetzter `source=`-Wert), z.B. "meteofrance_vigilance",
"geosphere_warn". Der Filter in `official_warnings.sources[]` vergleicht
daher gegen `OfficialAlert.source`.

Struktureller Vorbild: tests/tdd/test_compare_official_alert.py (echte
Fake-Quellen, register_official_alert_source(), echte Presets/Orte auf
Platte, mail_sink-DI-Seam). NO MOCKS.

RED heute: `CompareOfficialAlertService` kennt `official_warnings.sources`
noch nicht -> beide Quellen fliessen ungefiltert in den Alarm ein, beide
Labels erscheinen im Mail-Body (AssertionError, kein Crash).
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.loader import save_location
from app.user import SavedLocation
from services.official_alerts.models import OfficialAlert

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

LAT_A, LON_A = 46.62, 13.68  # Hermagor


def _clean_user(user_id: str) -> None:
    d = DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _uid(prefix: str) -> str:
    return f"tdd-1258-srcfilter-{prefix}-{uuid.uuid4().hex[:6]}"


def _settings_all_channels() -> Settings:
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _preset(preset_id: str, official_warnings: dict, **extra) -> dict:
    p: dict = {
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": ["loc-a"], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["e@x.invalid"], "created_at": "2026-07-15T00:00:00Z",
        "official_warnings": official_warnings,
    }
    p.update(extra)
    return p


def _write_presets(user_id: str, presets: list[dict]) -> None:
    p = DATA_ROOT / user_id / "compare_presets.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(presets, ensure_ascii=False), encoding="utf-8")


class _FixedSourceAlertSource:
    """Echte Quelle (kein Mock): liefert genau einen Alert mit einem festen,
    registry-echten `source`-Wert; zaehlt fetch()-Aufrufe."""

    def __init__(self, lat: float, lon: float, alert: OfficialAlert) -> None:
        self._lat, self._lon, self._alert = lat, lon, alert
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return self._alert.source

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        return [self._alert]


def _vigilance_alert() -> OfficialAlert:
    return OfficialAlert(
        source="meteofrance_vigilance", hazard="thunderstorm", level=3,
        label="Vigilance-Warnung (#1258 AC-7 — MUSS erscheinen)",
        valid_from=datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc),
        valid_to=datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc),
        region_label="Hermagor",
    )


def _geosphere_alert() -> OfficialAlert:
    return OfficialAlert(
        source="geosphere_warn", hazard="wind", level=2,
        label="GeoSphere-Warnung (#1258 AC-7 — darf NICHT erscheinen)",
        valid_from=datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc),
        valid_to=datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc),
        region_label="Hermagor",
    )


def _sources_backup():
    import services.official_alerts.base as b
    return b, list(b._REGISTERED_SOURCES)


# ═══════════════════════════════ AC-7 ════════════════════════════════════════

def test_ac7_sources_filter_restricts_alarm_to_named_source():
    """AC-7: `official_warnings.sources = ["meteofrance_vigilance"]` -> nur
    Warnungen dieser Quelle fliessen in die Alarmentscheidung ein, die
    zweite Quelle (geosphere_warn, anderer hazard -> kein Cross-Source-
    Dedupe-Kollaps) wird ignoriert.

    RED heute: der Filter existiert nicht -> beide Labels erscheinen im
    Mail-Body.
    """
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac7")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p1", official_warnings={"enabled": True, "sources": ["meteofrance_vigilance"]},
        )])
        vigilance_alert = _vigilance_alert()
        geosphere_alert = _geosphere_alert()
        vigilance_src = _FixedSourceAlertSource(LAT_A, LON_A, vigilance_alert)
        geosphere_src = _FixedSourceAlertSource(LAT_A, LON_A, geosphere_alert)
        register_official_alert_source(vigilance_src)
        register_official_alert_source(geosphere_src)

        mail_calls: list = []
        sent = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
        ).check_all_compare_presets()

        assert sent == 1, f"Erwartet genau 1 gebuendelter Alarm (gefilterte Quelle), erhalten: {sent}"
        assert len(mail_calls) == 1
        body = mail_calls[0]
        assert vigilance_alert.label in body, (
            f"Die gefilterte Quelle (meteofrance_vigilance) MUSS im Alarm erscheinen: {body!r}"
        )
        assert geosphere_alert.label not in body, (
            f"Die NICHT gefilterte Quelle (geosphere_warn) darf NICHT im Alarm erscheinen: {body!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════════════════════════ AC-8 ════════════════════════════════════════

def test_ac8_unset_sources_considers_all_sources_unfiltered():
    """AC-8: `official_warnings.sources` ist nicht gesetzt (leer/fehlend) ->
    weiterhin ALLE registrierten Quellen fliessen ein — unveraendertes
    Verhalten gegenueber der Vor-Migration-Zeit.

    Legacy-Feld wird hier BEWUSST auf `false` gesetzt (Konflikt-Fixture,
    analog AC-6 fuer Trips): nur so ist der Test heute wirklich rot — ein
    Preset ohne gesetztes Legacy-Feld wuerde ueber den heutigen
    Default-True-Pfad zufaellig schon senden, ohne dass die Pipeline das
    neue Feld tatsaechlich liest.

    RED: die Compare-Pipeline liest weiterhin ausschliesslich
    `official_alert_triggers_enabled` -> das hier gesetzte `false` blockt
    den Versand komplett (sent=0 statt 1), obwohl `official_warnings.enabled`
    true ist.
    """
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac8")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-a", "Hermagor", LAT_A, LON_A), user_id=uid)
        _write_presets(uid, [_preset(
            "p1", official_warnings={"enabled": True},
            official_alert_triggers_enabled=False,
        )])
        vigilance_alert = _vigilance_alert()
        geosphere_alert = _geosphere_alert()
        register_official_alert_source(_FixedSourceAlertSource(LAT_A, LON_A, vigilance_alert))
        register_official_alert_source(_FixedSourceAlertSource(LAT_A, LON_A, geosphere_alert))

        mail_calls: list = []
        sent = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append(body),
        ).check_all_compare_presets()

        assert sent == 1, (
            f"official_warnings.enabled=true muss den Alarm ausloesen, obwohl das "
            f"Legacy-Feld false ist (Pipeline muss das neue Feld als Gate lesen "
            f"statt official_alert_triggers_enabled), erhalten: {sent}"
        )
        assert len(mail_calls) == 1
        body = mail_calls[0]
        assert vigilance_alert.label in body, f"Ohne sources-Filter muessen ALLE Quellen erscheinen: {body!r}"
        assert geosphere_alert.label in body, f"Ohne sources-Filter muessen ALLE Quellen erscheinen: {body!r}"
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)
