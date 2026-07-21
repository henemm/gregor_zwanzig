---
entity_id: issue_1191_compare_alert_deactivated_metric
type: module
created: 2026-07-12
updated: 2026-07-12
status: draft
version: "1.0"
tags: [compare, alert, deactivation, metric-filter]
---

# #1191 — Compare-Δ-Alarm respektiert deaktivierte Metriken

## Approval

- [x] Approved (PO 2026-07-12, Option „go" + frischer Umsetzungslauf; Entscheidungen A/B final: 4 Schalter inkl. CAPE, Migration auf „alle aktiv")

## Purpose

Behebt, dass eine im Compare-Editor (Tab „Idealwerte") **deaktivierte** Metrik im Compare-Δ-Wetter-Alarm **weiterfeuert**. Ursache: `compare_alert.py::_build_eval_config` übergibt `display_config=None` an die Engine, wodurch der #961-Deaktivierungs-Filter (`expand_per_metric_levels`) übersprungen wird. Der Trip-Pfad reicht sein `display_config` durch und filtert korrekt.

## Source

**Full-Stack (PO-Erweiterung 2026-07-12):**
- **Backend:** `src/services/compare_alert.py::CompareAlertService._build_eval_config` (Fix an `:207`) + Summary→Katalog-Mapper (erweitert `src/app/loader.py:617 _OLD_METRIC_MAP` oder eigener Helfer).
- **Frontend:** Idealwerte-Tab um 4 Schalter erweitern — `frontend/src/lib/components/compare/compareMetricDefs.ts` (neue Metrik-Defs) + `CompareEditor.svelte` (Toggles + `active_metrics`-Persistenz) + `frontend/.../compareMetricDefs`-Vokabular.
- **Migration:** Skript `scripts/migrate_1191_compare_active_metrics.py` — setzt `active_metrics` auf bestehenden Compare-Presets (idempotent, Backup). Per-Host als `claude-gregor` (data/users gitignored).

Schichten: **Python-Core** (Filter/Mapper) + **SvelteKit-Frontend** (Idealwerte-Tab) + **Daten-Migration**.

## Estimated Scope

- **LoC:** ~180–260 (Backend-Fix+Mapper ~60, Frontend 4 Toggles ~80, Migration ~40, Tests ~60) → über 250 möglich, ggf. LoC-Override.
- **Files:** ~2 Backend + ~2 Frontend + 1 Migration + Tests
- **Effort:** high (Full-Stack, UI-Änderung → Fresh-Eyes + Staging-Playwright Pflicht)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `display_config.active_metrics` (Summary-Keys) | Datenquelle | Aktivierungs-Status je Metrik (Compare-Editor) |
| `is_alert_metric_active` / `is_metric_enabled` (`weather_change_detection.py:137-177`) | Konsument | prüft Katalog-IDs gegen `display_config.metrics` |
| `expand_per_metric_levels` (`alert_preset.py:96`) | Filter | #961-Deaktivieren-Lücke |
| `UnifiedWeatherDisplayConfig` / `MetricConfig` (`models.py:553`) | Aufbau | Objekt, das die Engine erwartet |
| Trip-Pfad `trip_alert.py:191` (`display_config=trip.display_config`) | Vorbild | analoges Durchreichen |

## Implementation Details

### Kernproblem: Vokabular-Mismatch
`active_metrics` nutzt **Summary-Keys** (`temp_max_c`, `wind_max_kmh`, `precip_sum_mm`, `thunder_level_max`, `visibility_min_m`, `snow_new_sum_cm`, …). Der Alarm-Filter prüft **Katalog-IDs** (`temperature`, `wind`, `precipitation`, `thunder`, `gust`, `visibility`, `fresh_snow`, `cape`, `freezing_level`). Naives Durchreichen (Dict oder `metric_id=summary_key`) filtert entweder gar nicht (leeres `.metrics` → `is_alert_metric_active` gibt konservativ `True`) ODER unterdrückt fälschlich ALLES (Key-Mismatch). Daher **Mapper Pflicht**.

### Fix
**PO-Paradigma (2026-07-12, überschreibt vorsichtige Defaults):** *Was deaktiviert wird, feuert nicht — der Nutzer weiß, was er tut.* Alt-Vergleiche werden schonungslos mitgezogen (kein Backward-Compat). Nur 2 Nutzer, keine Fremdnutzer-Rücksicht.

In `_build_eval_config`:
1. Baue ein `UnifiedWeatherDisplayConfig` mit `metrics=[MetricConfig(metric_id=<KATALOG-ID>, enabled=True) …]` **ausschließlich** aus den in `active_metrics` gelisteten Summary-Keys, via Mapper übersetzt: `temp_max_c→temperature`, `wind_max_kmh→wind`, `precip_sum_mm→precipitation`, `thunder_level_max→thunder`, `visibility_min_m→visibility`, `snow_new_sum_cm→fresh_snow`. Nicht-Alarm-Keys (`cloud_avg_pct`, `sunny_hours_h`, `uv_index_max`, `snow_depth_cm`) werden verworfen.
2. **Entscheidung A (PO, final): die 4 schalter-losen Metriken bekommen Schalter.** Idealwerte-Tab wird um **Böen** (`gust`), **Gewitter-Energie/CAPE** (`cape`), **Frostgrenze** (`freezing_level`), **Min-Temperatur** (`temperature_min`) erweitert (Experten-Zielgruppe → CAPE sichtbar). Der Mapper deckt dann alle 14 Metriken ab; jede folgt ihrem Schalter (aktiv=feuert, deaktiviert=stumm).
3. **Entscheidung B (PO, final): ich migriere.** Migrations-Skript setzt auf bestehenden Compare-Presets `active_metrics` auf den **vollen Satz** verfügbarer Metriken (bewahrt heutiges „alle feuern", jetzt explizit + abschaltbar) → kein stilles Verstummen.
4. Übergib das gebaute Objekt IMMER als `display_config=` an `AlertEvaluationConfig` (nie mehr `None` aus diesem Pfad).

`levels`/Preset-JSON bleiben unangetastet (reine Auswertungslogik).

## Expected Behavior

- **Input:** Compare-Preset mit `display_config.active_metrics` + Δ-Wetter (cached vs. fresh).
- **Output:** Alarm feuert nur für **aktive** Metriken (+ die schalter-losen Sicherheits-Metriken); deaktivierte Metriken feuern NICHT.
- **Side effects:** keine (nur Auswertung).

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset mit `active_metrics=["temp_max_c"]` (Wind also deaktiviert), leeres `metric_alert_levels`, und ein Wind-Δ über Standard-Schwelle / When der Compare-Δ-Alarm ausgewertet wird / Then feuert **kein** Wind-Alarm.
  - Test: `CompareAlertService.evaluate` mit cached/fresh + Wind-Delta; kein Wind-Trigger im Ergebnis.

- **AC-2:** Given dasselbe Preset und ein Temperatur-Δ über Schwelle / When ausgewertet / Then feuert der **Temperatur**-Alarm (aktive Metrik bleibt aktiv).
  - Test: Temp-Delta → Temp-Trigger vorhanden.

- **AC-3 (Frontend + Filter, die 4 neuen Schalter):** Given der Compare-Editor mit den neuen Idealwerte-Schaltern Böen/CAPE/Frostgrenze/Min-Temperatur / When der Nutzer z.B. **Böen aktiviert und CAPE deaktiviert** und speichert / Then persistiert `active_metrics` entsprechend, und im Alarm feuert ein Böen-Δ, ein CAPE-Δ **nicht**.
  - Test: Frontend-Toggle → `active_metrics` enthält `gust`, nicht `cape`; Backend: gust-Δ triggert, cape-Δ nicht.

- **AC-4 (Migration):** Given bestehende Compare-Presets ohne `active_metrics` / When das Migrations-Skript läuft / Then haben sie danach `active_metrics` mit dem vollen Metrik-Satz gesetzt (Backup angelegt, idempotent), und ihr Alarm feuert wie zuvor (kein Verstummen).
  - Test: Skript auf Fixture-Presets → `active_metrics` gesetzt = voller Satz; zweiter Lauf idempotent; Alarm-Auswertung feuert weiter.

- **AC-5:** Given der Trip-Δ-Alarm-Pfad mit identischer Metrik-Konfiguration / When ausgewertet / Then unverändertes Verhalten (keine Regression durch den geteilten Engine-Pfad).
  - Test: bestehende Trip-Alert-Tests bleiben grün.

- **AC-6:** Given `active_metrics` mit Summary-Keys `["temp_max_c","precip_sum_mm","visibility_min_m"]` / When in Katalog-IDs übersetzt / Then werden `temperature`/`precipitation`/`visibility` korrekt als aktiv erkannt (kein Vokabular-Mismatch, der aktive Metriken fälschlich unterdrückt).
  - Test: Δ auf temperature/precipitation/visibility → jeweils Trigger; Δ auf nicht-gelistetem wind → kein Trigger.

## Known Limitations

- Summary-Keys ohne Alarm-Katalog-Gegenstück (`cloud_avg_pct`, `sunny_hours_h`, `uv_index_max`, `snow_depth_cm`) bleiben reine Vergleichs-Metriken (kein Alarm) und beeinflussen die Filterung nicht.
- CAPE wird als Nutzer-Schalter sichtbar (Experten-Zielgruppe, PO-Entscheidung) — technischer Gewitter-Energie-Wert.
- Nach der Migration feuern Alt-Vergleiche wie bisher „alles", jetzt aber explizit und pro Metrik abschaltbar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reuse des bestehenden #961-Engine-Filters; nur der Compare-Pfad reicht (analog Trip) sein display_config durch. Neuer Mapper ist lokale Übersetzungslogik, keine Architektur-Änderung.

## Changelog

- 2026-07-12: Initial spec (Bug #1191, Nebenbefund F006 aus #1170; Root-Cause + Vokabular-Mismatch via Analyse bestätigt).
