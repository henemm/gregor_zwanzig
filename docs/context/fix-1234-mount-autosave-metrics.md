# Context: fix-1234-mount-autosave-metrics

**Issue:** #1234 — Datenverlust-Risiko: Mount-Auto-Save im Inhalt-Tab kann `display_config.metrics` mit `[]` überschreiben
**Track:** Full Process (Score 4/6 — Blast Radius High: stiller Datenverlust)
**Erstellt:** 2026-07-14

## Request Summary

Öffnet ein Nutzer im Trip-Editor den Tab „Inhalt", ohne etwas zu ändern, kann ein verzögertes Auto-Save die konfigurierten Wetter-Metriken mit einer **leeren Liste** überschreiben. Der Fix muss den stillen Datenverlust beseitigen, **ohne** den legitimen Fall „Nutzer wählt bewusst alle Metriken ab" unmöglich zu machen.

## Die Kausalkette (belegt, nicht vermutet)

| # | Stelle | Was passiert |
|---|--------|--------------|
| 1 | `WeatherMetricsTab.svelte:67` + `:491` | `loading` startet auf `false`; der Loading-Guard `{#if loading && Object.keys(catalog).length === 0}` greift beim ersten Render **nicht**. Kindkomponenten mounten, bevor der Katalog geladen ist. **Das ist die Enabling Condition.** |
| 2 | `EditReportConfigSection.svelte:104-171` | `onMount` liest `reportConfig` und migriert Defaults in lokale States. |
| 3 | `EditReportConfigSection.svelte:174-216` | Write-Back-`$effect` schreibt einen **normalisierten, vollständig aufgefüllten** Blob zurück in die gebundene Prop (`enabled`, `morning_time` als HH:MM:SS, alle `show_*`-Defaults, `daily_summary_metrics`…). Weicht fast immer vom sparsamen Original ab. |
| 4 | `WeatherMetricsTab.svelte:461-468` | Watch-`$effect` vergleicht `JSON.stringify(reportConfig)` gegen `_lastReportConfigJson` (initialisiert aus dem **Prop-Rohwert**). Der Diff aus (3) sieht aus wie eine Nutzeränderung → `scheduleAutoSave()`. |
| 5 | `WeatherMetricsTab.svelte:447-457` | `scheduleAutoSave()` baut den Payload **sofort** (`buildWeatherPayload()`), debounced nur den PUT. |
| 6 | `WeatherMetricsTab.svelte:400-417` + `:64`/`:73` | `buildWeatherConfigMetrics(buckets, …, catalog)` mit noch leeren `buckets`/`catalog` → `metrics: []`. Der Key ist **immer** im Payload, nie abwesend. |
| 7 | `internal/handler/weather_config.go:61-69` | Feld-Level-Merge (#1151) schützt die **Geschwister-Keys** von `metrics`, nicht `metrics` selbst → `[]` wird übernommen. |
| 8 | `internal/handler/weather_config.go:71-72` → `internal/model/trip.go:227` | **Kaskade (im Issue nicht erwähnt):** `SyncAlertRules(trip.AlertRules, [])` → `result := []AlertRule{}` → **alle Alarm-Regeln des Trips werden ebenfalls gelöscht.** |

**Folgeschaden lesend:** `src/services/weather_change_detection.py:175` — `if not display_config.metrics: return False` → nach dem Unfall feuert **kein** Wetteränderungs-Alarm mehr.

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | **Primär.** Auto-Save-Gate fehlt, Loading-Guard wirkungslos, Watch-Baseline falsch initialisiert |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | **Primär.** Mount-Write-Back nicht von Nutzeränderung unterscheidbar |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts:67` | `schedule(fn, 700)` — Debounce-Mechanik, nur EIN pending Save |
| `internal/handler/weather_config.go` | Merge-Ebene; Alert-Rules-Kaskade |
| `internal/model/trip.go:227` | `SyncAlertRules` |

## Dependents von EditReportConfigSection (Regressionsfläche)

| Aufrufer | mode | saveController | Auto-Save-Watch? |
|---|---|---|---|
| `trip-detail/WeatherMetricsTab.svelte:691-697` | edit | ja | **ja — der Bug** |
| `edit/TripEditView.svelte:203` | edit | nein | nein |
| `briefings-tab/BriefingsTab.svelte:40` | edit | nein | nein |
| `trip-new/TripNewEditor.svelte:765/:990` | create | — | nein (`createMode` → kein PUT) |

Ein Eingriff **in** `EditReportConfigSection` trifft alle vier. Ein Eingriff in `WeatherMetricsTab` trifft nur den Bug-Pfad. Das ist ein Argument für den Fix in der Elternkomponente.

## Existing Patterns (im Repo etabliert)

- **Save-Gate statt blindem Schedule:** `shared/corridor-editor/corridorEditorState.ts:517-519` `saveGateDecision(rows): 'schedule' | 'dirty'` — bei ungültigem/unvollständigem State wird **nicht** geschedult, nur `setDirty()`. Nutzung: `CorridorEditor.svelte:126-132`. **Das ist das Vorbild.**
- **JSON-Diff-Guard mit Prop-Rohwert-Baseline** (das fehlerhafte Muster, 3× im Repo): `WeatherMetricsTab.svelte:461`, `BriefingScheduleTab.svelte:68-79`, `shared/VersandTab.svelte:239-259`.
- **Dirty-Snapshot:** `WeatherMetricsTab.svelte:156-165` (`isDirty` gegen `savedSnapshot`, gesetzt in `initFromTrip()`).
- **`untrack()`** gegen Selbst-Trigger in Effects: `routes/trips/+page.svelte:102-112`.

## Trip/Compare-Teilung (CLAUDE.md-Invariante)

Der Orts-Vergleich hat **keinen** Inhalt-/Metriken-Tab (`CompareEditor.svelte:77`: `vergleich, orte, idealwerte, layout, versand, alarme`) und **kein** Debounce-Auto-Save (nur expliziter Speichern-Button). Der Bug existiert dort also nicht.

Das ist zugleich ein **vorbestehender Verstoß** gegen die Teilungs-Invariante (Trip-only-Tab ohne Pendant) — **nicht Teil dieses Fixes**, gehört als Nebenbefund ins Sammel-Issue #1199.

## Design-Entscheidung: Warum der Fix NICHT ins Backend gehört

Ein Backend-Guard „leere `metrics`-Liste ablehnen" würde #1234 stoppen — und gleichzeitig den legitimen Fall „Nutzer wählt bewusst alle Metriken ab" unmöglich machen. Genau diese Unterscheidung („leer ≠ nie konfiguriert") hat das Projekt im Orts-Vergleich bei **#1191** bewusst hergestellt (`compareEditorSave.ts:94-100`). Wir würden einen Datenverlust-Bug gegen einen Semantik-Rückschritt eintauschen.

**Konsequenz:** Der Client muss aufhören, Unsinn zu senden. Das Backend darf ihm weiter glauben.

## Risks & Considerations

- **R1 — Halbherziger Guard:** Ein Fix nur am `reportConfig`-Watch (Kette Schritt 4) lässt die anderen 8 `scheduleAutoSave()`-Aufrufer offen, die ebenfalls vor Hydration feuern könnten. Das Gate gehört **in `scheduleAutoSave()` selbst** (Schritt 5).
- **R2 — Legitime Abwahl:** Der Fix darf „alle Metriken abwählen" nicht blockieren. Ein Payload-Guard „`metrics: []` nie senden" wäre also falsch; korrekt ist „nicht senden, solange nicht hydriert".
- **R3 — Regressionsfläche:** Änderungen an `EditReportConfigSection` treffen 4 Aufrufer inkl. Create-Flow.
- **R4 — Latente Zwillinge:** `BriefingScheduleTab.svelte:68-79` und `shared/VersandTab.svelte:239-259` benutzen dieselbe fehleranfällige Baseline-Initialisierung. Kein Datenverlust (sie schreiben keine `metrics`), aber spurious Saves. Prüfen, ob im Scope oder Nebenbefund.
- **R5 — Parallelarbeit:** In anderer Session läuft `feat-1256-s4-layouttab` (Layout-Tab). Andere Datei, aber benachbart. Bei Berührung abstimmen.
- **R6 — Reproduktion:** Bisher nur im Playwright-Kontext deterministisch. Der Repro-Test muss den Wettlauf zuverlässig treffen (Katalog-Fetch verzögern), sonst ist er ein Flake-Test ohne Beweiskraft.

## Nächster Schritt

`/20-analyse` — Fix-Ansätze gegeneinander abwägen (Gate-Ort, Baseline-Reset, Loading-Guard), Adversary-Fragen an den Ansatz.
