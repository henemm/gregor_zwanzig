# Context: fix-2288-etappen-dnd

## Request Summary
Issue #2288 (Epic #2345, Etappe P2): Der Desktop-Etappen-Strip sortiert per natives HTML5-`draggable`,
alle anderen Sortier-Flächen (Orte, Metriken, Buckets, mobile Etappenliste) per geteiltem
`SortableList`/`DragHandle` (ADR-0024). Ziel: eine DnD-Technik, Wächter gegen Rückfall.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` (155 Z.) | Die einzige Fläche mit nativem HTML5-DnD (Z. 36-75, 99-107). Strip ist horizontal; zwischen Karten liegen `+ Pause`-Lücken, am Ende der `+ Etappe`-Knopf |
| `frontend/src/lib/components/shared/dnd/SortableList.svelte` (113 Z.) | Geteilter Baustein; Zone ist hart `flex-direction: column`; `dndzone` entfernt Nicht-Item-Kinder aus der Zone; Vertrag `onDndReorder(ids)` nur bei finalize; `onDndReorderEnd` existiert schon |
| `frontend/src/lib/components/shared/dnd/DragHandle.svelte` (56 Z.) | Griff-Atom (`<span role="button" tabindex=0>`, nie `<button>`) |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Einziger Aufrufer des Strips (Z. ~733). Mobil-Zweig (`isMobileViewport`, Z. 659-729) nutzt schon `SortableList`. `handleStagesReorder` (Z. 488) feuerte bisher bei JEDEM dragover; `handleReorderEnd` → `settleMootCascade` |
| `frontend/src/lib/components/trip-detail/StageCard.svelte` (waypoints/) | Karte im Strip |
| `frontend/src/lib/components/compare/GroupSection.svelte` | Zweite Fundstelle `draggable="true"` (Z. 86). Verwaist (0 Importeure) — gehört laut Epic #2345 und ADR-0024 Pkt. 7 zu #2235 (Totcode) |
| `docs/adr/0024-ein-sortier-baustein-svelte-dnd-action.md` | Z. 89-92 + 139: Strip „einzige geduldete HTML5-Ausnahme"; „wird der Non-Item-Kinder-Konflikt gelöst, ist die Fläche nachzuziehen". ADR ist anzupassen (Changelog) |

## Tests, die den heutigen Strip kennen
- `frontend/e2e/issue-498-stage-date-autosave.spec.ts`: Z. 633-660 `dragTo()` (nativ, HTML5) und Z. 1093-1150 Zwischenstationen-Drag (Bug #1393 R2-F002) — brechen garantiert, müssen auf das Pointer-Muster `dragDndZoneItem` (`compare-hub-inline-edit.spec.ts:22-38`) umgeschrieben werden (ADR-0024 Konsequenzen). Weitere Strip-Specs: Z. 1383-1555 (`data-locked`, Sperre während Kaskaden-Antwort).
- `frontend/src/lib/components/edit/issue_585_waypoint_editor_jsx.test.ts`: Dateiinhalt-Prüfungen am Strip (Eyebrow „DRAG ZUM SORTIEREN", PauseInsertGap 56px, `+ Pause`, `+ Etappe` dashed) — Texte/Maße müssen erhalten bleiben oder Test mitziehen.
- `frontend/src/lib/components/compare/__tests__/issue_453_locations_rail.test.ts:37`: prüft `draggable` in GroupSection (Totcode; fällt mit #2235).
- `frontend/e2e/waypoints-editor.spec.ts`, `issue-407-waypoint-editor-screen.spec.ts`: `etappen-strip` sichtbar (testid erhalten).
- Spec `docs/specs/modules/fix_1771_s1_dnd_wartestrategie.md`: Wartestrategie für DnD-Tests (Helper `dnd-helper-finalize-wait.spec.ts`).

## Existing Patterns
- `SortableList` mit Snippet-Row; bedingtes Markup zwischen Zeilen gehört INS Snippet (Item-Wrapper), nie Sibling in die Zone.
- Mobil-Etappenliste (`EditStagesPanelNew` Z. 693) ist der Präzedenzfall: `onDndReorder` + `onDndReorderEnd={handleReorderEnd}`.
- Bug #1393-Invariante: Kaskaden-Rückfrage wird erst beim Ablegen bewertet; `locked` (cascadeBusy) sperrt bauliche Änderungen sichtbar.

## Kernkonflikt / Lösungsrichtung
`dndzone` löscht Nicht-Item-Kinder → Pause-Lücke und `+ Etappe`-Knopf müssen ins Item-Snippet (Lücke als Teil des Items, hinter der Karte) bzw. außerhalb der Zone (Knopf als Geschwister des Zonen-Containers, in gemeinsamer Flex-Zeile). `SortableList` braucht eine waagerechte Variante (neuer optionaler Prop, z. B. `direction="horizontal"`, Default unverändert vertikal → Bestands-Konsumenten unberührt). Pause-Lücke im Item: Die letzte Etappe hat keine Lücke danach (`i < len-1`); beim Umsortieren wandert die Lücke mit dem Item — Index-Logik `onPauseInsert(i)` bleibt über den Item-Index korrekt.

## Dependencies
- Upstream: `svelte-dnd-action` (Version laut ADR 0.9.69), `StageCard`, `isPauseStage`.
- Downstream: `EditStagesPanelNew` (Kaskaden-Settling), Trip-Editor E2E-Suite.

## Existing Specs
- `docs/specs/modules/fix_1771_s1_dnd_wartestrategie.md`, `docs/specs/fast/feat-848-dnd-metrics.md`, ADR-0024 (Spec #1272).

## Risks & Considerations
- **Wächter AC-2 (`git grep "draggable="` nur in `shared/dnd/`)** würde an `GroupSection.svelte` (Totcode, #2235) rot: Wächter muss diese Datei explizit ausnehmen (mit Verweis #2235) oder #2235 zuerst — keine stille Ausnahme.
- Drag per Pointer-Events statt HTML5 → alle nativen `dragTo`-E2E-Tests brechen (bekannt, siehe oben); Zwischenstationen-Test (#1393 R2-F002) neu formulieren: jetzt feuert `onDndReorder` nur bei finalize — Test muss das beweisen (Mutation: Reorder bei consider feuern lassen).
- Horizontales Scrollen (`overflow-x:auto`) und Touch-Verhalten: `svelte-dnd-action` Autoscroll prüfen.
- Hover-Breitenanimation der Pause-Lücke (8→56px) darf das Ziehen nicht stören.
- Barrierefreiheit: Griff + `aria-label` an Zone/Items (ADR-Folgepflicht); Tastatur-Pfad Leertaste/Pfeile neu am Strip verfügbar.
- Trip/Ortsvergleich-Teilung: Änderung ist reine Angleichung (Trip an geteilten Baustein) — Pendant-Frage erfüllt.
- Dateien in `src/app/models.py` etc. werden nicht berührt (kein Schema-Risiko).

## Analysis

### Type
Feature/Rework (type:rework, Epic #2345 Etappe P2) — Angleichung des Etappen-Strips an den geteilten Sortier-Baustein.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/dnd/SortableList.svelte` | MODIFY | Neuer optionaler Prop `direction` (vertical/horizontal), Default vertikal, Bestands-Konsumenten unberührt |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | MODIFY | Natives `draggable`/`ondrag*`/`reorder()` entfernen; `SortableList` + `DragHandle`; Pause-Lücke ins Item-Snippet; `+ Etappe` als Geschwister der Zone |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY (klein) | `onStagesReorder`-Vertrag auf `ids[]` + `onReorderEnd` (analog Mobil-Zweig Z. 693) |
| `frontend/e2e/issue-498-stage-date-autosave.spec.ts` | MODIFY | `dragTo` auf Pointer-Muster `dragDndZoneItem`; Zwischenstationen-Test (#1393 R2-F002) neu |
| `frontend/src/lib/components/edit/issue_585_waypoint_editor_jsx.test.ts` | MODIFY | Texte/Maße erhalten, sonst Test mitziehen |
| neuer Wächter-Test (`draggable=` nur in `shared/dnd/`) | CREATE | AC-2; `GroupSection.svelte` (Totcode, #2235) explizit mit Verweis ausnehmen |
| `docs/adr/0024-…md` | MODIFY | Strip-Ausnahme streichen, Changelog |

### Scope Assessment
- Files: ~6 produktiv/Test + ADR
- Estimated LoC: +150/-80
- Risk Level: MEDIUM (Pointer-DnD statt HTML5 bricht alle nativen E2E-Drag-Tests; horizontales Scrollen/Touch; #1393-Invariante)

### Technical Approach
1. `SortableList` horizontale Variante (Flex-Richtung per Prop, Items `flex-shrink:0`).
2. Strip: `SortableList items={stages.map(id)}`; Item-Snippet = Karte + (bei `i < len-1`) `+ Pause`-Lücke; Lücke wandert mit dem Item, `onPauseInsert(i)` bleibt über Index korrekt. `+ Etappe`-Knopf in gemeinsamer Flex-Zeile NEBEN der Zone (dndzone löscht Nicht-Item-Kinder).
3. `onDndReorder` feuert nur bei finalize → #1393-Invariante (Kaskaden-Rückfrage erst beim Ablegen) strukturell erfüllt; `onDndReorderEnd` → `settleMootCascade`. `locked` bleibt (opacity/pointer-events + `data-locked`).
4. `DragHandle` an jeder Karte (a11y: Griff + aria-label, Tastatur-Pfad neu).
5. Wächter: Test greppt `draggable=` in `frontend/src`, nur `shared/dnd/` erlaubt, `GroupSection` benannt ausgenommen (siehe #2235).

### Dependencies
- `svelte-dnd-action` 0.9.69, `StageCard`, `isPauseStage`; Downstream `EditStagesPanelNew` (Kaskaden-Settling), Trip-Editor-E2E-Suite.

### Open Questions
- [ ] Wächter-Ausnahme `GroupSection.svelte` vs. #2235 vorziehen — Empfehlung: Ausnahme mit Verweis (kein Scope-Kriechen).
- [ ] Autoscroll der horizontalen Zone bei `overflow-x:auto` per E2E messen.
- [ ] Hover-Breitenanimation der Pause-Lücke (8→56px) darf Drag nicht stören — in Spec als AC.
