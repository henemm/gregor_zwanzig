# Context: Epic #1273 Scheibe S4b — Unit-Test-Migration (CompareEditor.svelte Source-Inspection)

## Request Summary
`CompareEditor.svelte` ist seit S3 unerreichbar (nur noch `/compare/new` nutzt es für den Create-Wizard) und wird in S5 komplett gelöscht. 5 Unit-Testdateien lesen aktuell direkt aus `CompareEditor.svelte` (Source-Inspection-Idiom, da Svelte-5-Snippet-Props ohne `@testing-library/svelte` nicht mountbar sind). S4b migriert/löscht diese, bevor S5 sie ersatzlos mitreißen würde.

## Related Files

| File | LoC | Relevance |
|------|-----|-----------|
| `frontend/src/lib/components/compare/__tests__/compare_editor_gesture_capture_scope.test.ts` | 117 | Prüft DOM-Containment der Gesten-Capture-Listener (`onEditorTouchGesture`/`onEditorValueChange`), die "jede Nutzerberührung als dirty" erkennen — ein Architektur-Muster, das **nur** CompareEditor.svelte nutzt. Der Hub verwendet stattdessen pro-Commit-Handler `setSaving()`/`setSaved()` (S1-Muster, `hubSaveCtl`), kein generisches Touch-Capture. **Kein Hub-Äquivalent — löschen.** |
| `frontend/src/lib/components/compare/__tests__/compare_editor_mobile_fidelity.test.ts` | 321 | AC-6 bis AC-20: fast vollständig CompareEditor-eigene Markup-Fidelity (`.cm-desktop`/`.cm-mobile`-Blöcke, `cm-mobile-appbar`, CTA-Füße, Testids `cm-mobile-*`) gegen den alten Mobile-Editor-Figma-Handoff (JSX-M). AC-6/AC-7 grenzen an Step2Orte.svelte's `dense`-Prop (ein geteiltes Feature), aber im Kontext der jetzt sterbenden Mobile-Editor-Erfahrung. AC-20 ist explizit eine "Sharing-Invariante" (geteilte Organismen bleiben in CompareEditor referenziert) — wird mit der Datei selbst gegenstandslos. **Wahrscheinlich komplett löschen — offene Frage für Analyse: wird `Step2Orte`s `dense`-Modus irgendwo im Hub noch gebraucht, oder war er nur für den jetzt sterbenden Mobile-Editor?** |
| `frontend/src/lib/components/compare/__tests__/compare_editor_layout_tab_wiring.test.ts` | 376 | Prüft, dass CompareEditor.svelte den geteilten `LayoutTab`-Organism (`context="vergleich"`) direkt mountet (ohne redundante Step4Layout-Hülle) sowie Step3Idealwerte/Step4Layout-Löschung und `LTComparePreview.svelte`-Inhalt. Die Wiring-Prüfung selbst ("Organism direkt gemountet, kein Hüllen-Wrapper") ist ein Muster, das auch im Hub gelten sollte. **UMBAUEN: Source-Anker von `CompareEditor.svelte` auf die Hub-Datei umziehen, die `LayoutTab` mountet — muss in Analyse-Phase identifiziert werden.** |
| `frontend/src/lib/components/compare/__tests__/step2_orte_library_grouping.test.ts` | 275 | Prüft Step2Orte.svelte's Gruppierung über `groupLocations()`/`group_id` (geteilte, weiterlebende Logik) UND CompareEditor-eigenes Lazy-Loading-Gate für Gruppen (`ceGroups`-Pattern). **UMBAUEN: Step2Orte-Teile bleiben gültig, Lazy-Gate-Teil muss auf Hub-Äquivalent umgezogen werden (falls der Hub dieselbe Lazy-Fetch-Optimierung braucht).** |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorMobile.test.ts` | 162 gesamt, nur 1 `describe`-Block (~Zeile 156-165) betroffen | Der betroffene Block prüft, dass CompareEditor.svelte im mobilen Zweig `<CorridorEditorMobile context="vergleich">` mountet. Rest der Datei (TripTabs-Einbau, F001-Fix, Touch-Target-Struktur) bleibt unberührt. **UMBAUEN: nur diesen einen Block auf die Hub-Mount-Stelle ummünzen.** |

## Existing Patterns
- **Source-Inspection-Idiom:** `readFileSync` + Struktur-Anker (Textfenster-Proximity, Regex) statt echtem Component-Mount — etabliertes Projekt-Muster für Svelte-5-Snippet-Props, siehe auch `issue_683_wizard_remove.test.ts`, `StageDateField.test.ts`.
- **S4a-Vorbild:** Bei der e2e-Migration (S4a) stellte sich heraus, dass "erst löschen, dann grep nach Text-Erwähnungen" zu kosmetischen Adversary-Findings führte, aber v.a., dass vermeintlich lösch-reife Dateien oft Prüf-Logik enthalten, die eigentlich nur umgezogen werden muss (nicht gelöscht). Gleiches Muster hier: 2 Dateien wahrscheinlich löschbar, 3 enthalten Mischungen aus totem CompareEditor-Wiring und weiterlebender Fachlogik geteilter Komponenten.

## Dependencies
- Upstream: `CompareEditor.svelte` existiert weiterhin bis S5 (nur noch von `/compare/new` erreicht).
- Offene Fragen für Analyse-Phase:
  1. Wo genau mountet der Hub (`CompareTabs.svelte` bzw. `frontend/src/routes/compare/[id]/+page.svelte`) den `LayoutTab`-Organism mit `context="vergleich"`? (für `compare_editor_layout_tab_wiring.test.ts`-Umbau)
  2. Hat der Hub ein eigenes Lazy-Loading-Gate für Location-Gruppen, oder lädt er sie unbedingt? (für `step2_orte_library_grouping.test.ts`-Umbau)
  3. Mountet der Hub im mobilen Zweig `CorridorEditorMobile context="vergleich"`? Wo? (für `corridorEditorMobile.test.ts`-Umbau)
  4. Wird `Step2Orte`s `dense`-Prop irgendwo im Hub verwendet, oder war das eine reine Mobile-Editor-Eigenheit? (entscheidet, ob `compare_editor_mobile_fidelity.test.ts` AC-6/AC-7 wirklich vollständig tot sind)

## Existing Specs
- `docs/specs/modules/feat_1273_s1_compare_hub_save_chip.md`, `..._s2_...md`, `..._s3_redirect.md` — Hub-Architektur bisher.
- `docs/specs/modules/issue_1256_compare_ui_rewire.md` — Ursprung von `compare_editor_layout_tab_wiring.test.ts` und `step2_orte_library_grouping.test.ts`.
- `docs/specs/modules/feat_1256_s8d_mobile_editor_fidelity.md` — Ursprung von `compare_editor_mobile_fidelity.test.ts`.

## Analysis

### Type
Feature (Test-Migration als Folge-Scheibe des laufenden Epics #1273; kein Bugfix).

### Recherche-Ergebnis der 4 offenen Fragen (Explore-Agent, CompareTabs.svelte = die Hub-Datei)

1. **LayoutTab-Mount:** Der Hub mountet `LayoutTab.svelte` **nicht** — er nutzt eine eigene, andere Komponente `CompareLayoutRow` (CompareTabs.svelte:1149 mobil mit `dense`, :1165 Desktop ohne). Die in `compare_editor_layout_tab_wiring.test.ts` geprüfte Wiring-Beziehung (CompareEditor mountet LayoutTab direkt) existiert im Hub schlicht nicht in dieser Form — kein 1:1-Umzugsziel.
2. **CorridorEditorMobile:** Hub mountet `<CorridorEditorMobile context="vergleich">` im mobilen Idealwerte-Tab-Zweig, CompareTabs.svelte:1119 — exaktes Analogon zur CompareEditor-Assertion. Klares Umzugsziel.
3. **Gruppen-Lazy-Loading:** Hub hat ein eigenes Lazy-Gate (`toggleAddPanel()`/`addPanelLoadStarted`, CompareTabs.svelte:269-283) — andere Variablennamen, gleiches Muster (laden erst beim ersten Öffnen des "Ort hinzufügen"-Panels statt beim Mount).
4. **Step2Orte im Hub:** Wird **nicht** verwendet — der Hub hat eine eigene Orte-Verwaltung (Drag/Drop via `SortableList`, CompareTabs.svelte:1059-1083). `Step2Orte.svelte` lebt aber weiter über den Create-Wizard (`/compare/new`, bleibt laut Epic-Scope unverändert bestehen) — die reinen Step2Orte-Grouping-Assertions in `step2_orte_library_grouping.test.ts` sind daher NICHT tot, unabhängig vom Hub.

### Affected Files (revidiert nach Recherche)

| File | Change Type | Description |
|------|-------------|-------------|
| `compare_editor_gesture_capture_scope.test.ts` (117 LoC) | DELETE | Hub-Autosave nutzt anderes Muster (pro-Commit-Handler statt generischem Touch-Capture) — kein Äquivalent. |
| `compare_editor_mobile_fidelity.test.ts` (321 LoC) | DELETE | Hub nutzt weder Step2Orte noch CompareEditor-eigene CTA-Fuß-/Appbar-Markup. Vollständig CompareEditor-exklusive UI, die mit S5 ersatzlos verschwindet. |
| `compare_editor_layout_tab_wiring.test.ts` (376 LoC) | DELETE (mit Vorbehalt) | Hub nutzt `CompareLayoutRow`, nicht `LayoutTab` direkt — die geprüfte Wiring-Beziehung existiert im Hub nicht. Vorbehalt: prüfen ob `Step3Idealwerte`/`Step4Layout`-Dead-File-Guards und `LTComparePreview.svelte`-Checks noch einen eigenständigen Wert haben (ggf. als Mini-Regressionsanker an anderer Stelle erhalten) — Detailentscheidung in der Spec. |
| `step2_orte_library_grouping.test.ts` (275 LoC) | MODIFY | Step2Orte-Grouping-Assertions (Großteil der Datei) bleiben unverändert gültig (Create-Wizard nutzt Step2Orte weiter). Nur der CompareEditor-spezifische `ceGroups`-Lazy-Gate-Testblock (Mini-Fix-Loop 1 laut Datei-Header) wird auf das Hub-Äquivalent (`addPanelLoadStarted`/`toggleAddPanel`, CompareTabs.svelte:269-283) umgezogen. |
| `corridorEditorMobile.test.ts` (162 LoC gesamt) | MODIFY | Nur der eine `describe`-Block "Einbau CompareEditor.svelte — Mobile-Zweig context=vergleich" (~Zeile 156-165) wird auf CompareTabs.svelte:1119 umgezogen (identisches Assertion-Muster). Rest der Datei unverändert. |

### Scope Assessment
- Files: 5 (3 DELETE, 2 MODIFY — jeweils nur ein kleiner Teilblock pro MODIFY-Datei)
- Estimated LoC: ~-814 (3 Löschungen) / +~15-30 (2 kleine Testblock-Umzüge) → netto stark negativ, deutlich unter dem 250-LoC-Limit
- Risk Level: LOW — reine Testdateien, kein Produktivcode betroffen

### Technical Approach
1. `corridorEditorMobile.test.ts`: den einen Block auf `CompareTabs.svelte`-Pfad + Zeile ~1119 umziehen, exakt gleiches Assertionsmuster (`context="vergleich"` im mobilen Zweig).
2. `step2_orte_library_grouping.test.ts`: nur den `ceGroups`-Lazy-Gate-Block identifizieren und auf `addPanelLoadStarted`/`toggleAddPanel`-Pattern in `CompareTabs.svelte` umziehen; Rest der Datei unangetastet lassen.
3. Die 3 DELETE-Kandidaten vor dem Löschen nochmal auf versteckte, noch gültige Einzel-Assertions prüfen (Lehre aus S4a: nicht blind nach Dateiname löschen) — insbesondere bei `compare_editor_layout_tab_wiring.test.ts` den Wert der Dead-File-Guards (Step3Idealwerte/Step4Layout) und `LTComparePreview.svelte`-Checks separat bewerten.
4. Kein Produktivcode betroffen.

### Dependencies
- Upstream: keine (CompareEditor.svelte bleibt bis S5 im Repo, nur die Testabdeckung wird umgezogen).
- Downstream: keine.

### Open Questions — GEKLÄRT
- Step3Idealwerte.svelte/Step4Layout.svelte existieren im Repo bereits nicht mehr (verifiziert). Die Dead-File-Guards in `compare_editor_layout_tab_wiring.test.ts` sind damit dauerhaft trivial-grün und redundant — dieselbe Tatsache wird bereits in 4 anderen Testdateien abgesichert (`corridorEditorState.test.ts`, `corridorEditorMobile.test.ts`, `issue_462.test.ts`, `issue_683_wizard_remove.test.ts`). `LTComparePreview.svelte` wird laut Grep NUR von `CompareEditor.svelte` importiert (nicht vom Hub) — stirbt also mit. **Ergebnis: `compare_editor_layout_tab_wiring.test.ts` komplett löschen, kein Vorbehalt mehr.**

## Risiken & Überlegungen
- Anders als bei S4a (reine e2e-URL/Testid-Fixes) braucht S4b für 3 von 5 Dateien echtes Verständnis der aktuellen Hub-Implementierung, um die richtigen Umzugsziele zu finden — das ist Kern der Analyse-Phase, nicht mehr des Context-Schritts.
- Risiko einer Fehleinschätzung wie bei S4a (dort stellte sich erst beim Implementieren heraus, dass eine vermeintlich stabile Datei selbst kaputt war) — Analyse-Phase sollte die Hub-Datei(en) tatsächlich lesen, nicht nur vermuten.
