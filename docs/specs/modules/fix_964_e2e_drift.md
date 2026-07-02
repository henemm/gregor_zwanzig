---
entity_id: fix_964_e2e_drift
type: module
created: 2026-07-02
updated: 2026-07-02
status: draft
version: "1.0"
tags: [e2e, test-drift, trip-new, weather-metrics-tab]
---

# E2E-Test-Drift-Fix (#964)

## Approval

- [ ] Approved

## Purpose

18 E2E-Tests in drei Dateien schlagen fehl. Zwei unabhängige Ursachen: (A) 13 Tests in
`epic-138-metriken-editor.spec.ts` und `issue-343-horizon-chips.spec.ts` erwarten Test-IDs
und eine Komponentenstruktur aus dem Vor-v2-Layout der Wetter-Metriken-Tab, die durch
Issue #587/#848 vollständig ersetzt wurde (kein Produktbug — reine Testkorrektur). (B) 3 Tests
in `issue-661-trip-new-mobile.spec.ts` decken einen echten Produktbug auf: zwei DOM-Elemente
mit identischem `data-testid="trip-new-name-input"` (Desktop + Mobile, nur per CSS
`display:none/block` geschaltet, nicht per Svelte `{#if}`), was `getByTestId(...)` im
Playwright Strict Mode mit "resolved to 2 elements" scheitern lässt.

## Source

- **Fund A (Test-Migration):** `frontend/e2e/epic-138-metriken-editor.spec.ts`,
  `frontend/e2e/issue-343-horizon-chips.spec.ts`
- **Fund B (Produktbug):** `frontend/src/lib/components/trip-new/TripNewEditor.svelte:512-517`
  (Desktop-Input), `:793-800` (Mobile-Input) — beide mit `data-testid="trip-new-name-input"`
- **Fund B (Test-Fix):** `frontend/e2e/issue-661-trip-new-mobile.spec.ts:34` (`fillRoute()`)

## Estimated Scope

- **LoC:** ~150-200 (überwiegend Testcode; Produktcode-Änderung nur 2 Zeilen Test-ID-Rename)
- **Files:** 4 (3 E2E-Spec-Dateien + 1 Svelte-Komponente)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherV2PresetBar.svelte` | Referenz (read-only) | Aktuelle Preset-Pill-Test-IDs |
| `WeatherV2Grundauswahl.svelte` | Referenz (read-only) | Aktuelle Grundauswahl-Sektion + Toggle-Buttons |
| `WeatherV2Reihenfolge.svelte` | Referenz (read-only) | Aktuelle Reihenfolge/Format-Zeilen |
| `MetricCheckbox.svelte` | Referenz (read-only) | Aktuelle Horizon-Chip-Test-IDs |
| `TablePreview.svelte` | Referenz (read-only) | Tages-Vorschau-Test-IDs (unverändert gültig) |
| `Segmented.svelte` (atom) | Referenz (read-only) | Roh/Einfach-Umschalter, kein eigenes Test-ID |

## Implementation Details

### Fund A — Konkrete Test-ID-Migrationstabelle (verifiziert per Grep gegen aktuellen Code)

Die alten Test-IDs `bucket-section-primary`/`-secondary`, `weather-metrics-preset-list`,
`weather-metrics-preset-row-{id}`, `active-metric-row-{id}`, `metric-mode-raw-{id}`,
`metric-mode-scale-{id}`, `bucket-off-toggle`, `off-add-column-{id}` existieren **nicht mehr**
im DOM — die dazugehörige Komponente `BucketSection.svelte`/`BucketSectionOff.svelte`/
`PresetRow.svelte` wird von `WeatherMetricsTab.svelte` seit Issue #587 nicht mehr importiert
(Dead Code, nur noch von eigenen `*.test.ts`-Unit-Tests referenziert — nicht Teil dieses Fixes).
Die aktuelle Struktur:

| Alt (Test erwartet, existiert nicht mehr) | Neu (tatsächlich im DOM) | Quelle |
|---|---|---|
| `bucket-section-primary` / Bucket-Editor mit primary/secondary/off | `wm2-grundauswahl` (eine Sektion "02 — Grundauswahl", secondary ist seit #587 immer leer) | `WeatherV2Grundauswahl.svelte:25` |
| `weather-metrics-preset-list` + `weather-metrics-preset-row-{id}` | `weather-preset-pill-{id}` (User-Presets UND Templates in derselben Pill-Reihe) | `WeatherV2PresetBar.svelte:35,49` |
| Metrik aktivieren via Bucket-Drag/-Button | Toggle-Button in `wm2-grundauswahl` — **kein eigenes `data-testid` pro Metrik**, Button-Text/`title` = `m.label` (Klartext-Bezeichnung aus Katalog) | `WeatherV2Grundauswahl.svelte:40-50` |
| `active-metric-row-{id}`, `metric-mode-raw-{id}`/`metric-mode-scale-{id}` | `wm2-reihenfolge-row` (Test-ID ist NICHT pro Metrik eindeutig — Disambiguierung über zusätzliches Attribut `data-metric-id="{id}"`); Roh/Einfach-Umschalter ist das `Segmented`-Atom, das **kein eigenes `data-testid`** setzt — Ansteuerung über sichtbaren Text "Roh"/"Einfach" gescoped auf `[data-testid="wm2-reihenfolge-row"][data-metric-id="..."]` | `WeatherV2Reihenfolge.svelte:32,56,90-96` |
| `bucket-off-toggle`, `off-add-column-{id}` | entfällt ersatzlos — Off→Primary-Übergang läuft über denselben Grundauswahl-Toggle-Button (kein separater "Aus"-Bereich mehr in der aktuellen UI) | `WeatherV2Grundauswahl.svelte` |
| `horizon-chip-{id}` (global, ein Chip pro Metrik) | `horizon-chip-{metric.id}-today` / `-tomorrow` / `-day_after` (drei Chips pro Metrik) | `MetricCheckbox.svelte:120,126,132` |
| `table-preview-day-{day}` | **unverändert gültig**, keine Migration nötig | `TablePreview.svelte:84` |
| `weather-metrics-tab`, `weather-metrics-tab-save`, `weather-metrics-dirty-pill`, `weather-metrics-tab-success`, `weather-metrics-tab-checkbox-{id}`, `preset-confirm-ok`/`-cancel` | **unverändert gültig**, keine Migration nötig | `WeatherMetricsTab.svelte:469,473,477,483`, `MetricCheckbox.svelte:64` |

Save-Payload (`PUT /api/trips/{id}/weather-config`) hat weiterhin ein `bucket`-Feld pro Metrik
(`buildWeatherPayload()` in `WeatherMetricsTab.svelte:374`) — Tests, die den PUT-Body auf
`bucket`/`order`-Felder prüfen (ehem. AC-6), bleiben inhaltlich gültig, nur der UI-Interaktionspfad
zum Dirty-Machen ändert sich (Grundauswahl-Toggle statt Off-Bucket-Button).

Betroffene ehemalige AC-Blöcke in `epic-138-metriken-editor.spec.ts`: AC-2 bis AC-7, AC-10
(AC-1, AC-8/AC-9 bereits grün bzw. bewusst `.skip` — unverändert lassen). In
`issue-343-horizon-chips.spec.ts`: alle Tests, die `horizon-chip-*` ohne Suffix
(`-today`/`-tomorrow`/`-day_after`) referenzieren.

### Fund B — Test-ID-Split in TripNewEditor.svelte

- Desktop-Input (Zeile ~512-517): `data-testid="trip-new-name-input"` → `data-testid="trip-new-name-input-desktop"`
- Mobile-Input (Zeile ~793-800): `data-testid="trip-new-name-input"` → `data-testid="trip-new-name-input-mobile"`
- `issue-661-trip-new-mobile.spec.ts:34` (`fillRoute()`) und Zeile 71 (`toBeVisible()`-Check)
  auf `trip-new-name-input-mobile` umstellen (dieser Testfile läuft ausschließlich im
  Mobile-Viewport, siehe `MOBILE`-Konstante Zeile 30).
- Reiner Rename, keine Verhaltens-/Layoutänderung — CSS-Gating (`@media (max-width: 899px)`,
  Zeile ~1039-1061) bleibt unverändert.

## Expected Behavior

- **Input:** Playwright-Testläufe (`npx playwright test`) gegen Staging für die drei
  betroffenen Spec-Dateien.
- **Output:** Alle vormals 18 roten Tests werden grün; kein anderer bestehender E2E-Test wird
  rot (insbesondere keine Kollateralschäden an Tests, die dieselben Komponenten anfassen, z.B.
  `issue-848-drag-drop-reorder.spec.ts` falls vorhanden — vor Abschluss per Grep auf
  `wm2-reihenfolge-row`/`trip-new-name-input` prüfen).
- **Side effects:** Keine Änderung am sichtbaren Erscheinungsbild (Fund B ist ein reiner
  Attribut-Rename, kein visuelles Delta — kein Fresh-Eyes-Review erforderlich).

## Acceptance Criteria

- **AC-1:** Given die 13 Tests in `epic-138-metriken-editor.spec.ts` und
  `issue-343-horizon-chips.spec.ts` erwarten veraltete Test-IDs der Vor-v2-Struktur / When die
  Tests auf die aktuelle v2-Komponentenstruktur migriert werden (Grundauswahl-Toggle per
  Klartext-Label, `wm2-reihenfolge-row[data-metric-id]`-Scoping, `horizon-chip-{id}-{horizon}`)
  / Then jeder migrierte Test führt einen echten Klick-Pfad gegen die reale UI aus (kein
  goto+DB-Zustandscheck) und ist grün gegen Staging.
  - Test: `npx playwright test epic-138-metriken-editor.spec.ts issue-343-horizon-chips.spec.ts`
    gegen Staging, alle Tests PASS.

- **AC-2:** Given `TripNewEditor.svelte` rendert zwei Inputs mit identischem
  `data-testid="trip-new-name-input"` (Desktop Zeile ~512-517, Mobile Zeile ~793-800), was
  `page.getByTestId(...)` im Playwright Strict Mode auf 2 Elemente auflöst / When die Test-IDs
  auf `trip-new-name-input-desktop` und `trip-new-name-input-mobile` aufgespalten und
  `issue-661-trip-new-mobile.spec.ts` entsprechend angepasst wird / Then löst
  `getByTestId('trip-new-name-input-mobile')` im Mobile-Viewport (375×667) auf genau EIN
  Element auf (`.count() === 1`), ebenso `getByTestId('trip-new-name-input-desktop')` im
  Desktop-Viewport (1280×900).
  - Test: `npx playwright test issue-661-trip-new-mobile.spec.ts` gegen Staging, alle 3 vormals
    roten Tests PASS; zusätzlich expliziter Zähler-Check
    `await expect(page.getByTestId('trip-new-name-input-mobile')).toHaveCount(1)`.

- **AC-3:** Given 18 E2E-Tests waren vor diesem Fix rot / When beide Funde (Test-Migration in
  Fund A + Test-ID-Split in Fund B) vollständig behoben sind / Then
  läuft die volle Suite der drei betroffenen Spec-Dateien grün UND kein anderer bestehender
  E2E-Test (der dieselben Komponenten berührt, z.B. Drag&Drop-/Preset-Tests) wird durch die
  Änderung rot.
  - Test: `npx playwright test` (voller Lauf oder mindestens alle Specs, die
    `WeatherMetricsTab`, `WeatherV2*`, oder `TripNewEditor` anfassen) gegen Staging, 0 neue
    Fehlschläge gegenüber dem Stand vor diesem Fix.

## Known Limitations

- Die Grundauswahl-Toggle-Buttons und der Roh/Einfach-Umschalter (`Segmented`-Atom) haben aktuell
  **kein** eigenes `data-testid` pro Metrik. Die migrierten Tests müssen daher über sichtbaren
  Text (`m.label`) bzw. das Attribut `data-metric-id` selektieren, gescoped auf die jeweilige
  Elternsektion (`wm2-grundauswahl` bzw. `wm2-reihenfolge`). Das ist bewusst **kein**
  Produktcode-Fix in diesem Ticket (`WeatherV2Grundauswahl.svelte`/`WeatherV2Reihenfolge.svelte`/
  `Segmented.svelte` bleiben unverändert) — falls sich das als zu fragil erweist, ist ein
  Folge-Issue für zusätzliche Test-IDs zu erwägen.
- `BucketSection.svelte`, `BucketSectionOff.svelte`, `PresetRow.svelte` sind Dead Code
  (nicht mehr von `WeatherMetricsTab.svelte` importiert) — sie werden in diesem Fix nicht
  angefasst oder gelöscht, da das außerhalb des Scopes liegt (separates Aufräum-Issue).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testkorrektur (Fund A) und ein Test-ID-Rename ohne Verhaltensänderung
  (Fund B) — keine Architekturentscheidung.

## Changelog

- 2026-07-02: Initial spec created
