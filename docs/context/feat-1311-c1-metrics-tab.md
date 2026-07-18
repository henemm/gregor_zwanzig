# Context: feat-1311-c1-metrics-tab

## Request Summary

Scheibe C1 aus Epic #1301 (Issue #1311): Neuer Tab **„Wetter-Metriken"** als geteilter Baustein für Trip UND Ortsvergleich. `active_metrics` wird dort explizit gesetzt statt implizit über das `notify`-Flag der Korridore; löst #1293 (Trip-Wertebereiche-Pool) an der Wurzel. PO-Entscheide verbindlich: „wie beim Trip — geteilter Baustein", „erweitern, nicht nachbauen", keine Attrappen (Einstellungen ohne Mail-Wirkung sind der Kern-Befund des Epics).

## Befunde der drei Explore-Agenten (2026-07-18, Stand bb6544de)

### Trip-Seite

| Fakt | Referenz |
|---|---|
| `WeatherMetricsTab.svelte` existiert, **1027 Zeilen**, trip-gebunden | `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` |
| Props: `trip`, `createMode?`, `onChannelsChange?`, `onTripUpdate?`, `saveController?` | `:57-66` |
| Metrik-Katalog via `GET /api/metrics` (selectable-gefiltert) | `:257-258` |
| Persistiert Buckets (primary/secondary/off) + friendlyMap + horizonsMap + telegramKurzform + smsThresholds | `buildWeatherPayload()` `:428-445` |
| Save = ZWEI PUTs: `PUT /api/trips/{id}/weather-config` + `PUT /api/trips/{id}` | `:465,469,495,497` |
| Save-Gate `weatherSaveGate` blockt ohne echte Nutzer-Geste (#1234) | `:454,489` |
| Trip-Tabs: `route·etappen·wetter·reports·alarmregeln` — Wetter-Tab mountet `<WeatherMetricsTab {trip} />` | `TripEditView.svelte:42-65,200-201` |
| **#1293-Wurzel bestätigt, aber präzisiert:** `buildRoutePool` speist den Trip-Wertebereiche-Pool aus **6 hartkodierten** AlertableMetrics — völlig UNABHÄNGIG von der Metrik-Auswahl im Wetter-Tab | `shared/corridor-editor/corridorEditorState.ts:29-36,65-85` |
| Tests: `metricsEditor.test.ts`, `corridorEditorState.test.ts:33-69` (buildRoutePool: confidence-Ausschluss, 6er-Pool) | — |

### Compare-Seite

| Fakt | Referenz |
|---|---|
| `COMPARE_TABS`: **7 Tabs** `uebersicht·orte·idealwerte·layout·alarme·versand·vorschau` | `compareTabsResolve.ts:7-17` (Achtung: .ts, nicht .js) |
| `active_metrics` wird heute aus dem `notify`-Flag der Korridore abgeleitet — NUR für 10 hartkodierte alarmfähige Metriken | `corridorEditorState.ts:387-445` (`buildCompareCorridorSavePayload`, `:431-432`), 10er-Liste `:200-203` |
| Gelesen/gespeichert via `compareEditorSave.ts:96-102` — `undefined` = nicht editiert → Round-Trip (RMW-Vorbild) | — |
| `unknownCorridors`-Pass-Through (Datenerhalt-Muster) | `corridorEditorState.ts:271-293,437-440` |
| Wertebereiche-Tab compare = `CorridorEditor`/`CorridorEditorMobile` mit Pool aus `COMPARE_METRIC_DEFS` = **14 Metriken** | `CompareTabs.svelte:49,52,115-122`, `corridorEditorState.ts:238-254` |
| Teilungs-Vorbild `AlarmeTab.svelte`: `context: 'route'|'vergleich'`, Props-Differenzierung (route: trip+saveController; vergleich: wiz-State), Sections-Config `alarmeTabSections.ts:21-26` | `AlarmeTab.svelte:42-51,87-92` |
| Preset-Felder: `display_config.active_metrics: []string` (absent = Legacy = alle alarmfähigen), `display_config.ideal_ranges`, Top-Level `corridors[]` | `api_contract.md:1320-1345,1379-1380` |
| `CompareEditor.svelte` (Legacy, Route weggeleitet seit S3) mountet CorridorEditor direkt — wird mit F2 gelöscht, hier NICHT anfassen | `CompareEditor.svelte:37-57` |

### Vertrag/Backend

| Fakt | Referenz |
|---|---|
| `GET /api/metrics`: EIN Endpoint für beide Seiten, `selectable`-Filter (Confidence #710 draußen) | `api/routers/config.py:31-55`, `metric_catalog.py:220-228,451` |
| Compare-Renderpfad liest `active_metrics` + `hourly_metrics` über `resolve_compare_render_options` | `report_config_resolver.py:166-231` |
| Trip-Briefing liest `UnifiedWeatherDisplayConfig.metrics` (models.py:566) über `resolve_report_render_options` | `report_config_resolver.py:102-147` |
| Compare-Preset-Save: Go `UpdateComparePresetHandler` mit serverseitigem RMW (`mergeConfigMap`, #582/#1159) → `briefings/{id}.json` | `compare_preset.go:259-327` |
| Epic #1230 Konvergenz: Scheiben 5-7 (kind-Diskriminator, /api/briefings, Persistenz-Cutover) offen — C1 darf NICHT auf ungebaute #1230-Strukturen aufsetzen | `docs/specs/modules/issue_1250_briefing_subscription.md` |
| `reportConfigDirty.ts` (#1269): geteilte normalisierungsbewusste Diff-Logik — neuer Tab nutzt sie (WeatherMetricsTab tut es bereits) | `shared/reportConfigDirty.ts:39-53` |

## Kern-Analyse (Design-Richtung)

**Zwei verschiedene Metrik-Datenmodelle:** Trip = `display_config.metrics` (reiche `MetricConfig`-Liste: Buckets, friendly, Horizonte, SMS-Schwellen), Compare = `display_config.active_metrics` (flache String-Liste). Die Compare-Mail konsumiert NUR an/aus (+ separat `hourly_metrics`). Buckets/Horizonte/friendly hätten beim Vergleich KEINE Mail-Wirkung → sie im Vergleich anzubieten, würde exakt die Attrappen-Klasse reproduzieren, die das Epic beseitigt (#1291/#1287).

**Folgerung (AlarmeTab-Muster):** `WeatherMetricsTab` wird geteilt mit `context="route"|"vergleich"`; im Kontext `vergleich` zeigt er NUR die wirksamen Bedienelemente (Metrik an/aus → `active_metrics`), im Kontext `route` unverändert alles Bisherige. Extraktion nach `shared/`, Trip-Verhalten bit-identisch (Regressionsschutz), Compare-Zweig schreibt über den bestehenden `compareEditorSave`-RMW-Pfad.

**Entkopplung von den Korridoren:** Das `notify`-Flag der Korridore hört auf, `active_metrics` zu SCHREIBEN (die implizite Ableitung `corridorEditorState.ts:431-432` entfällt); Korridore behalten ihre Alarm-Funktion, `active_metrics` gehört dem neuen Tab. Migrationsverhalten für Bestands-Presets (absent = Legacy-Semantik „alle alarmfähigen") MUSS erhalten bleiben.

**#1293-Wurzelfix (Trip):** `buildRoutePool` bezieht den Pool statt aus der 6er-Hartkodierung aus der Metrik-Auswahl des Tabs (geschnitten auf korridorfähige Metriken). Genauer Schnitt in der Spec.

## Risks & Considerations

- **Datenverlust-Klasse #102:** Alle Writes als RMW-Merge; `unknownCorridors`-Muster und `undefined`-heißt-unangefasst-Semantik (compareEditorSave) erhalten. Schema-relevante Dateien (models.py u.a.) triggern den Backup-Hook.
- **1027-Zeilen-Komponente teilen:** Extraktion nach `shared/` mit context-Zweigen — Verstoß-Gefahr „Compare-Kopie statt Teilung" ist der dokumentierte Default-Fehler (#1170). Adversary-Punkt.
- **Legacy-Semantik `active_metrics` absent:** absent ≠ leer (api_contract.md:1379). Der Tab darf beim bloßen Öffnen ohne Nutzer-Geste NICHTS schreiben (weatherSaveGate-Muster #1234 + reportConfigDirty #1269).
- **LoC-Limit 250 wird gerissen** (Plan kündigt an) — Override-Frage mit konkreter Schätzung vor Implementierung.
- **Parallel-Sessions:** B4 (backend/Renderer) keine Überschneidung; `precious-chasing-frost` (S4a-Tests) baut auf „Hub = Bearbeiten-Fläche" — F1-Abstimmung erst nach C, hier nur nicht kollidieren (keine Test-Migrationen anfassen).
- **Staging-E2E:** Svelte-5-Reaktivitäts-Races werden nur auf Staging sichtbar — E2E mit PUT-Count über den echten Klick-Pfad einplanen.
- **Frontend-only-Scope wahrscheinlich NICHT gegeben:** evtl. Backend-Anteil, falls `resolve_compare_render_options` oder Preset-Validierung angepasst werden muss — in der Spec klären.

## Existing Specs

- `docs/specs/modules/issue_1250_briefing_subscription.md` (#1230-Konvergenz — Abgrenzung)
- `docs/specs/modules/issue_1298_compare_metric_guard_cape_label.md` (B2/B3, Metrik-Wächter liest `compareMetricDefs.ts` — bei neuen Metrik-Flüssen Wächter beachten)
- Epic-Plan `~/.claude/plans/warum-verweist-du-immer-crispy-ladybug.md`, Abschnitt C1
