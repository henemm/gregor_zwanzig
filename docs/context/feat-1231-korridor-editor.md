# Context & Analyse — feat-1231-korridor-editor

**Issue:** #1231 „Phase 1 — Korridore: Alerts + Idealwerte vereinen" (Sub-Issue Epic #29, `stable_id=korridor-editor-phase1`)
**Modus:** AENDERUNG an bestehenden Editoren (Trip-Alerts-Tab, Compare-Idealwerte-Tab, Alert-Backend)
**Analyse:** feature-planner (Sonnet), 2026-07-12. PO-Entscheidungen: Henning, 2026-07-12 (s.u.).

---

## PO-Entscheidungen (2026-07-12, bindend für die Spec)

- **(A) Warn-Mechanik:** Bestehende Trip-Warn-Mechanik (Δ-Abweichungs-Wächter seit #817, Empfindlichkeit je Metrik vom User einstellbar) bleibt UNVERÄNDERT und wird für Ortsvergleiche in gleicher Form verwendet (Compare-Δ-Alarm existiert seit #1191). **Keine neue Warn-Logik erfinden.** `corridor.notify` ist die Oberflächen-Steuerung, welche Metrik warnt — die Trigger-Mechanik dahinter bleibt die heutige. Insbesondere KEINE Rückkehr zu absoluten Schwellwert-Warnungen als Ersatz des Δ-Wächters.
- **(B) Wizard:** `CorridorEditor context="vergleich"` ersetzt die Idealwerte-UI an BEIDEN Stellen — Compare-Wizard Step 3 UND Editor-Tab (heute beide `Step3Idealwerte.svelte`). Eine Bedienung, kein Fork.
- **(C) Kanäle:** Vergleichs-Briefings gehen ausschließlich per E-Mail (keine Kanal-Auswahl). Alert-Kanäle = bestehende Trip-Kanalwahl wiederverwenden. **Kein neues `alertChannels[]`-Konstrukt**, kein neuer AlertChannelPicker.

Frühere bindende PO-Entscheidungen aus dem Issue-Body: User-Label „Wertebereich(e)", Code-Term bleibt `corridor`; C1 Neutralität (prio ist nur Reihenfolge, kein Rang); C2 offene Seiten via `null`; C5 `corridorInside()` als Single-Source Backend == Frontend.

---

## Ist-Zustand (Befund feature-planner)

### Frontend
- **Trip · Alerts-Tab:** `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` (171 Z.) + `AlertMetricLevelTable.svelte` (186 Z.) — seit #1232 nur Heading + Onboarding + Metrik-Level-Tabelle (off/entspannt/standard/sensibel je Metrik). Zustell-Controls bereits in `shared/VersandTab.svelte` (context="route"), Save-Payload `shared/versand-tab/alertDeliveryPayload.ts`.
- **Compare · Idealwerte:** `frontend/src/lib/components/compare/steps/Step3Idealwerte.svelte` (235 Z.) mit `RangeSlider.svelte` — voll funktional, genutzt vom Compare-**Wizard** Step 3 UND vom **CompareEditor**-Tab `idealwerte` (`CompareEditor.svelte:25,690,854`).
- **Mark-Effekt heute nur im FE-Preview:** `shared/layout-tab/ltIdealRange.ts::isIdealGood()` (fast identisch zu `corridorInside`, mit Demo-Fallback).
- **Tabs:** `trip-detail/TripTabs.svelte:64-69` („Inhalt", „Alerts"), `compare/CompareEditor.svelte:51-55` TAB_DEFS („Idealwerte").

### Backend
- **Go `internal/model/trip.go:53-64`:** `AlertRule{ID, Kind(absolute|delta), Metric, Threshold, Unit, Severity, Enabled, PairID, DeltaWindow, Channels}`. `SyncAlertRules()` (trip.go:210+) erzwingt für die 6 `AlertableMetrics` genau eine Kind=delta-Regel je aktiver Metrik, migriert absolute→delta (#817).
- **Python:** `src/services/weather_change_detection.py` (Kinds ABSOLUTE/DELTA/THRESHOLD_CROSSING), `alert_preset.py`, `trip_alert.py`, `deviation_alert_engine.py`.
- **Idealwerte-Persistenz:** nur opaque in `Trip/ComparePreset.DisplayConfig["ideal_ranges"]` (`map[string]interface{}`), Go interpretiert nie (Read-Modify-Write-Passthrough).
- **Compare-Mail:** `src/output/renderers/email/compare_html.py` hat KEINE Idealbereich-Markierung — nur Severity-Färbung. „mark im Briefing" = NEUE Backend-Funktion.
- **Scoring:** `src/services/comparison_scoring.py::calculate_score()` noch aktiv; Neutralisierung ist eigenes Issue #1229 — mark darf dort NICHT andocken.

### Design-Referenzen (JSX = Wahrheit)
- `claude-code-handoff/current/jsx/corridor-editor.jsx` (Desktop; Exports corridorInside, corridorFmt, CorridorEditor, CorridorBand, CorridorRow, CORRIDOR_CTX/SEED/POOL, CompareEndDateControl [Phase 2])
- `claude-code-handoff/current/jsx/corridor-editor-mobile.jsx` (Card je Metrik, Touch ≥44px, ±-Stepper, dual-handle Band; importiert Logik aus Desktop-File)
- `nav-map.jsx` zeigt noch „Alerts" — stale, Issue-Body-Naming („Wertebereiche") gewinnt.

---

## Delta (unter Berücksichtigung der PO-Entscheidungen)

1. Typ `Corridor{metric, range:[min|null,max|null], notify, mark, prio?}` — Go (Trip + ComparePreset) + TS. Additiv neben `alert_rules`/`ideal_ranges` bis Cutover verifiziert.
2. `corridorInside()`/`corridorFmt()` als Single-Source: FE-Util (ersetzt `isIdealGood`-Duplikat) + Python-Pendant für Compare-Mail-Renderer.
3. `mark` im Compare-Mail-Renderer (`compare_html.py`) — NEU: Markierung wenn `corridorInside(v)===true`. Kein Einfluss auf `calculate_score` (C1, #1229).
4. `notify` verdrahtet mit BESTEHENDER Warn-Mechanik (Δ-Wächter; Enabled-Steuerung je Metrik) — keine neue Trigger-Logik (PO-A).
5. `CorridorEditor`/`CorridorEditorMobile` als Svelte-Organismen (Port aus JSX); ersetzen `AlertsTab`+`AlertMetricLevelTable` (Trip) und `Step3Idealwerte` (Compare-Wizard Step 3 + Editor-Tab, PO-B).
6. Migration `scripts/migrate_1231_corridors.py` (Vorbilder migrate_946/migrate_1191): `ideal_ranges`→`corridors[mark]`; Alert-Enabled/Empfindlichkeit→`corridors[notify]`-Ansicht; Dry-Run + Report, verlustfrei (C4); deaktivierte Metriken bleiben deaktiviert (#1191-Erhalt).
7. Tab-Renames: „Inhalt"→„Wetter-Metriken", „Alerts"→„Wertebereiche" (Trip), „Idealwerte"→„Wertebereiche" (Compare) + Playwright-Testid-Folgen (7 E2E-Specs referenzieren alte Testids).
8. ENTFÄLLT (PO-C): AlertChannelPicker / `alertChannels[]`.

## Slicing (je Slice ≤ ~250 LoC, eigene Workflows analog #1232)

1. Datenmodell + corridorInside Single-Source (additiv, ~120–180 LoC)
2. Migrationsskript + Dry-Run + Report (~200–250 LoC)
3. CorridorEditor Desktop context="route" (~230 LoC)
4. CorridorEditor Desktop context="vergleich" inkl. Wizard Step 3 (~200 LoC)
5. CorridorEditorMobile beide Contexts (~230 LoC)
6. Tab-Renames + Nav + Testid-Migration (~150 LoC)
7. mark im Compare-Mail-Renderer (~180 LoC)

## Risiken

- Bestandsdaten-Erhalt: Schema-Dateien (`trip.go`, `compare_preset.go`, `models.py`, `loader.py`) → data_schema_backup-Hook; additives Feld, Read-Modify-Write, kein Replace.
- #1191-Regression: Migration darf deaktivierte Compare-Metriken nicht reaktivieren; leeres `[]` ≠ fehlend.
- C1: mark nie in `calculate_score` (#1229 parallel offen).
- confidence_pct bleibt nicht wählbar (#710) — darf im CorridorEditor-Metrikpool nicht auftauchen.
- Mail-Renderer-Slice triggert Renderer-Commit-Gate (#811) + email_spec_validator (compare-Pfad).

## Betroffene Dateien (Kern)

`frontend/src/lib/components/alerts-tab/*`, `compare/steps/Step3Idealwerte.svelte`, `compare/CompareEditor.svelte`, `trip-detail/TripTabs.svelte`, `shared/layout-tab/ltIdealRange.ts`, neu `shared/corridor-editor/*`; `internal/model/trip.go`, `internal/model/compare_preset.go`; `src/app/models.py`, `src/app/loader.py`, `src/output/renderers/email/compare_html.py`; `scripts/migrate_1231_corridors.py` (neu).
