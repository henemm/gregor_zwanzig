---
entity_id: fix_970_971_1011_e2e_ui_drift
type: module
created: 2026-07-06
updated: 2026-07-06
status: draft
version: "1.0"
tags: [e2e, test-drift, weather-metrics-tab, mail-simplification, dead-code]
---

<!-- Bündel I — Issues #970, #971, #1011 -->

# E2E-/Unit-Test-Drift nach v2-Redesign und Mail-Vereinfachung bereinigen (#970, #971, #1011)

## Approval

- [x] Approved (2026-07-06)

## Purpose

Nach dem v2-Redesign der Wetter-Metriken-Ansicht (#848, #587) UND einer unabhängigen
Mail-Vereinfachung (#790, #942) erwarten mehrere Frontend-E2E-Tests und eine
Unit-Test-Datei Test-IDs bzw. Interaktionspfade, die im aktuellen DOM nicht mehr
existieren. Diese Spec bereinigt das Bündel I (#970, #971, #1011): tote Tests werden
zurückgezogen (PO-Entscheidung, keine Feature-Wiederherstellung), lebende Tests werden
auf reale Selektoren migriert, und eine bereits durch Vorcommit behobene Unit-Test-Datei
wird verifiziert statt erneut gefixt.

## Source

- **Fund #970 (Horizon-Chips):** `frontend/e2e/issue-343-horizon-chips.spec.ts:104,108,113,117,120`
  (5 `test.skip()`-Blöcke: AC-1/2/3/5/6) und `:125,166` (2 aktive Tests: AC-7, AC-4)
- **Fund #971 — Doppelzählung mit #970:** `frontend/e2e/issue-690-custom-metrics-persist.spec.ts:71-74`
  (`makeDirty()`-Helper, toter Selektor `weather-metrics-tab-checkbox-*`)
- **Fund #971 — epic-138-block-b:** `frontend/e2e/epic-138-block-b.spec.ts:60-118` (#178
  dirty-State, Zeilen 79/94 toter Selektor), `:119-166` (#174 MetricGroup, tot), `:167-200`
  (#175 ModeBtn/INDICATOR_MAP, tot), `:201-256` (#176 TablePreview, tot), `:257-345` (#177
  SavePresetDialog, Zeilen 297/307/318 `save-preset-dialog-trigger` tot, Zeile 328
  `weather-metrics-preset-row-*` tot)
- **Fund #971 — Metriken-Überblick-Checkbox:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte:466-475`
  (die tatsächliche Checkbox-Markup, `data-testid="report-show-metrics-summary"`),
  konsumiert ohne `showMailContent={false}` u.a. in
  `frontend/src/lib/components/trip-new/TripNewEditor.svelte:765` (Desktop-Zeitplan-Tab)
  und `:990` (Mobile-Zeitplan-Tab) — dort sichtbar im Neuanlegen-Formular als wirkungslose
  Karteileiche. Zugehörige Tests: `frontend/e2e/issue-774-metrics-summary-persist.spec.ts:73-166`
  (3 Tests), `frontend/e2e/issue-776-metrics-toggle.spec.ts:20-79` (1 Test, klickt den
  bereits entfernten `report-content-modules-toggle`, Zeile 43)
- **Fund #1011 (nur Verifikation, kein Code-Fix):** `frontend/src/lib/utils/alertMetricLabels.test.ts`,
  `frontend/src/lib/utils/alertMetricLabels.ts:67-70` — bereits durch Commit `b65f22a0`
  (2026-07-03) behoben, 15/15 grün

## Estimated Scope

- **LoC:** ~80-130 (überwiegend Löschungen/Selektor-Austausch; einzige Produktivcode-
  Änderung ist die Checkbox-Entfernung in `EditReportConfigSection.svelte`, ~10 Zeilen)
- **Files:** 6 (5 E2E-/Unit-Test-Dateien + 1 Svelte-Komponente:
  `EditReportConfigSection.svelte`, das die eigentliche Karteileiche trägt, die in
  `TripNewEditor.svelte:765,990` sichtbar wird)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherV2Grundauswahl.svelte:25` | Referenz (read-only) | Aktueller Klickpfad für `makeDirty()`-Ersatz (`wm2-grundauswahl`) |
| `WeatherV2Reihenfolge.svelte:32,45,56,90-96` | Referenz (read-only) | Aktuelle Reihenfolge-Test-IDs (unverändert gültig, nicht Teil dieses Fixes) |
| `WeatherV2PresetBar.svelte:35,38,49,58` | Referenz (read-only) | Aktueller Preset-Pill-Selektor `weather-preset-pill-{id}` und Text-Trigger "als eigenes Profil speichern" für die #177-Migration |
| `build_metrics_summary_pills()` (`src/output/renderers/email/html.py:1287`) | Referenz (read-only) | Beweis, dass der Metriken-Überblick-Block seit #790 unconditional gerendert wird — Grundlage für AC-4 |
| `docs/specs/modules/fix_964_e2e_drift.md` | Vorgänger-Spec | Migrations-Methodik (Skip-Kommentar-Vorbild), aber dessen Tabellenzeilen zu `table-preview-day-*`/`weather-metrics-tab-checkbox-*` sind **veraltet** — durch diesen Fix implizit korrigiert |

## Implementation Details

### 1. `issue-690-custom-metrics-persist.spec.ts` + `epic-138-block-b.spec.ts` #178 (kleinster, risikoärmster Schritt)

`makeDirty()` (issue-690, Zeile 71-74) sowie die beiden `firstCheckbox`-Vorkommen in
`epic-138-block-b.spec.ts` (#178-Gruppe, Zeilen 79 und 94) ersetzen den toten Selektor
`[data-testid^="weather-metrics-tab-checkbox-"]` durch einen echten Klick gegen die
Grundauswahl-Sektion (`wm2-grundauswahl`), analog zum Vorbild in
`issue-343-horizon-chips.spec.ts:148-151`:

```ts
async function makeDirty(page: Page) {
	const toggle = page.locator('[data-testid="wm2-grundauswahl"] button').first();
	await toggle.click();
	await expect(page.locator('[data-testid="weather-metrics-dirty-pill"]')).toBeVisible();
}
```

`openSaveDialog()` (Zeile 78-80, Text-Selektor "als eigenes Profil speichern") ist
bereits korrekt und bleibt unverändert.

### 2. `epic-138-block-b.spec.ts` — Dead-Code-Gruppen zurückziehen, #177 migrieren

- Gruppen `#174 MetricGroup` (Zeilen 119-166) und `#175 ModeBtn/INDICATOR_MAP` (Zeilen
  167-200) werden entfernt (PO-Entscheidung: totes v2-Redesign-Dead-Code, analog zu
  #970, keine Wiederherstellung).
- Gruppe `#176 TablePreview` (Zeilen 201-256) wird entfernt (überschneidet sich mit dem
  #970-Fund, gleiche PO-Entscheidung).
- Gruppe `#177 SavePresetDialog` (Zeilen 257-345) wird migriert:
  `save-preset-dialog-trigger` (Zeilen 297, 307, 318) → Text-/Rollen-Selektor
  `page.getByRole('button', { name: 'als eigenes Profil speichern' })`;
  `weather-metrics-preset-row-{id}` (Zeile 328) → `weather-preset-pill-{id}`.
  Die API-only-Subtests `AC-6a` (Zeile 287) und `AC-7` (Zeile 337) sind bereits grün
  (kein Frontend-Selektor betroffen) — **nicht unnötig anfassen**.

### 3. `issue-343-horizon-chips.spec.ts` — Skip-Bereinigung (#970)

Die 5 bereits `test.skip()`-ten Tests (Zeilen 104, 108, 113, 117, 120 — AC-1/2/3/5/6)
werden vollständig entfernt (nicht nur weiter geskippt). Die 2 aktiven Tests (Zeile 125
AC-7, Zeile 166 AC-4) bleiben unverändert.

### 4. Metriken-Überblick-Checkbox entfernen (#774/#776) — einzige Produktivcode-Änderung

Die Checkbox-Markup (`EditReportConfigSection.svelte:466-475`, Testid
`report-show-metrics-summary`) wird entfernt. Das ist die **einzige** Stelle im Code,
an der die Karteileiche existiert — sie wird über die Komponente an allen
Aufrufstellen konsumiert, u.a. `TripNewEditor.svelte:765` (Desktop) und `:990`
(Mobile), wo sie mangels `showMailContent={false}` sichtbar im
Neuanlegen-Formular auftaucht (im Bearbeiten-Modus via `BriefingScheduleTab.svelte:105`
bereits durch `showMailContent={false}` ausgeblendet). Die Entfernung an der einen
Quelle bereinigt damit konsistent alle Aufrufstellen (Single Source, keine
Duplikat-Fixes pro Konsument nötig).

Test-Anpassungen:
- `issue-774-metrics-summary-persist.spec.ts`: AC-1 (Persistenz-Test der Checkbox)
  entfällt ersatzlos — es gibt keine Checkbox mehr, die einen Wert persistieren könnte.
  AC-2 (kein Einklapp-Element, Checkboxen direkt sichtbar) bleibt sinngemäß gültig für
  die verbleibenden 3 Checkboxen (`show_outlook`, `show_stage_stats`,
  `show_yesterday_comparison`). AC-3 (Wetter-Metriken bleiben nach Save unverändert)
  wird auf einen der verbleibenden Checkboxen umgestellt.
- `issue-776-metrics-toggle.spec.ts`: Der einzige Test klickt bereits einen nicht mehr
  existierenden `report-content-modules-toggle` (Zeile 43) — wird ersetzt durch eine
  Prüfung, dass der Metriken-Überblick-Block in der versendeten Mail **immer** erscheint
  (kein Toggle-Verhalten mehr zu testen).

### 5. `#1011` — Verifikation statt Fix

`npm run test -- src/lib/utils/alertMetricLabels.test.ts` wird real ausgeführt; der
Output (15/15 grün) wird als Artefakt für den Issue-Schluss dokumentiert. Kein Edit an
`alertMetricLabels.ts` oder `.test.ts`.

## Expected Behavior

- **Input:** `npx playwright test` gegen Staging für die 4 betroffenen E2E-Spec-Dateien;
  `npm run test -- src/lib/utils/alertMetricLabels.test.ts` für #1011.
- **Output:** Alle vormals roten Tests aus #970/#971 sind entweder grün (migrierte
  Selektoren) oder entfernt (PO-Entscheidung: kein Feature-Ersatz für Dead Code); die 2
  weiterhin aktiven `issue-343`-Tests bleiben grün; `alertMetricLabels.test.ts` bestätigt
  15/15 grün ohne Code-Änderung.
- **Side effects:** Die Metriken-Überblick-Checkbox verschwindet nicht nur im
  Neuanlegen-Formular, sondern auch aus `TripEditView.svelte:203` und
  `BriefingsTab.svelte:40` (beide konsumieren dieselbe Komponente ohne
  `showMailContent={false}`) — beabsichtigter Nebeneffekt der Single-Source-Entfernung,
  konsistent mit der PO-Entscheidung "Checkbox überall entfernen".

## Acceptance Criteria

- **AC-1:** Given `issue-343-horizon-chips.spec.ts` enthält 5 bereits `test.skip()`-te
  Tests (AC-1/2/3/5/6, Zeilen 104/108/113/117/120) für eine PO-seitig endgültig nicht
  wiederherzustellende Horizon-Chip-UI / When die 5 Skip-Blöcke vollständig aus der
  Datei entfernt werden / Then bleiben nur die 2 aktiven Tests (AC-4, AC-7) übrig und
  laufen weiterhin unverändert grün gegen Staging.
  - Test: `npx playwright test issue-343-horizon-chips.spec.ts` gegen Staging, 2 PASS,
    0 SKIP, 0 FAIL; Diff der Datei zeigt ausschließlich Löschungen der 5 Skip-Blöcke.

- **AC-2:** Given `issue-690-custom-metrics-persist.spec.ts` (`makeDirty()`,
  Zeile 71-74) und `epic-138-block-b.spec.ts` Gruppe #178 (Zeilen 79, 94) nutzen den
  toten Selektor `weather-metrics-tab-checkbox-*` / When `makeDirty()` bzw. der
  gleichwertige Helper stattdessen einen echten Klick gegen `wm2-grundauswahl` ausführt
  / Then laufen alle betroffenen Tests durch einen echten Playwright-Lauf gegen
  Staging durch, ohne dass der tote Selektor auftaucht — kein Mock, echter Klickpfad.
  - Test: `npx playwright test issue-690-custom-metrics-persist.spec.ts
    epic-138-block-b.spec.ts` gegen Staging, alle 4 (issue-690) + 2 (#178) Tests PASS.

- **AC-3:** Given `epic-138-block-b.spec.ts` enthält die Dead-Code-Gruppen #174
  (MetricGroup, Zeilen 119-166), #175 (ModeBtn/INDICATOR_MAP, Zeilen 167-200) und #176
  (TablePreview, Zeilen 201-256) sowie die Gruppe #177 (SavePresetDialog, Zeilen
  257-345) mit toten Selektoren `save-preset-dialog-trigger` und
  `weather-metrics-preset-row-*` / When #174/#175/#176 vollständig entfernt werden (PO-
  Entscheidung: Dead Code, keine Wiederherstellung) und #177 auf
  `getByRole('button', { name: 'als eigenes Profil speichern' })` sowie
  `weather-preset-pill-{id}` migriert wird / Then läuft die verbleibende #177-Gruppe
  grün gegen Staging, und #174/#175/#176 existieren nicht mehr in der Datei.
  - Test: `npx playwright test epic-138-block-b.spec.ts` gegen Staging — nur noch #177-
    und #178-Tests vorhanden, alle PASS; `grep -c "MetricGroup\|ModeBtn\|TablePreview"
    epic-138-block-b.spec.ts` liefert 0 Treffer für die entfernten `test.describe`-Blöcke.

- **AC-4:** Given die "Metriken-Überblick"-Checkbox (`EditReportConfigSection.svelte:466-475`)
  ist seit Issue #790 im Mail-Renderer wirkungslos (der Block wird in
  `build_metrics_summary_pills()` immer unconditional gerendert) und erscheint dennoch
  im Neuanlegen-Formular (`TripNewEditor.svelte:765` Desktop, `:990` Mobile) als
  Karteileiche / When die Checkbox aus `EditReportConfigSection.svelte` entfernt wird
  und `issue-774-metrics-summary-persist.spec.ts` sowie
  `issue-776-metrics-toggle.spec.ts` auf das tatsächliche Verhalten ("Block erscheint
  immer, keine Checkbox-Interaktion nötig") umgestellt werden / Then zeigt das
  Neuanlegen-Formular keine "Metriken-Überblick"-Checkbox mehr, und beide Testdateien
  laufen grün gegen Staging.
  - Test: `npx playwright test issue-774-metrics-summary-persist.spec.ts
    issue-776-metrics-toggle.spec.ts` gegen Staging, alle Tests PASS; manueller
    Playwright-Check `await expect(page.getByTestId('report-show-metrics-summary')).toHaveCount(0)`
    im Neuanlegen-Formular (`/trips/new`).

- **AC-5:** Given #1011 meldet Drift in `frontend/src/lib/utils/alertMetricLabels.test.ts`,
  aber Commit `b65f22a0` (2026-07-03) hat die Ursache bereits vor der Meldung behoben /
  When `npm run test -- src/lib/utils/alertMetricLabels.test.ts` real ausgeführt wird /
  Then bestätigt der Lauf 15/15 grün, 0 Fails, ohne dass Code oder Testdatei verändert
  werden — der Testlauf-Output dient als Verifikationsnachweis für den Issue-Schluss.
  - Test: `npm run test -- src/lib/utils/alertMetricLabels.test.ts`, Output als Artefakt
    gespeichert, 15/15 PASS.

## Known Limitations

- Die bestätigt toten Dateien `MetricCheckbox.svelte`, `TablePreview.svelte`,
  `MetricGroup.svelte`, `BucketSection.svelte`, `BucketSectionOff.svelte`,
  `PresetRow.svelte` werden **nicht** gelöscht — nur die Tests dazu werden
  zurückgezogen. Eine Löschung wäre ein separater Cleanup, nicht Teil dieser Spec
  (Scope-Disziplin, siehe Kontext-Dokument).
- Das Backend-Feld `show_metrics_summary` (Model, Loader,
  `frontend/src/lib/components/edit/reportConfigWrite.ts:54,79,120,136`) bleibt
  bestehen (totes Feld, kein funktionaler Schaden) — wird nicht entfernt.
- Die API-only-Subtests `AC-6a` und `AC-7` der Gruppe #177 in `epic-138-block-b.spec.ts`
  (Zeilen 287, 337) waren laut Analyse vermutlich bereits grün (kein Frontend-Selektor
  betroffen) — sie werden bei der Umsetzung nicht unnötig angefasst.
- Die Entfernung der Metriken-Überblick-Checkbox in `EditReportConfigSection.svelte`
  wirkt sich als Nebeneffekt auch auf `TripEditView.svelte:203` und
  `BriefingsTab.svelte:40` aus (beide rendern dieselbe Komponente ohne
  `showMailContent={false}`) — das ist beabsichtigt (PO-Entscheidung "überall
  entfernen"), wird aber nicht durch eigene E2E-Tests in dieser Spec abgedeckt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Migration/-Rückzug (4 von 6 Dateien) plus eine kleine,
  durch Renderer-Code zweifelsfrei belegte Dead-Code-Entfernung (Checkbox ohne
  funktionale Wirkung seit #790) — keine Architektur- oder Verhaltensentscheidung, die
  über eine bereits getroffene PO-Entscheidung hinausgeht. Gegen `adr_guard.py`
  geprüft: Testdateien und die einzeilige Checkbox-Entfernung treffen keine der
  konfigurierten Decision-Surface-Muster (analog zum Vorgehen bei Bündel H).

## Changelog

- 2026-07-06: Initial spec created — Bündel I, Issues #970, #971, #1011
