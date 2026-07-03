"""Issue #846 — Alert-Preset-Expansion (Epic #813 Slice 3).

Expandiert einen Preset-Namen in eine Liste von AlertRule-Objekten.

Presets:
- "deaktiviert" → leere Liste (kein Alert-Versand)
- "entspannt"   → lockere Schwellen (13 Regeln)
- "standard"    → empfohlene Schwellen (13 Regeln, Default)
- "sensibel"    → enge Schwellen (13 Regeln)

Schwellwert-Tabelle:
    Metrik                  Art               Entspannt  Standard  Sensibel
    wind_gust               delta ↑              35         20        12
    precipitation_sum       delta ↑              20         10         5
    thunder_level           delta ↑               1          1         1
    freezing_level          delta ↓             600        400       200
    temperature_min         delta ↓               8          5         3
    temperature_max         delta ↑              10          6         4
    temperature_change      delta ↑              14         10         6
    wind_change             delta ↑              35         25        15
    precipitation_change    delta ↑              15          7         3
    fresh_snow              delta ↑              20          8         2
    cape                    delta ↑            1200        600       200
    visibility   threshold_crossing ↓           500       1000      3000
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Final

from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity

if TYPE_CHECKING:
    from app.models import UnifiedWeatherDisplayConfig

# ───────────────────────── Schwellwert-Tabelle ──────────────────────────────

# Jede Zeile: (metric, kind, threshold_entspannt, threshold_standard, threshold_sensibel)
_PRESET_TABLE: Final[list[tuple]] = [
    (AlertMetric.WIND_GUST,            AlertRuleKind.DELTA,              35,    20,    12),
    (AlertMetric.PRECIPITATION_SUM,    AlertRuleKind.DELTA,              20,    10,     5),
    (AlertMetric.THUNDER_LEVEL,        AlertRuleKind.DELTA,               1,     1,     1),
    # Issue #959: Nullgradgrenze konsolidiert zu EINER Zeile (freezing_level) mit den
    # bisher wirksamen snow_line-Schwellen 600/400/200 (PO-freigegeben). Die frühere
    # separate SNOW_LINE-Zeile entfällt; alt-persistierte snow_line-Levels werden
    # beim Trip-Laden auf freezing_level migriert (loader._migrate_metric_alert_levels).
    (AlertMetric.FREEZING_LEVEL,       AlertRuleKind.DELTA,             600,   400,   200),
    (AlertMetric.TEMPERATURE_MIN,      AlertRuleKind.DELTA,               8,     5,     3),
    (AlertMetric.TEMPERATURE_MAX,      AlertRuleKind.DELTA,              10,     6,     4),
    (AlertMetric.TEMPERATURE_CHANGE,   AlertRuleKind.DELTA,              14,    10,     6),
    (AlertMetric.WIND_CHANGE,          AlertRuleKind.DELTA,              35,    25,    15),
    (AlertMetric.PRECIPITATION_CHANGE, AlertRuleKind.DELTA,              15,     7,     3),
    (AlertMetric.FRESH_SNOW,           AlertRuleKind.DELTA,              20,     8,     2),
    (AlertMetric.CAPE,                 AlertRuleKind.DELTA,            1200,   600,   200),
    (AlertMetric.VISIBILITY,           AlertRuleKind.THRESHOLD_CROSSING, 500,  1000,  3000),
    # Issue #889 / ADR-0010: HUMIDITY ist Vorboten-Metrik — kein Preset-Alert mehr.
]

# Spaltenindex in _PRESET_TABLE (2=entspannt, 3=standard, 4=sensibel)
_COL: Final[dict[str, int]] = {
    "entspannt": 2,
    "standard":  3,
    "sensibel":  4,
}


def expand_preset(name: str) -> list[AlertRule]:
    """Expandiert einen Preset-Namen in eine AlertRule-Liste.

    Args:
        name: Preset-Name ("deaktiviert" | "entspannt" | "standard" | "sensibel").
              Unbekannte Namen werden wie "standard" behandelt.

    Returns:
        Liste von AlertRule-Objekten. Leer bei "deaktiviert".
    """
    if name == "deaktiviert":
        return []

    col = _COL.get(name, _COL["standard"])
    rules: list[AlertRule] = []
    for row in _PRESET_TABLE:
        metric, kind, *thresholds = row
        threshold = float(thresholds[col - 2])
        rules.append(AlertRule(
            id=str(uuid.uuid4()),
            kind=kind,
            metric=metric,
            threshold=threshold,
            severity=AlertSeverity.WARNING,
            enabled=True,
        ))
    return rules


def expand_per_metric_levels(
    levels: dict[str, str],
    display_config: "UnifiedWeatherDisplayConfig | None" = None,
) -> list[AlertRule]:
    """Konvertiert metric_alert_levels (metric → SensLevel) in AlertRule-Liste.

    Level 'off' wird übersprungen. Nutzt dieselbe _PRESET_TABLE wie expand_preset().

    Issue #961 — Vertrag `should_fire = weather_tab_enabled AND level != 'off'`:
    Wird `display_config` übergeben (nicht None), wird der Weather-Tab-
    Aktivierungsstatus berücksichtigt:
      - **Deaktivieren-Lücke:** Ein `metric_alert_levels`-Eintrag für eine Metrik,
        deren Weather-Tab-Metrik(en) NICHT aktiv sind, wird übersprungen (keine
        AlertRule), unabhängig vom Level.
      - **Aktivieren-Lücke:** Metriken, die auf dem Weather-Tab aktiv sind, aber in
        `levels` fehlen, bekommen implizit 'standard' (Backfill-Default) — analog
        zur UI-Anzeige. Explizit gesetztes `level: 'off'` bleibt Opt-out (kein
        Backfill-Overwrite).
    Ohne `display_config` (Default None): altes Verhalten (Abwärtskompatibilität,
    keine Filterung, kein Backfill).

    `levels` (die Trip-JSON-Quelle) wird NIE verändert — reine Auswertungslogik.
    """
    from services.weather_change_detection import (
        _ALERT_DELTA_METRIC_TO_FIELDS,
        _ALERT_METRIC_TO_CATALOG_ID,
        _ALERT_METRIC_TO_SUMMARY_FIELD,
        is_alert_metric_active,
    )

    # Issue #959: Legacy-Schlüssel snow_line auf die konsolidierte freezing_level-
    # Metrik normalisieren, falls er der Loader-Migration entgangen ist (z. B.
    # in-memory konstruierte Trips). `levels` (die Trip-JSON-Quelle) bleibt
    # unangetastet — es wird nur eine lokale Kopie umbenannt. Ein bereits
    # gesetzter freezing_level-Eintrag gewinnt.
    if "snow_line" in levels:
        _normalized = dict(levels)
        _normalized.setdefault("freezing_level", _normalized.pop("snow_line"))
        levels = _normalized

    # Aufbau: metric.value (str) → (kind, entspannt, standard, sensibel)
    metric_to_row: dict[str, tuple] = {
        row[0].value: row for row in _PRESET_TABLE
    }

    def _fields_for(metric_str: str) -> set[str]:
        """Summary-/Delta-Felder, die eine Metrik in `_thresholds` belegt.
        Issue #961: Wird gebraucht, um Feld-Kollisionen zwischen Metriken zu
        erkennen (z. B. temperature_change teilt sich temp_min_c mit temperature_min,
        precipitation_change teilt sich precip_sum_mm mit precipitation_sum)."""
        try:
            am = AlertMetric(metric_str)
        except ValueError:
            return set()
        delta = _ALERT_DELTA_METRIC_TO_FIELDS.get(am)
        if delta:
            return set(delta)
        summary = _ALERT_METRIC_TO_SUMMARY_FIELD.get(am)
        return {summary} if summary else set()

    def _make_rule(metric_str: str, level: str) -> "AlertRule | None":
        col = _COL.get(level)
        if col is None:
            return None
        row = metric_to_row.get(metric_str)
        if row is None:
            return None
        _metric, kind, *thresholds = row
        threshold = float(thresholds[col - 2])
        # metric_str direkt speichern: str(rule.metric) == "wind_gust" (Test-Erwartung)
        return AlertRule(
            id=str(uuid.uuid4()),
            kind=kind,
            metric=metric_str,  # type: ignore[arg-type]
            threshold=threshold,
            severity=AlertSeverity.WARNING,
            enabled=True,
        )

    rules: list[AlertRule] = []
    for metric_str, level in levels.items():
        if level == "off":
            continue
        # Issue #961: Deaktivieren-Lücke schließen (nur mit display_config).
        if display_config is not None:
            try:
                alert_metric = AlertMetric(metric_str)
            except ValueError:
                alert_metric = None
            if alert_metric is None or not is_alert_metric_active(alert_metric, display_config):
                continue
        rule = _make_rule(metric_str, level)
        if rule is not None:
            rules.append(rule)

    # Issue #961: Aktivieren-Lücke schließen — Backfill 'standard' für Weather-Tab-
    # aktive Metriken, die (noch) nicht in `levels` stehen. Explizites 'off' bleibt.
    #
    # Feld-Kollisions-Schutz (AC-6): Metriken, die der Nutzer EXPLIZIT in `levels`
    # konfiguriert hat, belegen bestimmte Summary-Felder. Ein Backfill einer ANDEREN
    # Metrik, die sich ein solches Feld teilt, würde die explizite Nutzer-Entscheidung
    # aushebeln — insbesondere ein explizites 'off' (z. B. temperature_min='off' darf
    # nicht durch Backfill von temperature_change wieder scharf werden — beide belegen
    # temp_min_c). Solche Backfills werden feld-granular unterdrückt: eine Backfill-
    # Metrik armiert nur die Felder, die NICHT bereits von einer explizit gesetzten
    # Metrik belegt sind.
    #
    # Finding F001 (AC-3): Ein Feld blockiert den Backfill NUR, wenn die
    # beanspruchende explizite Metrik tatsächlich AKTIV ist (Weather-Tab aktiv). Eine
    # explizit gesetzte, aber Weather-Tab-INAKTIVE Metrik (z. B. Level gesetzt, aber
    # Weather-Tab-Metrik deaktiviert) belegt kein Feld — so kann eine dritte,
    # Weather-Tab-aktive Metrik ihr Feld gebackfillt bekommen. Explizites 'off' bei
    # AKTIVER Weather-Tab-Metrik bleibt dagegen ein wirksames Opt-out (AC-6).
    if display_config is not None:
        claimed_fields: set[str] = set()
        for metric_str in levels:
            try:
                claiming_metric = AlertMetric(metric_str)
            except ValueError:
                continue
            # F001: Nur Weather-Tab-aktive Metriken belegen ihr Feld (schützen es vor
            # Backfill). Ein Level-Eintrag für eine deaktivierte Weather-Tab-Metrik
            # ist ohnehin wirkungslos und darf keinen Backfill blockieren.
            if not is_alert_metric_active(claiming_metric, display_config):
                continue
            claimed_fields |= _fields_for(metric_str)
        for alert_metric in _ALERT_METRIC_TO_CATALOG_ID:
            metric_str = alert_metric.value
            if metric_str in levels:
                continue  # bereits behandelt (inkl. explizitem 'off')
            if not is_alert_metric_active(alert_metric, display_config):
                continue
            # Finding F004 (feld-granular): Nur die Felder aus der Backfill-Metrik
            # entfernen, die bereits von einer explizit gesetzten AKTIVEN Metrik
            # belegt sind. Bleibt danach KEIN Feld übrig → Regel komplett überspringen
            # (z. B. temperature_change, wenn temperature_min UND temperature_max beide
            # off/aktiv sind → beide temp-Felder belegt → AC-6-Konflikt, korrekt
            # unterdrückt). Bleibt mindestens ein Feld übrig → Regel erzeugen, aber die
            # kollidierenden Felder als suppressed_fields markieren, sodass sie NICHT
            # scharf gestellt werden (from_alert_rules zieht sie beim Threshold-Aufbau ab).
            metric_fields = _fields_for(metric_str)
            colliding = metric_fields & claimed_fields
            remaining = metric_fields - claimed_fields
            if metric_fields and not remaining:
                continue  # alle Felder belegt → Regel komplett unterdrücken (AC-6)
            rule = _make_rule(metric_str, "standard")
            if rule is not None:
                if colliding:
                    rule.suppressed_fields = set(colliding)
                rules.append(rule)

    return rules
