---
entity_id: issue_821_absolute_delta_dedup
type: module
created: 2026-06-15
updated: 2026-06-15
status: draft
version: "1.0"
tags: [alerts, weather-change-detection, bugfix, issue-816-interaction]
---

# Absolute/Δ-Dedup in WeatherChangeDetectionService (#821)

## Approval

- [x] Approved (PO 'go', 2026-06-15)

## Purpose

Verhindert, dass eine **absolute** Alert-Regel bei `detect_changes(..., include_absolute=True)`
denselben Wetter-Sprung **doppelt** als `WeatherChange` meldet — einmal über den seit #816 per
`setdefault` geseedeten Δ-Threshold, einmal über den Absolut-Pfad. Pro Wetter-Sprung soll genau
**ein** Change entstehen, ohne die symmetrischen Δ-Alerts reiner Schwellen-Trips
(`include_absolute=False`) zu beschädigen.

## Source

- **File:** `src/services/weather_change_detection.py`
- **Identifier:** `WeatherChangeDetectionService.from_alert_rules`, `WeatherChangeDetectionService.detect_changes`

## Estimated Scope

- **LoC:** ~25 (Backend) + Test-Anpassungen
- **Files:** 1 Source (`weather_change_detection.py`) + 1 Test (`tests/unit/test_issue_222_alert_rules_detection.py`)
- **Effort:** low

## Dependencies

- `src/app/metric_catalog.py` — `get_change_detection_map()` (Δ-Default-Quelle, unverändert)
- `AlertRule` / `AlertMetric` / `AlertRuleKind` (Modelle, unverändert)
- Bezug: #816 (Δ-Seed via setdefault, `include_absolute`-Flag), #222 (absolute/Δ-Regeln, severity-overrides)

## Behavior / Acceptance Criteria

> Begriff: „rein-geseedetes Feld" = ein Summary-Feld, dessen Δ-Threshold **ausschließlich**
> durch die `setdefault`-Seed einer ABSOLUTE-Regel (#816) entstand und **nicht** durch eine
> explizite DELTA-Regel gesetzt/überschrieben wurde.

**AC-1:** Given eine absolute `THUNDER_LEVEL`-Regel mit Schwelle 2.0 (severity CRITICAL),
When `detect_changes(old=NONE, new=HIGH)` mit `include_absolute=True` (Default) aufgerufen wird,
Then entsteht genau **ein** `WeatherChange` für `thunder_level_max` mit `severity=MAJOR`
(über den Absolut-Pfad; der rein-geseedete Δ-Change für dasselbe Feld wird unterdrückt).

**AC-2:** Given eine absolute `THUNDER_LEVEL`-Regel mit Schwelle 2.0,
When `detect_changes(old=NONE, new=MED)` mit `include_absolute=True` aufgerufen wird,
Then entsteht **kein** `WeatherChange` (MED=1 liegt unter Schwelle 2.0; der geseedete Δ-Change
wird ebenfalls unterdrückt, da das Feld absolut abgedeckt ist).

**AC-3:** Given eine absolute `WIND_GUST`-Regel (Schwelle 50.0),
When `detect_changes(..., include_absolute=False)` (Forecast-Alert-Pfad) mit einem
Δ-überschreitenden Sprung (z.B. gust 30→60) aufgerufen wird,
Then feuert der **geseedete Δ-Change** für `gust_max_kmh` weiterhin (genau ein Change) —
absolute-only-Trips behalten ihre symmetrischen Δ-Alerts unverändert.

**AC-4:** Given ein Feld mit **explizitem** Δ-Threshold (DELTA-Regel, z.B. `TEMPERATURE_CHANGE`)
**und** zusätzlich einer absoluten Regel auf demselben Summary-Feld (z.B. `TEMPERATURE_MAX`),
When `detect_changes(..., include_absolute=True)` mit einem Sprung aufgerufen wird, der beide
Schwellen verletzt,
Then werden **beide** Changes ausgegeben (ein Δ-Change + ein Absolut-Change) — eine explizit
gesetzte Δ-Regel wird **nie** unterdrückt; nur rein-geseedete Felder werden dedupliziert.

**AC-5:** Given eine absolute `WIND_GUST`-Regel,
When der Service via `from_alert_rules` gebaut wird,
Then bleibt `_thresholds == {"gust_max_kmh": 20.0}` (Seed bleibt erhalten, F222-A bleibt grün) —
die Dedup-Logik ändert die Threshold-Map **nicht**, sie wirkt nur in `detect_changes`.

**AC-6:** Der zuvor `@xfail` markierte Test
`test_ac9_thunder_level_high_with_threshold_2_fires` ist nach dem Fix **grün ohne xfail**
(xfail-Marker entfernt).

## Edge Cases

- Reiner Default-Konstruktor (Katalog-Defaults, kein `from_alert_rules`): `_absolute_rules` leer →
  Dedup ist No-Op, bestehendes Verhalten unverändert.
- Mehrere absolute Regeln auf unterschiedliche Felder: jede deckt nur ihr eigenes Feld.
- `include_absolute=False`: Dedup darf **nie** greifen (Absolut-Pfad läuft nicht → Δ ist die
  einzige Quelle).

## Non-Goals

- Keine Änderung am Produktiv-Alert-Versand-Verhalten (`trip_alert.py:448` nutzt bereits
  `include_absolute=False`, dort feuerte nie doppelt).
- Keine Änderung an Δ-Defaults oder am `setdefault`-Seed-Mechanismus selbst.
- Keine neue Konfigurationsoberfläche.

## Implementation Notes

`from_alert_rules` führt ein Set `absolute_seeded_fields` mit: Felder, die der ABSOLUTE-Zweig per
`setdefault` neu eingetragen hat. Setzt eine DELTA-Regel dasselbe Feld explizit, wird es aus dem
Set entfernt (es ist dann kein rein-geseedetes Feld mehr). Das Set wird auf der Instanz abgelegt
(`self._absolute_seeded_fields`). In `detect_changes` wird im Δ-Loop ein Feld übersprungen, wenn
`include_absolute and metric in self._absolute_seeded_fields` — dann übernimmt der Absolut-Pfad.

## Changelog

- 2026-06-15: Implementiert (`weather_change_detection.py`, +25 LoC). Adversary VERIFIED 6/6 ACs;
  54 Ziel-Tests grün inkl. entxfailtem `test_ac9_thunder_level_high_with_threshold_2_fires`.
  Keine neue Regression (Baseline-Stash-Diff leer gegen Umgebungsrauschen).
