---
entity_id: epic_1273_s4b_unit_test_migration
type: feature
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [epic-1273, unit-test, test-migration, compare]
---

# Epic #1273 S4b — Unit-Test-Migration (CompareEditor.svelte Source-Inspection)

## Approval

- [ ] Approved

## Purpose

`CompareEditor.svelte` ist seit Slice S3 nur noch vom Create-Wizard (`/compare/new`) erreichbar und wird in Slice S5 ersatzlos gelöscht. Fünf Unit-Testdateien lesen aktuell per Source-Inspection (`readFileSync` + Struktur-Anker, da Svelte-5-Snippet-Komponenten ohne `@testing-library/svelte` nicht mountbar sind) Verhalten aus `CompareEditor.svelte`. Diese Scheibe migriert bzw. löscht diese fünf Dateien, bevor S5 sie unbemerkt mitreißen würde — drei Dateien prüfen ausschließlich CompareEditor-exklusives, im Hub nicht existierendes Verhalten (löschen), zwei Dateien enthalten je einen kleinen Testblock, der auf ein konkretes Hub-Äquivalent umgezogen werden muss (Rest der jeweiligen Datei bleibt unverändert gültig).

## Source

- **File:** `frontend/src/lib/components/compare/__tests__/compare_editor_gesture_capture_scope.test.ts`, `compare_editor_mobile_fidelity.test.ts`, `compare_editor_layout_tab_wiring.test.ts`, `step2_orte_library_grouping.test.ts`, `frontend/src/lib/components/shared/corridor-editor/corridorEditorMobile.test.ts` (alle fünf werden geändert; kein Produktivcode betroffen)
- **Identifier:** Node-Test-Runner `describe`-Blöcke in den fünf genannten Dateien; Umzugsziele sind `frontend/src/lib/components/compare/CompareTabs.svelte` Zeilen 269-283 (`toggleAddPanel()`/`addPanelLoadStarted`) und Zeile 1119 (`<CorridorEditorMobile context="vergleich">`)

## Estimated Scope

- **LoC:** ~-814 (drei Löschungen: 117+321+376 LoC) / +~15-30 (zwei kleine Testblock-Umzüge in bestehenden Dateien) → netto stark negativ, weit unter dem 250-LoC-Workflow-Limit
- **Files:** 5 (3 DELETE, 2 MODIFY)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` (Hub, laufend erweitert seit S1) | Produktivcode | Liefert die beiden Umzugsziele: Lazy-Gate `toggleAddPanel()`/`addPanelLoadStarted` (Zeilen 269-283) und den mobilen Idealwerte-Tab-Mount `<CorridorEditorMobile context="vergleich">` (Zeile 1119) |
| `frontend/src/lib/components/compare/CompareEditor.svelte` (bleibt bis S5 im Repo) | Produktivcode (unverändert) | Bisheriger Source-Anker der fünf Testdateien; nur noch vom Create-Wizard erreicht |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` (Create-Wizard, unverändert) | Produktivcode | Grouping-Logik (`groupLocations()`/`group_id`), von `step2_orte_library_grouping.test.ts` weiterhin geprüft — bleibt gültig, da der Create-Wizard laut Epic-Scope unverändert bestehen bleibt |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | Produktivcode (unverändert) | Vom umgezogenen Block in `corridorEditorMobile.test.ts` weiterhin auf `context="vergleich"`-Einbau geprüft |
| `docs/specs/modules/epic_1273_s4a_test_migration.md` (bereits abgeschlossene Schwester-Scheibe) | Spec (Referenz) | Format-/Ton-Vorbild; Lehre übernommen: vor Löschung prüfen, ob eine vermeintlich tote Datei doch noch gültige Einzel-Assertions enthält |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare/__tests__/compare_editor_gesture_capture_scope.test.ts` | DELETE | Prüft DOM-Containment der Gesten-Capture-Listener (`onEditorTouchGesture`/`onEditorValueChange`) — ein Architektur-Muster, das ausschließlich `CompareEditor.svelte` nutzt. Der Hub verwendet stattdessen pro-Commit-Handler `setSaving()`/`setSaved()` (`hubSaveCtl`, S1-Muster) statt generischem Touch-Capture. Kein Hub-Äquivalent vorhanden. |
| `frontend/src/lib/components/compare/__tests__/compare_editor_mobile_fidelity.test.ts` | DELETE | AC-6 bis AC-20, fast vollständig CompareEditor-eigene Mobile-Markup-Fidelity gegen den alten Mobile-Editor-Figma-Handoff (`.cm-mobile-appbar`, CTA-Füße, Testids `cm-mobile-*`, Step2Orte `dense`-Prop-Nutzung). Recherche bestätigt: der Hub nutzt `Step2Orte.svelte` gar nicht (eigene Orte-Verwaltung via `SortableList`, `CompareTabs.svelte:1059-1083`) und hat keine der geprüften CompareEditor-eigenen Testids/Markup-Strukturen. |
| `frontend/src/lib/components/compare/__tests__/compare_editor_layout_tab_wiring.test.ts` | DELETE | Prüft, dass `CompareEditor.svelte` den geteilten `LayoutTab`-Organism direkt mountet (`context="vergleich"`, ohne Hüllen-Wrapper) sowie `Step3Idealwerte`/`Step4Layout`-Dead-File-Guards und `LTComparePreview.svelte`-Inhalt. Der Hub mountet `LayoutTab` nicht — er nutzt eine andere Komponente `CompareLayoutRow` (`CompareTabs.svelte:1149` mobil, `:1165` Desktop) — die geprüfte Wiring-Beziehung existiert im Hub in dieser Form nicht. Verifiziert: `Step3Idealwerte.svelte`/`Step4Layout.svelte` existieren im Repo bereits nicht mehr, deren Dead-File-Guards sind dauerhaft trivial-grün und redundant zu 4 anderen Testdateien (`corridorEditorState.test.ts`, `corridorEditorMobile.test.ts`, `issue_462.test.ts`, `issue_683_wizard_remove.test.ts`). `LTComparePreview.svelte` wird laut Grep nur von `CompareEditor.svelte` importiert, nicht vom Hub — stirbt mit. |
| `frontend/src/lib/components/compare/__tests__/step2_orte_library_grouping.test.ts` | MODIFY | Der Großteil der Datei (AC-12, AC-13, Nebenbefund-Block) prüft `Step2Orte.svelte`'s Gruppierungslogik über `groupLocations()`/`group_id` — bleibt UNVERÄNDERT gültig, da `Step2Orte.svelte` über den Create-Wizard (`/compare/new`) weiterlebt. Nur der letzte `describe`-Block "Fix-Loop 1 (S5, Adversary F001 MEDIUM) … Gruppen-Fetch ist an den Orte-Tab-Besuch gekoppelt" (Zeilen 225-275, Source-Anker `COMPARE_EDITOR_FILE`, prüft `ceLoadGroups`/`ceGroupsLoadStarted`/`activeTab === 'orte'`) ist CompareEditor-exklusiv und wird auf das Hub-Äquivalent umgezogen: `CompareTabs.svelte` Zeilen 269-283, Funktion `toggleAddPanel()`, Guard-Flag `addPanelLoadStarted`, lädt `/api/locations` + `/api/groups` erst beim ersten Öffnen des "Ort hinzufügen"-Panels (`addPanelOpen`-Toggle), nicht beim Mount. |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorMobile.test.ts` | MODIFY | Nur der `describe`-Block "Einbau CompareEditor.svelte — Mobile-Zweig context=vergleich" (Zeilen 156-162, Source-Anker `COMPARE_EDITOR` = `CompareEditor.svelte`) betrifft CompareEditor exklusiv und wird auf `CompareTabs.svelte` Zeile 1119 umgezogen (`<CorridorEditorMobile context="vergleich">` im mobilen Idealwerte-Tab-Zweig, gated durch `isMobileViewport`/`idealwerteHydrated`). Rest der Datei (F001-Fix-Block, AC-15 Import-Checks, AC-14 Touch-Target-Struktur, "Einbau TripTabs.svelte"-Block) bleibt unverändert. |

### Estimated Changes
- Files: 5 (3 DELETE, 2 MODIFY)
- LoC: -814/+~30

## Implementation Details

Die fünf Änderungen sind voneinander unabhängig (anders als bei S4a gibt es hier keinen Mandanten-Sicherheitstest, der zuerst migriert werden müsste) und können in beliebiger Reihenfolge umgesetzt werden.

1. **`compare_editor_gesture_capture_scope.test.ts` löschen** — komplette Datei entfernen, kein Umzugsziel.
2. **`compare_editor_mobile_fidelity.test.ts` löschen** — komplette Datei entfernen, kein Umzugsziel.
3. **`compare_editor_layout_tab_wiring.test.ts` löschen** — komplette Datei entfernen, kein Umzugsziel; die Dead-File-Guard-Redundanz besteht bereits in vier anderen Dateien fort.
4. **`step2_orte_library_grouping.test.ts` umbauen** — den `describe`-Block "Fix-Loop 1 (S5, Adversary F001 MEDIUM)…" (Zeilen 225-275) so anpassen, dass er `CompareTabs.svelte` statt `CompareEditor.svelte` liest (neue Konstante analog `COMPARE_EDITOR_FILE`, z. B. `COMPARE_TABS_FILE = join(here, '..', 'CompareTabs.svelte')`) und gegen `toggleAddPanel()`/`addPanelLoadStarted`/`addPanelOpen` statt `ceLoadGroups()`/`ceGroupsLoadStarted`/`activeTab === 'orte'` prüft. Die vier restlichen `describe`-Blöcke (AC-12, AC-13, Nebenbefund) bleiben unangetastet, inklusive ihrer `readStep2()`-Anker auf `Step2Orte.svelte`.
5. **`corridorEditorMobile.test.ts` umbauen** — den `describe`-Block "Einbau CompareEditor.svelte — Mobile-Zweig context=vergleich" (Zeilen 156-162) so anpassen, dass er `CompareTabs.svelte` liest (neue Konstante statt `COMPARE_EDITOR`) und auf `<CorridorEditorMobile\s+context="vergleich">` in dieser Datei prüft; der `!/<Step3Idealwerte\b/`-Gegen-Check entfällt oder wird sinngemäß durch einen Hub-passenden Negativ-Check ersetzt (Hub hat kein `Step3Idealwerte`-Äquivalent zu verdrängen — die Prüfung reduziert sich auf den Positiv-Nachweis des Mounts). Alle übrigen Blöcke (F001-Fix, AC-15, AC-14, TripTabs-Einbau) bleiben Zeile für Zeile unverändert.

Kein Produktivcode betroffen — reine `*.test.ts`-Dateien unter `frontend/src/lib/components/`.

## Expected Behavior

- **Input:** fünf bestehende Node-Test-Runner-Unit-Testdateien unter `frontend/src/lib/components/`, drei davon lesen aktuell aus `CompareEditor.svelte`.
- **Output:** drei gelöschte Dateien (kein Verlust an gültiger Testabdeckung, da alle geprüften Verhaltensweisen CompareEditor-exklusiv sind), zwei angepasste Dateien mit je einem umgezogenen Testblock, der jetzt gegen `CompareTabs.svelte` (den Hub) prüft. Die Gesamtsuite bleibt grün.
- **Side effects:** keine — reine Testdatei-Migration, kein Produktivpfad geändert, kein neues Verhalten in `CompareTabs.svelte` eingeführt (die geprüften Mechanismen — Lazy-Gate, mobiler Mount — existieren dort bereits unverändert).

## Acceptance Criteria

- **AC-1:** Given `compare_editor_gesture_capture_scope.test.ts` prüft ein Gesten-Capture-Muster (`onEditorTouchGesture`/`onEditorValueChange`), das ausschließlich `CompareEditor.svelte` nutzt und für das der Hub kein Äquivalent hat (pro-Commit-Handler `setSaving()`/`setSaved()` statt generischem Touch-Capture) / When die Datei vollständig gelöscht wird / Then existiert sie nicht mehr im Repository und keine andere Testdatei referenziert `onEditorTouchGesture`/`onEditorValueChange`.
  - Test: `git status` zeigt die Datei als gelöscht; `grep -rl "onEditorTouchGesture\|onEditorValueChange" frontend/src/` liefert keine Treffer mehr; die verbleibende Testsuite im `compare/__tests__`-Verzeichnis läuft per `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/compare/__tests__/*.test.ts` fehlerfrei durch (kein Import-Fehler durch die Löschung).

- **AC-2:** Given `compare_editor_mobile_fidelity.test.ts` prüft CompareEditor-exklusive Mobile-Markup-Fidelity (`.cm-mobile-appbar`, CTA-Füße, Testids `cm-mobile-*`, Step2Orte-`dense`-Nutzung), und der Hub verwendet weder `Step2Orte.svelte` noch eine dieser Markup-Strukturen / When die Datei vollständig gelöscht wird / Then existiert sie nicht mehr im Repository und keine andere Testdatei referenziert die dort geprüften `cm-mobile-*`-Testids.
  - Test: `git status` zeigt die Datei als gelöscht; `grep -rl "cm-mobile-appbar\|cm-mobile-" frontend/src/lib/components/compare/__tests__/` liefert keine Treffer mehr; die verbleibende Testsuite im `compare/__tests__`-Verzeichnis läuft per `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/compare/__tests__/*.test.ts` fehlerfrei durch.

- **AC-3:** Given `compare_editor_layout_tab_wiring.test.ts` prüft, dass `CompareEditor.svelte` den `LayoutTab`-Organism direkt mountet, und der Hub stattdessen `CompareLayoutRow` nutzt (`CompareTabs.svelte:1149`/`:1165`) ohne 1:1-Wiring-Entsprechung, und die darin enthaltenen `Step3Idealwerte`/`Step4Layout`-Dead-File-Guards bereits redundant in vier anderen Testdateien (`corridorEditorState.test.ts`, `corridorEditorMobile.test.ts`, `issue_462.test.ts`, `issue_683_wizard_remove.test.ts`) abgesichert sind / When die Datei vollständig gelöscht wird / Then existiert sie nicht mehr im Repository und die vier genannten Dateien laufen weiterhin grün (belegen die Dead-File-Guards ohne Lücke fort).
  - Test: `git status` zeigt die Datei als gelöscht; `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/shared/corridor-editor/corridorEditorState.test.ts src/lib/components/shared/corridor-editor/corridorEditorMobile.test.ts src/lib/components/compare/issue_462.test.ts src/lib/components/compare/__tests__/issue_683_wizard_remove.test.ts` — Exit-Code 0, alle Tests als "pass" gemeldet.

- **AC-4:** Given `step2_orte_library_grouping.test.ts` hat einen CompareEditor-exklusiven Testblock ("Fix-Loop 1 (S5, Adversary F001 MEDIUM)…", Zeilen 225-275), der aktuell `ceLoadGroups()`/`ceGroupsLoadStarted`/`activeTab === 'orte'` in `CompareEditor.svelte` prüft, während der Hub dasselbe Lazy-Gate-Muster unter anderen Namen implementiert (`toggleAddPanel()`/`addPanelLoadStarted`/`addPanelOpen`, `CompareTabs.svelte:269-283`) / When der Block auf `CompareTabs.svelte` umgezogen und auf die Hub-Bezeichner angepasst wird, während die restlichen Blöcke (AC-12, AC-13, Nebenbefund, alle gegen `Step2Orte.svelte`) unverändert bleiben / Then läuft die gesamte Datei grün und der umgezogene Block schlägt fehl, wenn `addPanelLoadStarted` probehalber vor dem asynchronen Fetch-Aufruf entfernt wird (Nachweis, dass der Test echtes Verhalten prüft, nicht nur Textvorkommen).
  - Test: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/compare/__tests__/step2_orte_library_grouping.test.ts` — Exit-Code 0, alle Tests "pass"; zusätzlich Gegenprobe: eine temporäre lokale Kopie von `CompareTabs.svelte` ohne `addPanelLoadStarted = true;` vor dem `Promise.all`-Aufruf lässt den migrierten Race-Guard-Test fehlschlagen (Beweis über echten Testlauf-Output, nicht über Dateiinhalt-Grep).

- **AC-5:** Given `corridorEditorMobile.test.ts` hat einen CompareEditor-exklusiven `describe`-Block ("Einbau CompareEditor.svelte — Mobile-Zweig context=vergleich", Zeilen 156-162), der aktuell prüft, dass `CompareEditor.svelte` `<CorridorEditorMobile context="vergleich">` mountet, während der Hub exakt dasselbe an anderer Stelle tut (`CompareTabs.svelte:1119`, im mobilen Idealwerte-Tab-Zweig) / When der Block so umgebaut wird, dass er `CompareTabs.svelte` liest und denselben `<CorridorEditorMobile context="vergleich">`-Mount dort nachweist, während alle anderen Blöcke der Datei (F001-Fix, AC-15, AC-14, TripTabs-Einbau) unverändert bleiben / Then läuft die gesamte Datei grün und der umgezogene Test schlägt fehl, wenn der `context="vergleich"`-Mount in einer temporären lokalen Kopie von `CompareTabs.svelte` probehalber entfernt wird.
  - Test: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/shared/corridor-editor/corridorEditorMobile.test.ts` — Exit-Code 0, alle Tests "pass"; zusätzlich Gegenprobe: eine temporäre lokale Kopie von `CompareTabs.svelte`, in der Zeile 1119 durch eine andere Komponente ersetzt ist, lässt den migrierten Test fehlschlagen (echter Testlauf-Output als Nachweis, kein Grep).

- **AC-6:** Given alle fünf Dateien wie oben migriert sind (drei gelöscht, zwei mit umgezogenem Teilblock) / When die gesamte betroffene Unit-Test-Fläche (`compare/__tests__/` + `shared/corridor-editor/corridorEditorMobile.test.ts` + die vier in AC-3 genannten Dead-File-Guard-Dateien) läuft / Then sind alle Tests grün — kein Testfall schlägt fehl, weil er noch einen toten `CompareEditor.svelte`-Anker referenziert, und `grep -rl "CompareEditor.svelte" frontend/src/lib/components/compare/__tests__/ frontend/src/lib/components/shared/corridor-editor/` liefert keine Treffer mehr in Quellcode-Referenzen (Kommentare, die den historischen Kontext dokumentieren, sind zulässig).
  - Test: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/components/compare/__tests__/*.test.ts src/lib/components/shared/corridor-editor/corridorEditorMobile.test.ts src/lib/components/shared/corridor-editor/corridorEditorState.test.ts src/lib/components/compare/issue_462.test.ts src/lib/components/compare/__tests__/issue_683_wizard_remove.test.ts` — Exit-Code 0, alle Testfälle als "pass" gemeldet ist der alleinige Verhaltensnachweis dieses AC (kein reiner Datei-Grep als Ersatz).

## Nachtrag nach Implementierung

Beim finalen Suite-Lauf zeigten sich 3 zusätzliche rote Tests außerhalb der 5 Zieldateien:
- `corridorEditorState.test.ts` (4 Leaf-Fehlschläge in 2 Testblöcken — `COMPARE_METRIC_DEFS`/`buildComparePool`, jeweils Metrik-Anzahl 13 vs. 14 wegen `pop_max_pct`) — verifiziert unabhängig, stammt aus der separaten Metrik-Änderung #1296, NICHT Teil dieser Scheibe, bleibt unangetastet.
- `issue_683_wizard_remove.test.ts` ("AC-5: compare/[id]/edit/+page.svelte importiert CompareEditor", Zeile ~259) — direkt verwandtes, bisher übersehenes S3-Testdebt: die Route ist seit S3 nur noch ein Redirect-Platzhalter ohne CompareEditor-Import, der Test prüfte noch das Vor-S3-Verhalten. Als kleine Ergänzung mitkorrigiert (Kern-Test-Politik: kein Kern-Test darf vorbestehend rot liegen bleiben), Umfang bleibt minimal (1 Assertion in bereits identifizierter Testdatei-Familie).

Auch bei der Löschung von `compare_editor_layout_tab_wiring.test.ts` (AC-3) zeigte sich eine kleine Abweichung von der Spec-Annahme: von den 4 genannten "redundanten" Dateien hat nur `issue_683_wizard_remove.test.ts` tatsächlich einen echten Dead-File-Check für Step3Idealwerte/Step4Layout — die primäre Löschbegründung (andere Hub-Komponente, kein 1:1-Wiring) trägt die Entscheidung unabhängig davon.

## Known Limitations

- Diese Scheibe deckt nur die fünf identifizierten Dateien ab, die per Source-Inspection direkt aus `CompareEditor.svelte` lesen. Weitere Dateien, die `CompareEditor.svelte` nur beiläufig in Kommentaren erwähnen (z. B. als historischer Kontext oder Analogie-Referenz wie in `step2_orte_library_grouping.test.ts` Zeile 45), bleiben unverändert — solche Kommentare sind nach AC-6 explizit zulässig.
- `compare-editor-autosave-user-isolation.spec.ts` (Playwright-E2E, nicht Unit-Test) ist strukturell rot seit S3 und gehört laut S4a-Spec ebenfalls in eine Folge-Migration — diese Datei ist NICHT Teil des S4b-Scopes (E2E, kein Unit-Test-Source-Inspection-Idiom).
- Nach Abschluss dieser Scheibe hängt keine Unit-Testdatei mehr strukturell von `CompareEditor.svelte` ab — Slice S5 (Löschung von `CompareEditor.svelte` selbst) kann ohne Testregressions-Risiko auf Unit-Ebene erfolgen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testdatei-Migration ohne Produktivcode-Änderung — es entsteht keine neue Architektur, kein neuer Endpoint, keine neue Komponente. Die zugrundeliegende Architekturentscheidung (Compare-Editor als reiner Hub-Redirect, Hub als einzige Bearbeitungsfläche) wurde bereits in den Slices S1-S3 getroffen und dokumentiert (`docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md`, `..._s2_...md`, `..._s3_redirect.md`).

## Changelog

- 2026-07-17: Initial spec created
