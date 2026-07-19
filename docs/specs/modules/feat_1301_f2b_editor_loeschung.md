---
entity_id: feat_1301_f2b_editor_loeschung
type: module
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
tags: [frontend, compare, cleanup, dead-code]
---

<!-- Issue #1301 (Scheibe F2b) / #1273 (S5) -->

# Epic #1301 Scheibe F2b — Ersatzlose Löschung des Alt-Editors `CompareEditor.svelte`

## Approval

- [ ] Approved

## Purpose

Nachdem F2a (`CompareNewEditor` nach Trip-Muster #622) live ist und der Hub
`/compare/[id]` seit S3 die einzige Bearbeiten-Fläche für Orts-Vergleiche ist,
wird der tote Alt-Editor `CompareEditor.svelte` samt seiner Editor-only-Helfer
ersatzlos entfernt. Reiner Rückbau — kein Verhaltenswandel für Nutzer.

## Source

- **File:** `frontend/src/lib/components/compare/CompareEditor.svelte` (DELETE, 1.686 Z.)
- **File:** `frontend/src/lib/components/compare/compareEditorLogic.ts` (DELETE, 51 Z.)
- **File:** `frontend/src/lib/components/compare/compareAutosave.ts` (DELETE, 25 Z.)
- **Identifier:** Alt-Editor-Lock-Engine (`compareEditorLogic`), Alt-Editor-Autosave (`compareAutosave`) — beide durch `compareNewLogic.ts` (F2a) bzw. den Hub-eigenen SaveController abgelöst

> **Schicht:** Ausschließlich Frontend / User-UI (`frontend/src/...`, SvelteKit). Keine Berührung von Go-API, Python-Core oder Persistenz.

## Estimated Scope

- **LoC:** ca. −2.040 / +15 (fast nur Löschung) — **LoC-Limit-Override nötig**, im Epic #1301 angekündigt, PO-Freigabe vor `set-field loc_limit_override` einholen
- **Files:** 6 DELETE + 2 UPDATE (plus punktuelle Kommentar-Bereinigung nur wo irreführend)
- **Effort:** low (reine Löschung, 0 Produktions-Importe des Lösch-Kandidaten laut Recherche)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareNewEditor` (F2a, `feat_1301_f2a_compare_new_trip_pattern.md`) | Vorgänger-Spec | Ersetzt den Alt-Editor vollständig für `/compare/new`; Architekturentscheidung „Trip-Muster #622" fiel dort |
| `compareEditorSave.ts` / `compareEditorLoad.ts` | Bestand, bleibt | Wird vom Hub-Save-Pfad (`compareWizardState.svelte.ts`, `compareHubWizardBridge.ts`) weiterverwendet, NICHT Teil dieser Löschung |
| `steps/Step2Orte.svelte` | Bestand, bleibt | PO-Vorgabe: wird von `CompareNewEditor` wiederverwendet, NICHT löschen |
| `routes/compare/[id]/edit/+page.server.ts` | Bestand, bleibt | 307-Redirect auf den Hub, analog Trip-Pendant `routes/trips/[id]/edit/` (#616) |
| `e2e/compare-edit-redirect.spec.ts` | Bestand, bleibt | Sichert den Redirect ab |
| `__tests__/issue_683_wizard_remove.test.ts` | Bestand, UPDATE | Wächter-Test; AC-5 präzisiert, neue Abwesenheits-Checks ergänzt |

## Implementation Details

```
DELETE:
  frontend/src/lib/components/compare/CompareEditor.svelte            (-1.686)
  frontend/src/lib/components/compare/compareEditorLogic.ts           (-51)
  frontend/src/lib/components/compare/compareAutosave.ts              (-25)
  frontend/src/lib/components/compare/compareEditorLogic.test.ts      (-121)
  frontend/src/__tests__/compare_wizard_alarme_station.test.ts        (-86)
  frontend/src/__tests__/compareAutosaveGate.test.ts                  (-68)

UPDATE:
  frontend/src/lib/components/compare/issue_718_idealwert_validation.test.ts
    - doneTabs-Import + zugehörige Blöcke raus
    - validateIdealRanges-Blöcke (compareMetricDefs) bleiben unverändert

  frontend/src/__tests__/issue_683_wizard_remove.test.ts
    - AC-5 (Zeile ~237): veraltete Prüfung "compare/new importiert CompareEditor"
      auf CompareNewEditor umstellen (Wortgrenzen-Regex, schließt die
      Substring-Falle /CompareEditor/ ~ "CompareNewEditor")
    - NEU: Wächter-Check (a) CompareEditor.svelte existiert nicht mehr
    - NEU: Wächter-Check (b) keine Produktionsdatei importiert CompareEditor.svelte
    - NEU: Wächter-Check (c) compareEditorLogic.ts und compareAutosave.ts
      existieren nicht mehr
    - Muster: die bestehenden Abwesenheits-Checks im selben Test übernehmen

KEEP (explizit, unangetastet):
  compareEditorSave.ts, compareEditorLoad.ts, compareWizardState.svelte.ts,
  compareHubWizardBridge.ts, steps/Step2Orte.svelte,
  routes/compare/[id]/edit/ (307-Redirect bleibt), alle 12 verbleibenden
  compareEditorSave-/Hub-Tests, alle Playwright-E2E-Specs
```

## Expected Behavior

- **Input:** Bestehender Frontend-Baum mit totem Alt-Editor (`CompareEditor.svelte`) und den davon abhängigen Editor-only-Helfern
- **Output:** Alt-Editor-Dateien und ihre 4 zugehörigen Testdateien sind entfernt; `/compare/new` mountet weiterhin `CompareNewEditor`; `/compare/[id]/edit` leitet weiterhin per 307 auf den Hub um; Wächter-Test verhindert Wiedereinführung
- **Side effects:** Keine Persistenz-, Mail- oder API-Änderung; kein Renderer-Gate betroffen; Build und Kern-Testsuite bleiben grün

## Acceptance Criteria

- **AC-1:** Given der Alt-Editor-Baum (`CompareEditor.svelte`, `compareEditorLogic.ts`, `compareAutosave.ts`) existiert im Repo / When die Löschung durchgeführt wird / Then existieren diese drei Dateien nicht mehr unter `frontend/src`, und keine Produktionsdatei importiert sie — geprüft durch einen Wortgrenzen-Regex-Wächter in `issue_683_wizard_remove.test.ts`, der `CompareNewEditor` NICHT fälschlich matcht.
  - Test: `find`/`grep`-gestützter Wächter-Test schlägt fehl, solange `CompareEditor.svelte` oder ein Import davon existiert; nach der Löschung grün.

- **AC-2:** Given ein Nutzer ruft `/compare/<id>/edit` für einen bestehenden Orts-Vergleich auf / When die Seite lädt / Then wird per HTTP 307 auf den Hub `/compare/<id>` weitergeleitet, unverändert zum Verhalten vor der Löschung.
  - Test: `e2e/compare-edit-redirect.spec.ts` navigiert real zur Edit-URL und prüft den Redirect-Zielpfad im Browser.

- **AC-3:** Given ein Nutzer ruft `/compare/new` auf, um einen neuen Orts-Vergleich anzulegen / When die Seite mountet / Then wird weiterhin `CompareNewEditor` gerendert (nicht der gelöschte Alt-Editor).
  - Test: Wächter-Test aus AC-1 prüft explizit den Import von `CompareNewEditor` in der `/compare/new`-Route; ergänzend bestehende `/compare/new`-Playwright-Specs bleiben grün.

- **AC-4:** Given `issue_718_idealwert_validation.test.ts` nach dem Update / When der Testlauf ausgeführt wird / Then prüft die Datei weiterhin `validateIdealRanges` (compareMetricDefs) korrekt und enthält keinen Import eines gelöschten Moduls mehr.
  - Test: Testlauf `node --test` auf die Datei; kein Modul-Resolve-Fehler, `validateIdealRanges`-Assertions bleiben grün.

- **AC-5:** Given die 12 verbleibenden Save-/Hub-/Step2Orte-Unit-Tests (u. a. `compareEditorSave.test`, `compareEditorHourlyToggle/ForecastHours/HourlyMetrics/Slice3`, `compareEditorTopN`, `compare_editor_save_official_warnings`, `compare_save_deprecated_fields_roundtrip`, `compare_versand_slot_payload`, `compare_preset_channels`, `issue_462`, `step2_orte_library_grouping`) / When sie nach der Löschung ausgeführt werden / Then laufen alle unverändert grün, und `Step2Orte.svelte` bleibt unangetastet.
  - Test: gezielter Testlauf dieser Suite-Dateien vor und nach der Löschung, Diff der Ergebnisse ist leer.

- **AC-6:** Given der bereinigte Frontend-Baum / When `npm run build` (bzw. `vite build`) sowie der Kern-Testlauf der Frontend-Suite ausgeführt werden / Then schlägt weder Build noch Testlauf fehl (keine hängenden Imports auf gelöschte Module, kein Loader/Vitest-Config-Verweis).
  - Test: CI-äquivalenter lokaler Build- und Testlauf nach der Löschung, Exit-Code 0.

## Known Limitations

- Prosa-Erwähnungen von `CompareEditor` in `docs/` und in Kommentaren (z. B. `CorridorEditor.svelte:102`, `weatherMetricsTabSections.ts:12`, `subscriptionHelpers.ts:310`, `saveStatus.test.ts:8`) bleiben teils stehen (stale, aber bruchfrei) — nur irreführende Kommentare in ohnehin berührten Dateien werden bereinigt.
- Der Epic-Text „Route löschen" wird bewusst als „Redirect bleibt" umgesetzt (Trip-Teilungs-Invariante, `routes/trips/[id]/edit/` #616 ist das Vorbild) — das ist eine bewusste Abweichung vom wörtlichen Epic-Text, PO entscheidet bei Freigabe mit.
- Zwei E2E-Specs (`compare-editor-autosave.spec.ts`, `compare-editor-fidelity-s8d.spec.ts`) laufen laut Recherche bereits gegen Hub/`/compare/new` und bleiben grün; sollte sich das beim Implementieren als falsch herausstellen, ist das ein Blocker, kein Nebenbefund.
- F3 (#1206, #989) ist ausdrücklich NICHT Teil dieser Scheibe.

## Test Plan

TDD-RED: Die erweiterten Wächter-ACs (AC-1) in `issue_683_wizard_remove.test.ts` werden zuerst geschrieben und sind rot, solange `CompareEditor.svelte`/`compareEditorLogic.ts`/`compareAutosave.ts` noch existieren. Die anschließende Löschung macht sie grün. Kein Mail-Pfad, kein Renderer-Gate, keine Persistenz betroffen — `renderer_mail_gate.py` und die Mail-Validatoren greifen hier nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — reiner Rückbau, die Architekturentscheidung (Trip-Muster #622 für `/compare/new`, geteilte Tab-Organismen) fiel bereits in F2a (siehe `docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md`).
- **Rationale:** Diese Scheibe trifft keine neue Design- oder Architekturentscheidung, sondern entfernt ausschließlich Code, der durch F2a bereits ersetzt wurde. Die einzige Entscheidung mit Tragweite (Redirect-Route bleibt statt Löschung, siehe Known Limitations) ist eine Anwendung der bereits bestätigten Trip/Compare-Teilungs-Invariante, keine neue Architekturfrage.

## Changelog

- 2026-07-19: Initial spec erstellt — Epic #1301 Scheibe F2b (= #1273 S5)
