# Context: f2b-1301-editor-loeschung

**Epic:** #1301 Scheibe F2b (= #1273 S5) · **Vorgänger:** F2a live (`37381f47` + `c5503e3a`)

## Request Summary

Der Alt-Anlege-/Bearbeiten-Editor `CompareEditor.svelte` fällt ersatzlos, nachdem
F2a (`CompareNewEditor` nach Trip-Muster #622) live ist und der Hub `/compare/[id]`
seit S3 die einzige Bearbeiten-Fläche ist. Reine Tote-Code-Löschung plus
Wächter-Anpassung — kein Verhaltenswandel für Nutzer.

## Kernbefunde (Recherche 2026-07-19)

1. **`CompareEditor.svelte` (1.686 Z.) wird nirgends mehr gemountet.**
   `/compare/[id]/edit` ist seit S3 ein reiner 307-Redirect auf den Hub
   (`routes/compare/[id]/edit/+page.server.ts`), `/compare/new` mountet seit F2a
   `CompareNewEditor`. Kein Test importiert die Komponente (nur Kommentar-Erwähnungen);
   kein Test liest sie per `readFileSync`.
2. **Einziger echter Import:** `__tests__/issue_683_wizard_remove.test.ts` — ein
   Wächter-Test, dessen AC-5 noch das ÜBERHOLTE Zielbild prüft
   („compare/new importiert CompareEditor", Regex `/CompareEditor/` matcht heute
   zufällig `CompareNewEditor` als Substring → grün aus falschem Grund).
3. **Lock-Engine ist dupliziert:** `compareNewLogic.ts` (F2a) ersetzt
   `compareEditorLogic.ts` vollständig (7 Stationen inkl. `metriken`/`alarme`
   statt 5+alarme; `idealsValid`-Mechanik per F2a-Spec abgelöst).

## Lösch-Kandidaten (nur vom Alt-Editor genutzt)

| Datei | LoC | Nachweis |
|---|---|---|
| `lib/components/compare/CompareEditor.svelte` | 1.686 | kein Mount, kein Test-Import |
| `lib/components/compare/compareEditorLogic.ts` | 51 | Importeure: nur CompareEditor + 3 Tests |
| `lib/components/compare/compareAutosave.ts` | 25 | Importeur: nur CompareEditor |
| `compareEditorLogic.test.ts`, `issue_718_idealwert_validation.test.ts`, `__tests__/compare_wizard_alarme_station.test.ts` | ~ | testen die alte Lock-Engine (durch `compareNewLogic` + dessen Tests abgelöst) |
| `__tests__/compareAutosaveGate.test.ts` | ~ | testet Alt-Editor-Autosave |

Weitere Alt-Editor-Tests prüfen `compareEditorSave`-Verhalten (bleibt) — Einzelfall-
Triage in der Spec: `compareEditorHourlyToggle/ForecastHours/HourlyMetrics/Slice3/TopN`-Tests.

## Bleibt stehen (vom Hub / CompareNewEditor genutzt)

| Datei | Genutzt von |
|---|---|
| `compareEditorSave.ts` (175 Z.) | `compareWizardState.svelte.ts`, `compareHubWizardBridge.ts` (Hub-Save-Pfad) |
| `compareEditorLoad.ts` (33 Z.) | Hub-Bridge, `weatherMetricsCompareSave.ts` |
| `compareWizardState.svelte.ts` (205 Z.) | Hub, `/compare/new`, geteilte Tabs (WeatherMetrics/Alarme/Versand/Corridor) |
| `compareHubWizardBridge.ts` | Hub `/compare/[id]` |
| `steps/Step2Orte.svelte` (424 Z.) | `CompareNewEditor` — **PO-Vorgabe: NICHT löschen** |

## Entscheidungspunkt für die Spec

- **Edit-Redirect-Route:** Epic-Text sagt „Route löschen", aber das Trip-Pendant
  `routes/trips/[id]/edit/` (#616) behält seinen 307-Redirect. Teilungs-Invariante
  (PO mehrfach bekräftigt) ⇒ Empfehlung: **Redirect bleibt**, nur die tote
  Komponente + Editor-only-Helfer fallen. `e2e/compare-edit-redirect.spec.ts`
  bleibt dann gültig.

## Dependencies

- Upstream (was der Lösch-Kandidat nutzt): Step2Orte, geteilte Tab-Organismen,
  compareEditorSave/Load, compareWizardState — alles bleibt, nur der Aufrufer fällt.
- Downstream (wer den Lösch-Kandidaten nutzt): niemand (produktiv 0 Importe).

## Nacharbeiten im selben Schnitt

- `issue_683_wizard_remove.test.ts` AC-5 auf `CompareNewEditor` präzisieren
  (Substring-Falle `/CompareEditor/` schließen); Checks „keine Produktionsdatei
  importiert CompareEditor.svelte" ergänzen (Muster des Tests selbst).
- Veraltete Kommentar-Verweise auf CompareEditor in geteilten Dateien
  (`CorridorEditor.svelte:102`, `weatherMetricsTabSections.ts:12`,
  `subscriptionHelpers.ts:310`, `saveStatus.test.ts:8`, …) — nur wo irreführend.
- E2E-Specs sichten: `compare-editor-autosave.spec.ts`,
  `compare-editor-fidelity-s8d.spec.ts` — laufen die gegen den Hub (behalten)
  oder die alte Editor-UI (löschen)?
- F3 (#1206, #989 auf Erledigung prüfen) ist NICHT Teil dieser Scheibe.

## Existing Specs

- `docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md` — F2a (Vorgänger)
- `docs/specs/modules/feat_1273_s3_redirect.md` — Edit-Route-Redirect (AC-1)
- `docs/specs/modules/issue_678_compare_editor_shell.md` — Alt-Editor (wird obsolet)

## Analysis (Phase 2, 2026-07-19)

### Type
Feature (Rückbau-Scheibe, kein Bug).

### Affected Files (with changes)
| File | Change | Begründung |
|---|---|---|
| `lib/components/compare/CompareEditor.svelte` | DELETE (−1.686) | toter Code, kein Mount, kein Import |
| `lib/components/compare/compareEditorLogic.ts` | DELETE (−51) | nur vom Alt-Editor importiert; `compareNewLogic.ts` ersetzt |
| `lib/components/compare/compareAutosave.ts` | DELETE (−25) | nur vom Alt-Editor importiert; Hub hat eigenen SaveController |
| `compareEditorLogic.test.ts` | DELETE (−121) | testet gelöschte Lock-Engine |
| `__tests__/compare_wizard_alarme_station.test.ts` | DELETE (−86) | testet gelöschte Lock-Engine (Alarme-Station lebt in `compareNewLogic`-Tests weiter) |
| `__tests__/compareAutosaveGate.test.ts` | DELETE (−68) | testet gelöschtes Autosave-Gate |
| `issue_718_idealwert_validation.test.ts` | UPDATE | `doneTabs`-Import + 2 Blöcke raus; `validateIdealRanges`-Blöcke (compareMetricDefs, bleibt) behalten |
| `__tests__/issue_683_wizard_remove.test.ts` | UPDATE | AC-5 (Z. 237) prüft VERALTET „compare/new importiert CompareEditor" — auf `CompareNewEditor` umstellen (Wortgrenze!); neue Wächter: `CompareEditor.svelte` gelöscht + keine Produktionsdatei importiert sie |
| `routes/compare/[id]/edit/` | KEEP | 307-Redirect bleibt — Trip-Muster #616 (`routes/trips/[id]/edit/` existiert identisch); `e2e/compare-edit-redirect.spec.ts` sichert das ab |

### Test-Triage (Explore-verifiziert, echte Imports)
- **KEEP (prüfen bleibenden Save-/Hub-Pfad):** `compareEditorSave.test`, `compareEditorHourlyToggle/ForecastHours/HourlyMetrics/Slice3`, `compareEditorTopN`, `compare_editor_save_official_warnings`, `compare_save_deprecated_fields_roundtrip`, `compare_versand_slot_payload`, `compare_preset_channels`, `issue_462`, `step2_orte_library_grouping` (liest `CompareTabs.svelte`/`Step2Orte.svelte`, bereits migriert).
- **E2E: alle KEEP.** Kein Playwright-Spec treibt die alte /edit-Editor-UI; `compare-editor-*`-Specs laufen gegen Hub bzw. `/compare/new`. `data-testid="compare-editor-name"` existiert in beiden Editoren → `/compare/new`-Specs bleiben nach Löschung grün.
- Keine vitest/node-test-Config, kein Loader, kein Hook referenziert die Löschmodule; Doku-Erwähnungen sind Prosa (stale, aber bruchfrei).

### Scope Assessment
- Files: 6 DELETE + 2 UPDATE (+ punktuelle Kommentar-Bereinigung nur wo irreführend)
- LoC: ca. −2.040 / +15 → **LoC-Limit-Override nötig (PO fragen, im Epic angekündigt)**
- Risk: LOW — Build bricht nachweislich nicht (0 Produktions-Importe), Brüche nur in den 4 gelisteten Testdateien

### Technical Approach
Ein Schnitt: 6 Dateien löschen, 2 Tests aktualisieren, `issue_683`-Wächter um
Abwesenheits-ACs für `CompareEditor.svelte` erweitern (Muster des Tests selbst,
Wortgrenzen-Regex gegen die `CompareNewEditor`-Substring-Falle). Kein
Verhaltenswandel, keine Persistenz-Berührung, kein Mail-Pfad → kein Renderer-Gate.

### Open Questions
- Redirect-Route behalten (Empfehlung, Trip-Muster) — in Spec als AC festschreiben, PO entscheidet bei Freigabe mit.

## Risks & Considerations

- **LoC-Limit:** ~2.000 Zeilen Delta (fast nur Löschung) — Override nötig,
  laut Epic angekündigt; vor `set-field loc_limit_override` PO fragen.
- **Substring-Fallen:** Wächter-Regexe `/CompareEditor/` matchen `CompareNewEditor`
  — bei neuen Wächtern Wortgrenzen bzw. exakte Pfade verwenden.
- **Vitest/node-test-Sammelläufe:** gelöschte Testdateien dürfen keine Referenzen
  hinterlassen (Loader-Konfigurationen prüfen).
