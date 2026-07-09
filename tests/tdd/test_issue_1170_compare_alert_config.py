"""TDD RED — Issue #1170: Trip-benannte Alarm-Konfiguration im Orts-Vergleich
(Scheibe 3/3, Epic #1095, AC-5).

SPEC: docs/specs/modules/issue_1170_compare_alert_config.md

RED-Grund: `CompareAlertService._build_eval_config()`
(`src/services/compare_alert.py:149-159`) liest die Alarm-Empfindlichkeit
heute per `preset.get("metric_alert_levels")` — einem TOP-LEVEL-Key, den kein
Compare-Preset je setzt. Trip-Konfigurationsseiten speichern die
Empfindlichkeit stattdessen unter `display_config.metric_alert_levels`
(analog zu `UnifiedWeatherDisplayConfig` bei Trips). Für ein Compare-Preset
mit einem SO gespeicherten Level liest `compare_alert.py` also stets `None`
→ fällt auf `_STANDARD_METRIC_LEVELS` (alles "standard") zurück → die vom
Nutzer gewählte Empfindlichkeit ("sensibel"/"entspannt") wird komplett
ignoriert. Das ist ein Key-/Location-Mismatch zwischen dem, was die
Konfigurationsseite schreibt, und dem, was der Service liest.

Diese Datei beweist das mit zwei Δ-Szenarien, die je nach tatsächlich
verwendeter Schwelle (aus `_PRESET_TABLE` in `services/alert_preset.py`:
precipitation_sum entspannt=20 / standard=10 / sensibel=5) unterschiedlich
ausgehen — RED heute, weil der Service faktisch immer "standard" (10)
verwendet, unabhängig vom gespeicherten Preset-Level.

Mock-freie Test-Seams 1:1 aus `test_issue_1169_compare_alert_consumer.py`
übernommen (`_ScriptedWeatherSource`, `_point`, `_location`, `_clean_user`,
`_write_preset_file`, `_settings_email_capable_dummy`, `mail_sink`-Capture-
Seam auf `CompareAlertService`) — keine Mocks, kein Netz, echte
Preset-/Snapshot-Dateien unter `data/users/tdd-1170-*`.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.user import SavedLocation

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


# ───────────────────────── Helfer (1:1 aus test_issue_1169) ─────────────────

def _clean_user(user_id: str) -> None:
    import shutil

    d = DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d)


def _settings_email_capable_dummy() -> Settings:
    """`can_send_email() == True` ohne echten Netzwerkzugriff — für
    `mail_sink`-Captures (kein SMTP-Dial, siehe
    `notification_service.py:475-489`)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _location(loc_id: str, name: str, lat: float, lon: float, elevation_m: int = 1000) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=elevation_m)


def _point(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float = 0.0,
           provider: str = "test-scripted"):
    """Echtes `PointWeatherData`-DTO (kein Mock)."""
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider=provider,
    )


class _ScriptedWeatherSource:
    """Deterministischer `LocationWeatherSource`-Impl — 1:1 aus
    `test_issue_1169_compare_alert_consumer.py`. Kein `Mock()`/`patch()`: ein
    Konfigurations-Seam, der echte `PointWeatherData` mit vorab festgelegten
    Werten liefert."""

    def __init__(self, values: dict[str, float]) -> None:
        self._values = dict(values)

    def fetch(self, point_id: str, lat: float, lon: float):
        return _point(point_id, point_id, lat, lon, precip_sum_mm=self._values.get(point_id, 0.0))


def _preset_with_alert_levels(
    preset_id: str, location_ids: list[str], empfaenger: list[str],
    metric_alert_levels: dict[str, str], cooldown_minutes: int | None = None,
) -> dict:
    """Compare-Preset-Dict mit Trip-benannter Alarm-Konfiguration unter
    `display_config.metric_alert_levels` (analog `UnifiedWeatherDisplayConfig`
    bei Trips) — NICHT unter dem Top-Level-Key `metric_alert_levels`, den
    `compare_alert.py._build_eval_config()` heute liest. Genau dieser
    Key-/Location-Mismatch ist der RED-Beweis dieser Datei."""
    preset = {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": location_ids,
        "schedule": "manual",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": empfaenger,
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-07-09T00:00:00Z",
        "display_config": {"metric_alert_levels": dict(metric_alert_levels)},
    }
    if cooldown_minutes is not None:
        preset["cooldown_minutes"] = cooldown_minutes
    return preset


def _write_preset_file(user_id: str, presets: list[dict]) -> Path:
    path = DATA_ROOT / user_id / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, ensure_ascii=False), encoding="utf-8")
    return path


def _preset_multi(preset_id: str, location_ids: list[str], empfaenger: list[str]) -> dict:
    """Compare-Preset-Dict ohne Alarm-Konfigurations-Override — reine
    Bündelungs-Fixture (AC-7), Standard-Empfindlichkeit (Schwelle 10) genügt."""
    return {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": location_ids,
        "schedule": "manual",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": empfaenger,
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-07-09T00:00:00Z",
    }


# ═══════════════════════════════ AC-5 ════════════════════════════════════════

def test_ac5_stored_sensibel_level_makes_alert_more_sensitive():
    """AC-5 GIVEN ein Compare-Preset mit gespeicherter Trip-benannter Alarm-
    Konfiguration `display_config.metric_alert_levels = {"precipitation_sum":
    "sensibel"}` (Schwelle 5 mm, `alert_preset.py::_PRESET_TABLE`) und einem
    Δ-Anker von 2,0 mm.

    WHEN ein frischer Fetch 9,0 mm liefert (Δ=7, ≥ Schwelle 5, aber < der
    Standard-Schwelle 10) und `CompareAlertService.check_all_compare_presets()`
    läuft.

    THEN muss GENAU EIN Alarm versendet werden — die gespeicherte
    Empfindlichkeit "sensibel" muss tatsächlich verwendet werden.

    RED heute: `compare_alert.py._build_eval_config()` liest
    `preset.get("metric_alert_levels")` (Top-Level) statt aus
    `display_config` → findet `None` → fällt auf `_STANDARD_METRIC_LEVELS`
    zurück (Schwelle 10 statt 5) → Δ=7 < 10 → KEIN Alarm → `sent == 0` statt
    des erwarteten `1`. Der gespeicherte Sensibilitäts-Wert wird komplett
    ignoriert.
    """
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from app.loader import save_location

    uid = "tdd-1170-ac5-sensibel"
    _clean_user(uid)
    preset_id = "cp-1170-sensibel"
    try:
        loc = _location("loc-s", "SensibelOrt", 47.0, 11.0)
        save_location(loc, user_id=uid)
        _write_preset_file(uid, [
            _preset_with_alert_levels(
                preset_id, ["loc-s"], ["gregor-test@henemm.com"],
                metric_alert_levels={"precipitation_sum": "sensibel"},
            )
        ])

        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-s", _point("loc-s", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _ScriptedWeatherSource({"loc-s": 9.0})  # Δ=7: >= sensibel(5), < standard(10)

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = service.check_all_compare_presets()

        assert sent == 1, (
            f"Gespeicherte Empfindlichkeit 'sensibel' (Schwelle 5) wurde ignoriert — "
            f"erwartet 1 Alarm bei Δ=7, erhalten: {sent}. Der Service liest die "
            "Alarm-Konfiguration offenbar nicht aus display_config.metric_alert_levels."
        )
        assert len(sent_subjects) == 1
    finally:
        _clean_user(uid)


def test_ac5_stored_entspannt_level_makes_alert_less_sensitive():
    """AC-5 GIVEN ein Compare-Preset mit gespeicherter Trip-benannter Alarm-
    Konfiguration `display_config.metric_alert_levels = {"precipitation_sum":
    "entspannt"}` (Schwelle 20 mm) und einem Δ-Anker von 2,0 mm.

    WHEN ein frischer Fetch 16,0 mm liefert (Δ=14, < Schwelle 20, aber ≥ der
    Standard-Schwelle 10) und `CompareAlertService.check_all_compare_presets()`
    läuft.

    THEN darf KEIN Alarm versendet werden — die gespeicherte Empfindlichkeit
    "entspannt" muss tatsächlich verwendet werden.

    RED heute: dieselbe Ursache wie im Sensibel-Test — `_build_eval_config()`
    liest die Empfindlichkeit nicht aus `display_config`, fällt auf
    "standard" (Schwelle 10) zurück → Δ=14 ≥ 10 → Alarm wird fälschlich
    ausgelöst → `sent == 1` statt des erwarteten `0`.
    """
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from app.loader import save_location

    uid = "tdd-1170-ac5-entspannt"
    _clean_user(uid)
    preset_id = "cp-1170-entspannt"
    try:
        loc = _location("loc-e", "EntspanntOrt", 47.0, 11.0)
        save_location(loc, user_id=uid)
        _write_preset_file(uid, [
            _preset_with_alert_levels(
                preset_id, ["loc-e"], ["gregor-test@henemm.com"],
                metric_alert_levels={"precipitation_sum": "entspannt"},
            )
        ])

        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-e", _point("loc-e", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _ScriptedWeatherSource({"loc-e": 16.0})  # Δ=14: < entspannt(20), >= standard(10)

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = service.check_all_compare_presets()

        assert sent == 0, (
            f"Gespeicherte Empfindlichkeit 'entspannt' (Schwelle 20) wurde ignoriert — "
            f"erwartet 0 Alarme bei Δ=14, erhalten: {sent}. Der Service liest die "
            "Alarm-Konfiguration offenbar nicht aus display_config.metric_alert_levels."
        )
        assert sent_subjects == []
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-7 (Fix-Loop F001) ════════════════════════

def test_ac7_multiple_locations_bundled_into_single_mail():
    """AC-7 (Adversary-Finding F001) GIVEN ein Preset mit ZWEI Orten
    (loc-1, loc-2), beide mit einem Δ-Anker von 2,0 mm Niederschlag.

    WHEN ein frischer Fetch für BEIDE Orte eine Abweichung ≥ Standard-
    Schwelle (10 mm) liefert (loc-1: 18,0 mm → Δ=16; loc-2: 20,0 mm → Δ=18)
    und `CompareAlertService.check_all_compare_presets()` läuft.

    THEN müssen beide Orte in EINER GEBÜNDELTEN Mail zusammengefasst werden
    — NICHT in zwei getrennten Versänden. `check_all_compare_presets()`
    liefert `1` (eine gebündelte Mail pro Preset-Lauf, nicht eine je Ort),
    es wird genau EIN Mail-Sink-Aufruf ausgelöst, und beide Ortsnamen
    erscheinen im Body dieser einen Mail.

    RED-Grund: `compare_alert.py` versendet heute je Ort eine eigene Mail
    (`_check_one_location()` ruft `send_location_deviation_alert()` PRO
    Treffer auf, `check_all_compare_presets()` zählt `preset_sent` PRO Ort
    hoch) — bei zwei gleichzeitig betroffenen Orten also `sent == 2` und
    zwei getrennte `mail_sink`-Aufrufe statt der laut AC-7 geforderten EINEN
    gebündelten Mail.
    """
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from app.loader import save_location

    uid = "tdd-1170-ac7-bundle"
    _clean_user(uid)
    preset_id = "cp-1170-bundle"
    try:
        loc1 = _location("loc-1", "ErsterVergleichsort", 47.0, 11.0)
        loc2 = _location("loc-2", "ZweiterVergleichsort", 47.2, 11.2)
        save_location(loc1, user_id=uid)
        save_location(loc2, user_id=uid)
        _write_preset_file(uid, [
            _preset_multi(preset_id, ["loc-1", "loc-2"], ["gregor-test@henemm.com"])
        ])

        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-1", _point("loc-1", loc1.name, loc1.lat, loc1.lon, precip_sum_mm=2.0)
        )
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-2", _point("loc-2", loc2.name, loc2.lat, loc2.lon, precip_sum_mm=2.0)
        )

        settings = _settings_email_capable_dummy()
        captured: list[tuple[str, str]] = []
        ws = _ScriptedWeatherSource({"loc-1": 18.0, "loc-2": 20.0})  # Δ=16 / Δ=18, beide ≥ 10

        service = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: captured.append((subject, body)),
        )
        sent = service.check_all_compare_presets()

        assert sent == 1, (
            f"Erwartet EINE gebündelte Mail für beide gleichzeitig betroffenen Orte, "
            f"erhalten sent={sent} (Rückgabewert zählt vermutlich je Ort statt je Preset-Lauf)."
        )
        assert len(captured) == 1, (
            f"Erwartet genau EINEN mail_sink-Aufruf, erhalten: {len(captured)} — "
            "beide Orte müssen in derselben Mail zusammengefasst werden (AC-7)."
        )
        _subject, body = captured[0]
        assert loc1.name in body and loc2.name in body, (
            f"Beide Ortsnamen müssen im Body der einen gebündelten Mail erscheinen:\n{body}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════ AC-7 (Fix-Loop F007) ═════════════════════════════

def test_ac7_single_location_two_metrics_no_per_row_location_prefix():
    """AC-7 (Adversary-Finding F007) GIVEN ein EINZELNER Vergleichs-Ort mit
    ZWEI gleichzeitig gerissenen Metriken (Wind + Niederschlag).

    THEN darf der Ortsname NICHT vor JEDER Metrik-Zeile als Präfix erscheinen
    (Mehr-Metrik-Zweig von `render_email`) — vor #1170 stand der Ortsname nur
    EINMAL im Footer/Where. `to_multi_point_alert_message()` setzt bei genau
    einer Gruppe `location_label` NICHT pro Event, sondern ausschließlich
    nachrichtenweit (`AlertMessage.location_label`).

    RED-Grund (vor dem Fix): `to_point_alert_message()` delegiert an
    `to_multi_point_alert_message()`, die bislang JEDES Event mit
    `location_label=location_name` versah, auch bei genau einer Gruppe. Der
    Mehr-Metrik-Zweig in `render.py` (`loc_prefix = f"{e.location_label} · "`)
    stellte diesen Präfix dann vor JEDE Zeile — Regression ggü. dem Vor-#1170-
    Verhalten (Vorlage: `test_ac7_point_alert_shows_location_name_not_km_zero`
    aus `test_issue_1169_compare_alert_consumer.py`).
    """
    from app.models import ChangeSeverity, SegmentWeatherSummary, WeatherChange
    from output.renderers.alert.project import to_point_alert_message
    from output.renderers.alert.render import render_email
    from services.point_weather import PointWeatherData
    from zoneinfo import ZoneInfo

    location_name = "Refuge de Ciottulu"
    point = PointWeatherData(
        id="loc-a", name=location_name, lat=42.3, lon=8.9,
        timeseries=None,
        aggregated=SegmentWeatherSummary(wind_max_kmh=48.0, precip_sum_mm=18.0),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    change_wind = WeatherChange(
        metric="wind_max_kmh", old_value=20.0, new_value=48.0, delta=28.0,
        threshold=10.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="loc-a",
    )
    change_precip = WeatherChange(
        metric="precip_sum_mm", old_value=2.0, new_value=18.0, delta=16.0,
        threshold=10.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="loc-a",
    )

    msg = to_point_alert_message(
        [change_wind, change_precip], [point], location_name,
        tz=ZoneInfo("UTC"), stand_at="14:00",
    )

    _html, plain = render_email(msg)

    per_row_prefix = f"{location_name} · "
    assert plain.count(per_row_prefix) == 0, (
        f"Ortsname erscheint als redundanter Präfix VOR Metrik-Zeile(n) — "
        f"erwartet EINMAL (Footer/Where), nicht pro Zeile:\n{plain}"
    )
    assert location_name in plain, (
        f"Einzel-Ort-Kontext (Footer/Where) fehlt komplett:\n{plain}"
    )
