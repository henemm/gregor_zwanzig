# Context: feat-1301-c2-hub-zugang (C2 von Epic #1301)

## Request Summary

Die einzige Ortsvergleich-Layout-Einstellung mit echter Mail-Wirkung — „Metriken im
Stundenverlauf" plus der „Stundenverlauf ein/aus"-Schalter — ist seit Slice S3
(`080e96d8`, live 2026-07-17) nicht mehr erreichbar, weil sie in `CompareInhaltSection`
hängt, die nur vom weggeleiteten `CompareEditor` gerendert wird. C2 holt diese Steuerung
in den erreichbaren Hub (`CompareTabs`, Layout-Tab). Die nie wirkenden Bedienelemente
(Top-N, „Spalte vs. Detail"-Zuordnung) kommen **nicht** mit — aber ihre gespeicherten
Werte bleiben erhalten. Behebt #1299, #1291, #1287.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` (1851 Z.) | **Der Hub.** Layout-Tab bei `:1205` zeigt heute NUR schreibgeschützte Kanal-Pillen (`CompareLayoutRow`) — hier kommt die Stundenverlauf-Steuerung rein. Persist-Bridge-Muster je Tab (Hydration-`$effect` + Snapshot + Commit-Handler). C1-Vorbild: `handleWetterMetrikenCommit` `:635-663` |
| `frontend/src/lib/components/compare/CompareInhaltSection.svelte` (169 Z.) | Enthält HEUTE die unerreichbare Steuerung: „Stundenverlauf"-Toggle `:90-95`, Top-N-Input `:100-117`, „Metriken im Stundenverlauf"-Checkboxen `:119-134`, plus doppelter „Amtliche Warnungen"-Toggle `:84-89`. Wird NUR von `CompareEditor:941` gerendert. Wird in F2 gelöscht — **nicht** darauf aufbauen |
| `frontend/src/lib/components/compare/CompareEditor.svelte` (1686 Z.) | Weggeleiteter Editor (Route `compare/[id]/edit` ist seit S3 reiner Redirect-Platzhalter). Rendert `CompareInhaltSection`. Wird in F2 gelöscht — **nicht** anfassen |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | Reine Persist-Funktionen: `buildHubPutPayload` `:95`, `flushPendingCorridorSave`/`Versand`/`Alarm`. Hier kommt `flushPendingLayoutSave` rein (analog) |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | C1-Vorbild: `hydrateWeatherMetricsFromPreset` + `flushPendingWeatherMetricsSave` — **exakte** Schablone für Hydration + Flush der Stundenverlauf-Felder |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `buildComparePresetSavePayload` — RMW-Kern. `hourly_metrics`/`hourly_enabled` sind bereits verdrahtet (`:104-111`, `:142`). `top_n`/`channel_layouts`/`forecast_hours`/`hour_from`/`hour_to` round-trippen per `...original`-Spread, solange die Bedienung sie nicht setzt (`:130-132`) |
| `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts` | `ALL_HOURLY_METRICS` (9 Keys) — eigenständiges Compare-Vokabular (Rohwerte/Stunde), bewusst KEIN Reuse von `compareMetricDefs.ts` |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | Hält `hourlyMetricKeys` `:33`, `hourlyEnabled` `:48`, `topN` `:75`, `channelLayouts` `:36` — bereits alle vorhanden |
| `frontend/src/lib/components/compare/compareTabsResolve.ts` | `COMPARE_TABS` — Tab-Reihe (uebersicht·orte·wetter-metriken·idealwerte·layout·alarme·versand·vorschau). Layout-Tab existiert bereits |

## Existing Patterns

- **Hub-Persist-Bridge (C1, S5–S7):** Pro Tab: (1) `$effect` hydriert bei erstem Öffnen aus
  `currentPreset`, (2) `currentXSnapshot()` liefert Vergleichs-Snapshot, (3) `handleXCommit`
  ruft `flushPendingXSave` (No-Op bei unverändertem Snapshot → `markPristine`), sonst PUT via
  `hubPutQueue.enqueue`, Rollback bei Fehler. Wrapper mit `onchange`/`onfocusout`/`onclick`
  (Bubble-Phase, Staging-Fund SF-1). **Exaktes Vorbild für den Layout-Tab.**
- **RMW-Datenerhalt:** `buildComparePresetSavePayload` spreadet `...original` (Body) und
  `...original.display_config` (displayConfig); ein Feld wird NUR überschrieben, wenn die
  Edits es explizit liefern. `buildHubPutPayload` liest `channel_layouts`/`top_n` aus dem
  bestehenden `displayConfig` und reicht sie unverändert durch → strukturell verlustfrei.
- **Leere-Auswahl-Semantik:** `hourly_metrics` = `[]` → Key wird gelöscht (Default „alle
  sichtbar", `compareEditorSave.ts:104-111`). Zu unterscheiden von `active_metrics=[]`
  (explizit als `[]` persistiert, #1191).

## Dependencies

- **Upstream (was C2 nutzt):** `wizardState.hourlyMetricKeys`/`hourlyEnabled`, `ALL_HOURLY_METRICS`,
  `buildHubPutPayload`, `hubPutQueue`, `saveController`, C1-Save-Muster.
- **Downstream (was von den Feldern abhängt):** Compare-Mail-Renderer liest `display_config.hourly_metrics`
  + `hourly_enabled` (`compare_html.py`, `compare_hourly_metric_ids.py`). Keine API-Änderung nötig —
  der PUT-Endpoint `/api/compare/presets/{id}` und der Go-RMW-Merge bleiben unverändert.

## Existing Specs

- `docs/specs/modules/compare_weather_metrics_tab.md` — C1-Spec (geteilter Metriken-Tab), Muster-Vorbild
- `docs/specs/modules/issue_1106_hourly_metrics_config.md` — ursprüngliche Stundenverlauf-Metrik-Spec
- `docs/specs/modules/issue_679_compare_editor_edit.md` — Save-Payload-RMW-Prinzip

## Risks & Considerations

- **Datenverlust (PFLICHT, #102/BUG-DATALOSS-GR221):** `top_n`, `channel_layouts`,
  `forecast_hours`, `hour_from`, `hour_to` dürfen NUR aus der Bedienung verschwinden, nicht
  aus der Persistenz. Strukturell schon abgesichert (RMW-Spread) — muss per Roundtrip-Test
  gegen Regress verriegelt werden.
- **#1291-Semantik:** „Im Briefing als Spalte" vs. „als Detail" ist bedeutungslos (Epic-Antwort:
  „Gruppe 2 gibt es nicht"; die Matrix zeigt Metriken IMMER als Zeilen, Orte als Spalten). Nur
  „Metriken im Stundenverlauf" wirkt → alleine übernehmen.
- **Trip/Compare-Invariante:** `hourly_metrics` ist echtes Compare-eigenes Vokabular (Rohwerte/Stunde,
  `compareHourlyMetricDefs.ts`-Kommentar) — kein Trip-Pendant. Übernahme als Compare-eigene
  Steuerung ist begründet; in der Spec explizit als Adversary-Punkt festhalten.
- **Doppelter „Amtliche Warnungen"-Toggle (D2-Territorium):** `CompareInhaltSection:84-89` dupliziert
  den AlarmeTab-Toggle. C2 zieht ihn NICHT in den Hub (AlarmeTab hat ihn bereits) — Bereinigung
  der Dublette ist D2. C2 rührt den Alarme-Toggle nicht an.
- **Reaktivitäts-Race (Svelte-5):** Der neue Layout-Commit teilt sich `wizardState` mit
  Nachbar-Tabs; eigener Snapshot-Baseline + Diff-Guard nötig (H3-Kreuzeffekt-Lehre aus S5).
  Staging-E2E mit PUT-Count.
- **F2-Abhängigkeit:** CompareInhaltSection/CompareEditor werden in F2 gelöscht. C2 baut
  self-contained im Hub — keine neue Abhängigkeit auf die doomed Dateien.
