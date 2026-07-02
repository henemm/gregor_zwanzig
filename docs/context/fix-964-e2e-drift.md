# Context: #964 — E2E-Test-Drift + Doppel-Element-Bug

## Request Summary

18 fehlschlagende E2E-Tests in 3 Dateien, entdeckt als Nebenbefund bei #951. Zwei
unabhängige Ursachen: (1) veraltete Test-IDs nach v2-Layout-Migration der
Weather-Metrics-Tab (13 Tests), (2) ein echter Doppel-Element-Bug bei `/trips/new`
(3 Tests).

## Fund 1 — Veraltete Test-IDs (13 Tests, kein Produktbug)

`frontend/e2e/epic-138-metriken-editor.spec.ts` + `frontend/e2e/issue-343-horizon-chips.spec.ts`
erwarten Test-IDs aus dem alten Layout (`bucket-section-primary`,
`weather-metrics-preset-list`, `weather-metrics-preset-row-wandern`, `horizon-chip-*` global,
`table-preview-day-*`). Die AKTUELLE Komponentenstruktur (verifiziert per Grep):

| Alt (Test erwartet) | Neu (Code hat tatsächlich) | Datei |
|---|---|---|
| `weather-metrics-preset-list`/`preset-row-{id}` | `weather-preset-pill-{p.id}` | `WeatherV2PresetBar.svelte:35,49` |
| (kein Äquivalent, Grundauswahl war anders strukturiert) | `wm2-grundauswahl` | `WeatherV2Grundauswahl.svelte:25` |
| `horizon-chip-{id}` global | `horizon-chip-{metric.id}-today/-tomorrow/-day_after` (pro Metrik) | `MetricCheckbox.svelte:120/126/132` |
| `table-preview-day-{day}` | `table-preview-day-{day}` (Format existiert weiter, Kontext geändert) | `TablePreview.svelte:84` |
| `bucket-section-primary` | `bucket-section-{bucket}` — ob `primary` noch gültiger Wert ist: ungeprüft | `BucketSection.svelte:61` |

`PresetRow.svelte` (alte Komponente mit `weather-metrics-preset-row-{id}`) existiert als Datei,
wird aber von `WeatherMetricsTab.svelte`/`WeatherV2PresetBar.svelte` nicht mehr referenziert
(Dead Code, nicht Teil dieses Fixes).

Zusätzlich: Auto-Save-Modell (`WeatherMetricsTab.svelte:483`) — Save-Button erscheint erst bei
`isDirty` (Dirty-Pill `weather-metrics-dirty-pill` Zeile 473). Tests, die einen immer
sichtbaren Save-Button erwarten, müssen das Dirty-Gating berücksichtigen.

**Konsequenz:** Die 13 Tests müssen auf die v2-Test-IDs migriert werden — echte Klick-Pfade
gegen die aktuelle UI-Struktur, nicht nur Selector-Strings blind ersetzen (Reihenfolge/Struktur
der Interaktion hat sich teilweise geändert, z.B. Grundauswahl als neue eigene Sektion).

## Fund 2 — Doppel-Element-Bug (3 Tests, ECHTER Produktbug)

`frontend/src/lib/components/trip-new/TripNewEditor.svelte` rendert **zwei** Inputs mit
identischem `data-testid="trip-new-name-input"`:
- Desktop: Zeile 512-517, in `.tn-desktop`
- Mobile: Zeile 793-800, in `.tn-mobile`, mit Entwickler-Kommentar (Zeile 794-795): "Desktop-Input
  ist display:none auf ≤899px, Playwright findet genau diesen einen sichtbaren" — Annahme war
  falsch für `getByTestId(...).fill()` (kein `.toBeVisible()`-Warten, Playwright Strict Mode
  zählt beide DOM-Knoten unabhängig von CSS-Sichtbarkeit).

CSS-Gating ist reines `display:none`/`display:block` per `@media (max-width: 899px)`
(Zeile 1039-1061) — **kein** Svelte-`{#if}`, beide Inputs bleiben immer im DOM.

Betroffener Test-Helper: `frontend/e2e/issue-661-trip-new-mobile.spec.ts:34`
`await page.getByTestId('trip-new-name-input').fill(name);` — kein `.first()`, kein
Viewport-Scope.

Git-Historie: Vorheriger Fix `af116e4f` ("E2E-Selektoren härten — mobile Tab scopen") hat
andere Locators gehärtet, aber **nicht** `fillRoute()`/dieses Test-ID.

**Root Cause:** Zwei UI-Varianten teilen sich ein Test-ID, statt je einen eigenen zu haben.
Das ist ein Anti-Pattern unabhängig vom aktuellen Testfehler (jeder künftige
`getByTestId('trip-new-name-input')`-Aufruf ist fragil).

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/e2e/epic-138-metriken-editor.spec.ts` | Test-ID-Migration nötig |
| `frontend/e2e/issue-343-horizon-chips.spec.ts` | Test-ID-Migration nötig |
| `frontend/e2e/issue-661-trip-new-mobile.spec.ts` | Locator-Fix (fillRoute-Helper) |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Test-ID-Duplikat auflösen (Zeile 512-517, 793-800) |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` + `WeatherV2*.svelte` | Referenz für aktuelle Test-IDs (read-only) |

## Risks & Considerations

- Fund 1 ist reine Testkorrektur (kein Produktcode), aber der größere Teil (13 Tests, echte
  Klick-Pfade gegen neue UI-Struktur nachbauen) — Risiko: neue Tests könnten "false green"
  werden, wenn sie nicht echtes Nutzerverhalten prüfen (Playwright gegen Staging, nicht
  goto+DB, siehe Projekt-Konvention).
- Fund 2 berührt Produktcode (`TripNewEditor.svelte`) — Test-ID-Rename ist eine reine
  Testbarkeits-Verbesserung, KEINE visuelle/Design-Änderung (kein Fresh-Eyes-Review nötig,
  da sich am gerenderten Erscheinungsbild nichts ändert).
- Scope: 5 Dateien (3 Test-Dateien + 1 Komponente + evtl. Sub-Komponenten-Referenz), grenzwertig
  zum Standard-Limit — im Blick behalten.
