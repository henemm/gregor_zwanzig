"""TDD RED — Bug #1191: Der Compare-Δ-Wetter-Alarm respektiert im Compare-Editor
DEAKTIVIERTE Metriken NICHT.

Spec: docs/specs/modules/issue_1191_compare_alert_deactivated_metric.md

Root-Cause (Kern der Sache):
`CompareAlertService._build_eval_config()` (src/services/compare_alert.py:207)
übergibt `display_config=None` an die Engine. Ohne `display_config` überspringt
`DeviationAlertEngine._select_detector()` den #961-Deaktivierungs-Filter
(`expand_per_metric_levels(..., display_config=None)`) → ALLE 12 Metriken der
`_STANDARD_METRIC_LEVELS`-Tabelle bekommen eine Regel → jede Metrik feuert,
unabhängig davon, was im Compare-Editor unter `display_config.active_metrics`
(de)aktiviert wurde. Der Trip-Pfad reicht sein `display_config` korrekt durch
(src/services/trip_alert.py:191) — genau das fehlt dem Compare-Pfad.

Vokabular-Mismatch: `active_metrics` nutzt Summary-Keys (`temp_max_c`,
`wind_max_kmh`, `precip_sum_mm`, `gust_max_kmh`, `cape_max_jkg`,
`visibility_min_m`, …), der #961-Filter prüft Katalog-IDs (`temperature`,
`wind`, `gust`, `cape`, …). Der Fix braucht daher einen Summary→Katalog-Mapper.

RED-Treiber (schlagen HEUTE fehl, weil der Bug reproduziert wird):
  - test_ac1_deactivated_wind_metric_does_not_fire
  - test_ac3_deactivated_cape_metric_does_not_fire
  - test_ac6_unlisted_wind_metric_does_not_fire
Guard-Tests (dürfen HEUTE schon grün sein — aktive Metriken feuern weiter):
  - test_ac2_active_temperature_metric_still_fires
  - test_ac3_active_gust_metric_still_fires
  - test_ac6_active_precipitation_metric_fires
  - test_ac6_active_visibility_metric_fires

Mock-frei: echte `CompareAlertService`-Instanzen, echte Preset-/Snapshot-Dateien
unter `data/users/tdd-1191-*`, deterministischer `_ScriptedSource` (kein
`Mock()`/`patch()`, kein Netz). Setup-Seams 1:1 aus
test_issue_1170_compare_alert_config.py übernommen.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


# ───────────────────────── Helfer (mock-frei) ──────────────────────────────

def _clean_user(user_id: str) -> None:
    import shutil

    d = DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d)


def _settings_email_capable_dummy() -> Settings:
    """`can_send_email() == True` ohne echten Netzzugriff (für mail_sink-Capture)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _location(loc_id: str, name: str, lat: float, lon: float, elevation_m: int = 1000) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=elevation_m)


def _point_full(point_id: str, name: str, lat: float, lon: float, **summary):
    """Echtes `PointWeatherData`-DTO mit frei setzbaren Summary-Feldern (kein Mock)."""
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="test-scripted",
    )


class _ScriptedSource:
    """Deterministischer `LocationWeatherSource`-Impl — liefert je Ort ein echtes
    `PointWeatherData` mit vorab festgelegten Summary-Feldern. Kein Mock: ein
    Konfigurations-Seam analog `_ScriptedWeatherSource` aus #1169/#1170."""

    def __init__(self, values: dict[str, dict]) -> None:
        self._values = {k: dict(v) for k, v in values.items()}

    def fetch(self, point_id: str, lat: float, lon: float):
        return _point_full(point_id, point_id, lat, lon, **self._values.get(point_id, {}))


def _preset_with_active_metrics(
    preset_id: str, location_ids: list[str], active_metrics: list[str],
    empfaenger: list[str] | None = None,
) -> dict:
    """Compare-Preset mit im Editor gesetzter Metrik-Auswahl unter
    `display_config.active_metrics` (Summary-Keys, wie das Frontend persistiert —
    frontend/.../compareEditorSave.ts). `metric_alert_levels` bleibt bewusst
    LEER → `_build_eval_config` fällt auf `_STANDARD_METRIC_LEVELS` (alle
    Metriken „standard") zurück. Genau hier greift der Bug: `active_metrics`
    wird von `_build_eval_config` heute überhaupt nicht gelesen."""
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
        "empfaenger": empfaenger or ["gregor-test@henemm.com"],
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-07-12T00:00:00Z",
        "display_config": {"active_metrics": list(active_metrics)},
    }


def _write_preset_file(user_id: str, presets: list[dict]) -> Path:
    # Issue #1250 S7b Cutover: per-Datei briefings/<id>.json (kind="vergleich").
    return write_compare_briefings(DATA_ROOT / user_id, presets)


def _run_scenario(
    uid: str, preset_id: str, active_metrics: list[str],
    cached_summary: dict, fresh_summary: dict,
) -> tuple[int, list[tuple[str, str]]]:
    """Baut EIN Compare-Preset mit einem Ort, verankert `cached_summary` als
    Δ-Anker (Snapshot) und lässt den frischen Fetch `fresh_summary` liefern.
    Gibt (sent, captured_mails) von `check_all_compare_presets()` zurück."""
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from app.loader import save_location

    _clean_user(uid)
    try:
        loc = _location("loc-x", "Vergleichsort", 47.0, 11.0)
        save_location(loc, user_id=uid)
        _write_preset_file(uid, [
            _preset_with_active_metrics(preset_id, ["loc-x"], active_metrics)
        ])

        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-x",
            _point_full("loc-x", loc.name, loc.lat, loc.lon, **cached_summary),
        )

        captured: list[tuple[str, str]] = []
        service = CompareAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            weather_source=_ScriptedSource({"loc-x": fresh_summary}),
            mail_sink=lambda subject, body: captured.append((subject, body)),
        )
        sent = service.check_all_compare_presets()
        return sent, captured
    finally:
        _clean_user(uid)


# ═══════════════════════════════ AC-1 (RED-Treiber) ══════════════════════════

def test_ac1_deactivated_wind_metric_does_not_fire():
    """AC-1 GIVEN ein Compare-Preset mit `active_metrics=["temp_max_c"]` (Wind
    also im Editor DEAKTIVIERT), leerem `metric_alert_levels`, und einem
    Wind-Δ deutlich über der Standard-Schwelle (cached 20 → fresh 50 km/h,
    Δ=30 > wind_change-Standard 25).

    WHEN `CompareAlertService.check_all_compare_presets()` läuft.

    THEN darf KEIN Alarm feuern (`sent == 0`) — die deaktivierte Wind-Metrik
    muss stumm bleiben.

    RED heute: `_build_eval_config` übergibt `display_config=None` und
    `metric_alert_levels=_STANDARD_METRIC_LEVELS` → der #961-Filter wird
    übersprungen → die Wind-Regel bleibt scharf → Wind-Δ feuert → `sent == 1`
    statt des erwarteten `0`. `active_metrics` wird komplett ignoriert.
    """
    sent, captured = _run_scenario(
        "tdd-1191-ac1-wind-off", "cp-1191-ac1",
        active_metrics=["temp_max_c"],
        cached_summary={"wind_max_kmh": 20.0},
        fresh_summary={"wind_max_kmh": 50.0},
    )
    assert sent == 0, (
        f"Deaktivierte Wind-Metrik (active_metrics=['temp_max_c']) hat trotzdem "
        f"gefeuert — erwartet 0 Alarme bei Wind-Δ=30, erhalten sent={sent}. "
        "Der Compare-Pfad reicht sein display_config nicht durch (Bug #1191)."
    )
    assert captured == []


# ═══════════════════════════════ AC-2 (Guard) ════════════════════════════════

def test_ac2_active_temperature_metric_still_fires():
    """AC-2 GIVEN dasselbe Preset (`active_metrics=["temp_max_c"]`) und ein
    Temperatur-Δ über der Standard-Schwelle (cached 10 → fresh 30 °C, Δ=20).

    Hinweis: `temp_max_c` wird von zwei Delta-Regeln belegt — temperature_max
    (Standard 6) UND temperature_change (Standard 10, Feld-Kollision, siehe
    `from_alert_rules`). Die zuletzt gebaute Regel (temperature_change, 10)
    gewinnt das Feld → das Δ muss > 10 sein, um sicher zu feuern (Δ=20 ✓).

    WHEN ausgewertet.

    THEN feuert der Temperatur-Alarm (`sent == 1`) — eine AKTIVE Metrik bleibt
    aktiv. Guard gegen Über-Filterung; darf HEUTE schon grün sein.
    """
    sent, captured = _run_scenario(
        "tdd-1191-ac2-temp-on", "cp-1191-ac2",
        active_metrics=["temp_max_c"],
        cached_summary={"temp_max_c": 10.0},
        fresh_summary={"temp_max_c": 30.0},
    )
    assert sent == 1, (
        f"Aktive Temperatur-Metrik hätte feuern müssen — erwartet 1 Alarm bei "
        f"Temp-Δ=20, erhalten sent={sent}."
    )
    assert len(captured) == 1


# ═══════════════════════════════ AC-3 (Böen aktiv / CAPE deaktiviert) ═════════

def test_ac3_active_gust_metric_still_fires():
    """AC-3 (Guard) GIVEN ein Preset mit `active_metrics=["gust_max_kmh"]`
    (Böen aktiv) und einem Böen-Δ über der Standard-Schwelle (cached 20 →
    fresh 50 km/h, Δ=30 > wind_gust-Standard 20).

    THEN feuert der Böen-Alarm (`sent == 1`). Darf HEUTE schon grün sein.
    """
    sent, captured = _run_scenario(
        "tdd-1191-ac3-gust-on", "cp-1191-ac3-gust",
        active_metrics=["gust_max_kmh"],
        cached_summary={"gust_max_kmh": 20.0},
        fresh_summary={"gust_max_kmh": 50.0},
    )
    assert sent == 1, (
        f"Aktive Böen-Metrik hätte feuern müssen — erwartet 1 Alarm bei "
        f"Böen-Δ=30, erhalten sent={sent}."
    )
    assert len(captured) == 1


def test_ac3_deactivated_cape_metric_does_not_fire():
    """AC-3 (RED-Treiber) GIVEN dasselbe Preset mit `active_metrics=
    ["gust_max_kmh"]` (CAPE also NICHT gelistet = deaktiviert) und einem
    CAPE-Δ über der Standard-Schwelle (cached 100 → fresh 900 J/kg, Δ=800 >
    cape-Standard 600).

    WHEN ausgewertet.

    THEN darf KEIN Alarm feuern (`sent == 0`) — CAPE ist deaktiviert.

    RED heute: `display_config=None` → CAPE-Regel bleibt scharf → CAPE-Δ
    feuert → `sent == 1` statt `0`. Beweist zugleich den fehlenden
    Summary→Katalog-Mapper (`cape_max_jkg` → Katalog-ID `cape`).
    """
    sent, captured = _run_scenario(
        "tdd-1191-ac3-cape-off", "cp-1191-ac3-cape",
        active_metrics=["gust_max_kmh"],
        cached_summary={"cape_max_jkg": 100.0},
        fresh_summary={"cape_max_jkg": 900.0},
    )
    assert sent == 0, (
        f"Deaktivierte CAPE-Metrik (nur gust_max_kmh aktiv) hat trotzdem "
        f"gefeuert — erwartet 0 Alarme bei CAPE-Δ=800, erhalten sent={sent}. "
        "Bug #1191: display_config wird nicht durchgereicht."
    )
    assert captured == []


# ═══════════════════════════════ AC-6 (Vokabular-Mapper) ═════════════════════

_AC6_ACTIVE = ["temp_max_c", "precip_sum_mm", "visibility_min_m"]


def test_ac6_active_precipitation_metric_fires():
    """AC-6 (Guard) GIVEN `active_metrics=["temp_max_c","precip_sum_mm",
    "visibility_min_m"]` und einem Niederschlags-Δ über der Standard-Schwelle
    (cached 2 → fresh 15 mm, Δ=13 > precipitation_sum-Standard 10).

    THEN feuert der Niederschlags-Alarm (`sent == 1`) — belegt, dass der
    Summary-Key `precip_sum_mm` als aktiv erkannt wird. Darf HEUTE grün sein.
    """
    sent, _ = _run_scenario(
        "tdd-1191-ac6-precip-on", "cp-1191-ac6-precip",
        active_metrics=_AC6_ACTIVE,
        cached_summary={"precip_sum_mm": 2.0},
        fresh_summary={"precip_sum_mm": 15.0},
    )
    assert sent == 1, (
        f"Aktive Niederschlags-Metrik hätte feuern müssen — erwartet 1 Alarm "
        f"bei Precip-Δ=13, erhalten sent={sent}."
    )


def test_ac6_active_visibility_metric_fires():
    """AC-6 (Guard) GIVEN dasselbe aktive Set und ein Sichtweiten-Threshold-
    Crossing (cached 20000 → fresh 500 m, unterschreitet die Standard-Schwelle
    1000 m).

    THEN feuert der Sichtweiten-Alarm (`sent == 1`) — belegt den Summary-Key
    `visibility_min_m` als aktiv. Darf HEUTE grün sein.
    """
    sent, _ = _run_scenario(
        "tdd-1191-ac6-vis-on", "cp-1191-ac6-vis",
        active_metrics=_AC6_ACTIVE,
        cached_summary={"visibility_min_m": 20000},
        fresh_summary={"visibility_min_m": 500},
    )
    assert sent == 1, (
        f"Aktive Sichtweiten-Metrik hätte feuern müssen — erwartet 1 Alarm bei "
        f"Unterschreiten von 1000 m (20000→500), erhalten sent={sent}."
    )


def test_ac6_unlisted_wind_metric_does_not_fire():
    """AC-6 (RED-Treiber) GIVEN dasselbe aktive Set `["temp_max_c",
    "precip_sum_mm","visibility_min_m"]` (Wind also NICHT gelistet) und einem
    Wind-Δ über der Standard-Schwelle (cached 20 → fresh 50 km/h, Δ=30 > 25).

    WHEN ausgewertet.

    THEN darf KEIN Alarm feuern (`sent == 0`) — Wind ist nicht in
    `active_metrics`, der Vokabular-Mapper darf ihn nicht fälschlich scharf
    lassen.

    RED heute: `display_config=None` → Wind-Regel bleibt scharf → `sent == 1`
    statt `0` (Bug #1191).
    """
    sent, captured = _run_scenario(
        "tdd-1191-ac6-wind-off", "cp-1191-ac6-wind",
        active_metrics=_AC6_ACTIVE,
        cached_summary={"wind_max_kmh": 20.0},
        fresh_summary={"wind_max_kmh": 50.0},
    )
    assert sent == 0, (
        f"Nicht gelistete Wind-Metrik hat trotzdem gefeuert — erwartet 0 "
        f"Alarme bei Wind-Δ=30 (active_metrics ohne Wind), erhalten sent={sent}. "
        "Bug #1191: display_config wird nicht durchgereicht."
    )
    assert captured == []


# ═══════════════════ Adversary F001: "alles deaktiviert" feuert nicht ═════════

def test_f001a_empty_active_metrics_wind_delta_does_not_fire():
    """Adversary F001-a GIVEN ein Compare-Preset mit `active_metrics=[]` (der
    Nutzer hat im Editor ALLES abgewählt) und einem Wind-Δ deutlich über der
    Standard-Schwelle (cached 20 → fresh 50 km/h, Δ=30 > 25).

    WHEN `check_all_compare_presets()` läuft.

    THEN darf KEIN Alarm feuern (`sent == 0`).

    Regression-Guard gegen den F001-Defekt: Eine LEERE (aber vorhandene)
    `active_metrics`-Liste erzeugte bislang ein `UnifiedWeatherDisplayConfig`
    mit leerer `metrics[]`. `is_alert_metric_active` deutete das als „Weather-Tab
    nie konfiguriert" und gab konservativ für JEDE Metrik `True` zurück → ALLES
    feuerte trotz vollständiger Abwahl. Der Fix listet nun alle Alarm-Katalog-IDs
    EXPLIZIT mit `enabled=False` → nichts feuert."""
    sent, captured = _run_scenario(
        "tdd-1191-f001a-empty", "cp-1191-f001a",
        active_metrics=[],
        cached_summary={"wind_max_kmh": 20.0},
        fresh_summary={"wind_max_kmh": 50.0},
    )
    assert sent == 0, (
        f"Vollständig abgewählte Metriken (active_metrics=[]) haben trotzdem "
        f"gefeuert — erwartet 0 Alarme bei Wind-Δ=30, erhalten sent={sent}. "
        "Adversary F001: leeres display_config wurde als 'alles aktiv' gedeutet."
    )
    assert captured == []


def test_f001b_only_non_alertable_metric_wind_delta_does_not_fire():
    """Adversary F001-b GIVEN `active_metrics=["cloud_avg_pct"]` — der einzige
    aktive Key ist eine reine Vergleichsmetrik OHNE Alarm-Katalog-Mapping — und
    einem Wind-Δ über der Standard-Schwelle (cached 20 → fresh 50 km/h, Δ=30).

    WHEN ausgewertet.

    THEN darf KEIN Alarm feuern (`sent == 0`) — kein gelisteter Key ist
    alarmfähig, also ist jede Alarm-Metrik deaktiviert.

    Regression-Guard F001: `cloud_avg_pct` mappt auf keine Katalog-ID → früher
    leere `metrics[]` → alles feuerte. Jetzt: alle Alarm-IDs `enabled=False` →
    stumm."""
    sent, captured = _run_scenario(
        "tdd-1191-f001b-cloud", "cp-1191-f001b",
        active_metrics=["cloud_avg_pct"],
        cached_summary={"wind_max_kmh": 20.0},
        fresh_summary={"wind_max_kmh": 50.0},
    )
    assert sent == 0, (
        f"Nur eine nicht-alarmfähige Metrik aktiv (cloud_avg_pct) — erwartet 0 "
        f"Alarme bei Wind-Δ=30, erhalten sent={sent}. Adversary F001."
    )
    assert captured == []


# ═══════════════ Adversary F002: Min-Temp entkoppelt von Max-Temp ════════════

def test_f002_temp_max_active_min_temp_delta_does_not_fire():
    """Adversary F002 GIVEN `active_metrics=["temp_max_c"]` (Min-Temp im Editor
    NICHT gelistet = deaktiviert) und einem drastischen Min-Temp-Δ (cached 10 →
    fresh -20 °C, Δ=30 — weit über jeder Standard-Schwelle).

    WHEN ausgewertet.

    THEN darf KEIN Min-Temp-Alarm feuern (`sent == 0`).

    Regression-Guard F002: Max-Temp (`temp_max_c` → Katalog `temperature`)
    aktivierte implizit auch die Min-Temp — sowohl über die
    TEMPERATURE_MIN-OR-Katalogtupel `("temperature_cold","temperature")` ALS AUCH
    über `temperature_change` (Δ auf temp_min_c UND temp_max_c, Katalog
    `temperature`). Der Fix unterdrückt das Feld `temp_min_c` aus JEDER Regel,
    sobald die synthetische Richtungs-Metrik `temperature_cold` EXPLIZIT
    deaktiviert ist — Min bleibt stumm, Max unberührt."""
    sent, captured = _run_scenario(
        "tdd-1191-f002-min-off", "cp-1191-f002",
        active_metrics=["temp_max_c"],
        cached_summary={"temp_min_c": 10.0},
        fresh_summary={"temp_min_c": -20.0},
    )
    assert sent == 0, (
        f"Deaktivierte Min-Temp (nur temp_max_c aktiv) hat trotzdem gefeuert — "
        f"erwartet 0 Alarme bei Min-Temp-Δ=30, erhalten sent={sent}. "
        "Adversary F002: temp_max_c aktivierte implizit die Min-Temp."
    )
    assert captured == []


def test_f002_guard_temp_min_active_min_temp_delta_fires():
    """Adversary F002 (Guard) GIVEN `active_metrics=["temp_min_c"]` (Min-Temp
    AKTIV) und demselben Min-Temp-Δ (10 → -20 °C, Δ=30).

    THEN feuert der Min-Temp-Alarm (`sent == 1`) — die Entkopplung darf die
    Min-Temp bei tatsächlicher Aktivierung NICHT verschlucken."""
    sent, captured = _run_scenario(
        "tdd-1191-f002-min-on", "cp-1191-f002-guard-min",
        active_metrics=["temp_min_c"],
        cached_summary={"temp_min_c": 10.0},
        fresh_summary={"temp_min_c": -20.0},
    )
    assert sent == 1, (
        f"Aktive Min-Temp hätte feuern müssen — erwartet 1 Alarm bei "
        f"Min-Temp-Δ=30, erhalten sent={sent}."
    )
    assert len(captured) == 1


def test_f002_guard_temp_max_active_max_temp_delta_still_fires():
    """Adversary F002 (Guard) GIVEN `active_metrics=["temp_max_c"]` und einem
    Max-Temp-Δ über der Standard-Schwelle (cached 10 → fresh 30 °C, Δ=20).

    THEN feuert der Max-Temp-Alarm weiter (`sent == 1`) — die Min-Entkopplung
    darf die Max-Temp NICHT beschädigen."""
    sent, captured = _run_scenario(
        "tdd-1191-f002-max-on", "cp-1191-f002-guard-max",
        active_metrics=["temp_max_c"],
        cached_summary={"temp_max_c": 10.0},
        fresh_summary={"temp_max_c": 30.0},
    )
    assert sent == 1, (
        f"Aktive Max-Temp hätte feuern müssen — erwartet 1 Alarm bei "
        f"Max-Temp-Δ=20, erhalten sent={sent}."
    )
    assert len(captured) == 1
