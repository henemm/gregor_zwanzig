---
entity_id: etappen_strip_sortable_list
type: module
created: 2026-10-06
updated: 2026-10-06
status: draft
version: "1.0"
workflow: fix-2288-etappen-dnd
tags: [frontend, dnd, trip-editor, epic-2345, adr-0024]
---

# Etappen-Strip sortiert über den geteilten Sortier-Baustein (#2288)

- **Issue:** #2288 (Epic #2345, Etappe P2)
- **Typ:** Rework (Angleichung an den geteilten Baustein), kein neues Nutzerfeature

## Approval

- [ ] Approved

## Purpose

Der Desktop-Etappen-Strip im Trip-Editor sortiert heute per nativem HTML5-`draggable`. Alle anderen
Sortier-Flächen (Orte, Metriken, Buckets, mobile Etappenliste) nutzen den geteilten Baustein
`SortableList`/`DragHandle` (ADR-0024). Diese Spec überführt den Strip auf denselben Baustein,
sodass es im Frontend nur noch EINE Drag-Technik gibt (Pointer-Events über `svelte-dnd-action`,
mit Griff und Tastatur-Pfad), und sichert das mit einem Wächter-Test gegen Rückfall.

**Trip/Ortsvergleich-Teilung:** Die Änderung ist eine reine Angleichung an den bereits geteilten
Baustein (Trip-Strip wird zum Konsumenten wie der Orte-Reiter im Ortsvergleich). Es entsteht kein
neuer Trip- oder Compare-eigener Baustein; die Pendant-Frage ist damit erfüllt.

## Source

- `frontend/src/lib/components/shared/dnd/SortableList.svelte` — MODIFY: neuer optionaler Prop
  `direction?: 'vertical' | 'horizontal'` (Default `'vertical'`), Items `flex-shrink:0` in der
  waagerechten Variante.
- `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` — MODIFY: natives
  `draggable`/`ondrag*`/`reorder()`/`drag`-State entfernen; `SortableList` (horizontal) +
  `DragHandle` je Karte; `+ Pause`-Lücke ins Item-Snippet; `+ Etappe`-Knopf als Geschwister der
  Zone in gemeinsamer Flex-Zeile. Öffentliche Props bleiben (`onStagesReorder(Stage[])`,
  `onReorderEnd`, `locked` …); der Strip übersetzt die IDs aus `onDndReorder` zurück in `Stage[]`.
- `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` — MODIFY (nur Kommentar):
  der Kommentar an `handleStagesReorder` („meldet jede Zwischenposition") ist nach der Umstellung
  falsch und wird korrigiert; Logik unverändert (`cascadeBusy`-Riegel bleibt als zweite Linie).
- `frontend/e2e/issue-498-stage-date-autosave.spec.ts` — MODIFY: `dragTo()` (Z. ~633-660) und
  Zwischenstationen-Test #1393 R2-F002 (Z. ~1093-1150) auf das Pointer-Muster `dragDndZoneItem`
  (`frontend/e2e/helpers.ts`, siehe `fix_1771_s1_dnd_wartestrategie.md`).
- `frontend/e2e/helpers.ts` + neue Spec `frontend/e2e/etappen-strip-touch-dnd.spec.ts` — MODIFY/CREATE:
  Touch-Helfer `dragDndZoneItemTouch` und Touch-Test (AC-10).
- `frontend/src/lib/components/edit/issue_585_waypoint_editor_jsx.test.ts` — MODIFY (nur falls
  Texte/Maße sich ändern; Eyebrow, 56px-Lücke, `+ Pause`, `+ Etappe` dashed bleiben erhalten).
- `frontend/src/lib/components/shared/dnd/no_native_draggable_guard.test.ts` — CREATE:
  Wächter-Test (`# doc-compliance-test`).
- `frontend/src/lib/components/compare/GroupSection.svelte` — DELETE: verwaister Totcode (0
  Importeure, ~120 Zeilen), trug das letzte native `draggable="true"` außerhalb `shared/dnd/`.
  PO-Entscheidung 2026-10-06: kein Wächter-Ausnahmeeintrag, Löschung in diesem Ticket.
- Strukturtests, die nur den Dateiinhalt von `GroupSection.svelte` prüfen — MODIFY: die
  GroupSection-Abschnitte entfallen mit der Datei, übrige Prüfungen der Dateien bleiben:
  `frontend/src/lib/components/compare/__tests__/issue_453_locations_rail.test.ts`,
  `frontend/src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts`,
  `frontend/src/lib/components/compare/issue_462.test.ts`,
  `frontend/src/lib/issue_390_compare_atomic_migration.test.ts` (nur die AC-3-/GroupSection-Fälle).
- `docs/adr/0024-ein-sortier-baustein-svelte-dnd-action.md` — MODIFY: Strip-Ausnahme und
  `GroupSection`-Hinweis (Pkt. 7 und Folgepflicht) streichen, Changelog-Eintrag.

> **Schicht:** ausschließlich Frontend (`frontend/src`, `frontend/e2e`) und ADR. Kein Go, kein
> Python, keine Persistenzänderung (kein Schema-Risiko).

## Estimated Scope

- **LoC:** ca. +150 / −200 (davon ~120 gelöschter Totcode)
- **Files:** ca. 12 (1 gelöscht, 4 Strukturtests angepasst, 2 neu, ADR, Bestand)
- **Effort:** medium (Risiko MEDIUM: Pointer-DnD statt HTML5 bricht alle nativen E2E-Drag-Tests)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `svelte-dnd-action` 0.9.69 | Bibliothek | `dndzone`, Autoscroll, Tastatur-Pfad; entfernt Nicht-Item-Kinder aus der Zone |
| `SortableList.svelte` / `DragHandle.svelte` | geteilter Baustein | Vertrag `onDndReorder(ids)` nur bei finalize, `onDndReorderEnd` |
| `StageCard.svelte`, `isPauseStage` | Komponente/Helfer | Karteninhalt, Zähler |
| `EditStagesPanelNew.svelte` | einziger Aufrufer | `handleStagesReorder`, `handleReorderEnd` → `settleMootCascade`, `cascadeBusy` |
| `frontend/e2e/helpers.ts` `dragDndZoneItem` | Test-Helfer | Pointer-Ziehgeste mit Warten auf `finalize` (#1771 S1) |

## Implementation Details

1. **`SortableList`**: neuer Prop `direction` (Default `'vertical'`). Die Zone setzt
   `flex-direction` je nach Prop (`column` / `row`); in der waagerechten Variante bekommen
   Item-Wrapper `flex-shrink:0`. `overflow-x:auto` setzt der Konsument über die Zone (Strip), nicht
   der Baustein. Bestands-Konsumenten übergeben den Prop nicht und bleiben bitgleich.
2. **Strip-Aufbau** (Kernkonflikt: `dndzone` löscht Nicht-Item-Kinder):
   ```
   <div data-testid="etappen-strip" style="display:flex; flex-direction:row; overflow-x:auto; …">
     <SortableList direction="horizontal" items={stages.map(s => s.id)} …>
       {#snippet row(id, i)}
         <DragHandle /> <StageCard …/>
         {#if i < stages.length - 1 && onPauseInsert} <PauseInsertGap {i}/> {/if}
       {/snippet}
     </SortableList>
     {#if onAddStage}<button class="add-stage-btn">+ Etappe</button>{/if}
   </div>
   ```
   Die `+ Pause`-Lücke ist Teil des Items (hinter der Karte), wandert also beim Umsortieren mit
   ihm; die Bedingung `i < stages.length - 1` wird auf den aktuellen Item-Index ausgewertet, die
   letzte Etappe hat nie eine Lücke. `onPauseInsert(i)` erhält den Index des Items → bleibt korrekt.
   Der `+ Etappe`-Knopf liegt außerhalb der Zone als Geschwister in derselben Flex-Zeile.
3. **Meldeweg:** `onDndReorder(ids)` (nur finalize) → Strip mappt `ids` auf `Stage[]` und ruft
   `onStagesReorder`; direkt danach `onDndReorderEnd` → `onReorderEnd`. Damit wird die
   #1393-Invariante strukturell erfüllt (kein Zwischenstand während des Ziehens).
4. **`locked`:** unverändert am Wrapper (`opacity:0.5; pointer-events:none`, `data-locked`,
   `aria-busy`); `pointer-events:none` verhindert zusätzlich den Drag-Start.
5. **Barrierefreiheit:** `DragHandle` je Karte (Default-Label), `ariaLabel` an der Zone
   („Etappen sortieren"), `itemLabel` je Item (Etappenname).

## Entscheidungen (offene Fragen der Analyse)

- **E-1 `GroupSection.svelte` wird gelöscht (PO-Entscheidung 2026-10-06):** Die verwaiste Datei
  trug das letzte native `draggable="true"`. Statt einer befristeten Wächter-Ausnahme wird sie in
  diesem Ticket samt der Strukturtests, die nur ihren Dateiinhalt prüfen, entfernt. Der Wächter
  hat dadurch KEINE Ausnahmeliste. #2235 (Totcode-Sammelliste) muss dafür nichts mehr tun.
- **E-2 Autoscroll:** wird als messbarer AC (AC-8) per E2E geprüft, nicht angenommen.
- **E-3 Hover-Animation der Lücke:** eigener AC (AC-4).
- **E-4 Mobil-Zweig** (`isMobileViewport`, nutzt bereits `SortableList`) bleibt unverändert.

## Expected Behavior

- **Input:** Nutzer zieht eine Etappenkarte am Griff (Maus/Touch) oder greift sie per Leertaste.
- **Output:** Die Reihenfolge wird erst beim Ablegen gemeldet und gespeichert; Kaskaden-Rückfrage
  wird erst dann bewertet.
- **Side effects:** Keine Persistenzänderung (kein Schema); die Reihenfolge wird beim Ablegen
  in `handleReorderEnd` gespeichert (siehe „Abweichungen bei der Umsetzung").

## Acceptance Criteria

- **AC-1:** Given ein Trip mit mindestens drei Etappen im Desktop-Editor / When der Nutzer die
  mittlere Etappenkarte am Griff anfasst, über die erste Karte zieht und dort ablegt / Then
  erscheint die neue Reihenfolge, `onStagesReorder` wird genau einmal beim Ablegen (finalize)
  gerufen, nie während des Ziehens (consider), und die Kaskaden-Rückfrage (#1393) wird erst nach
  dem Ablegen bewertet.
  - Test: E2E (`issue-498-stage-date-autosave.spec.ts`, Zwischenstationen-Test neu): Ziehen mit
    `dragDndZoneItem`; während der Geste (nach Move, vor Mouse-up) bleibt die gespeicherte
    Reihenfolge/Stage-Liste im Editor unverändert und es erscheint keine Rückfrage; nach Mouse-up
    genau ein Reorder und ggf. Rückfrage. Komponententest: `SortableList`-Vertrag (Reorder nur bei
    finalize) über die Strip-Verdrahtung.

- **AC-2:** Given der Quellbaum `frontend/src` / When der Wächter-Test `draggable=` über alle
  Dateien sucht / Then kommen Treffer ausschließlich unter `shared/dnd/` vor (keine Ausnahmeliste; `compare/GroupSection.svelte`
  ist gelöscht), und der Test wird rot, sobald `EtappenStrip.svelte` oder eine andere Datei wieder `draggable=` enthält.
  - Test: `no_native_draggable_guard.test.ts` mit `# doc-compliance-test` (einzig zulässiger
    Dateiinhalt-Check); der Test enthält keine Ausnahmeliste. Zusätzlich: `GroupSection.svelte`
    existiert nicht mehr, und kein verbliebener Test/Import verweist auf sie.

- **AC-3:** Given Trip mit drei oder mehr Etappen und `onPauseInsert` gesetzt / When der Nutzer die
  erste Etappe hinter die zweite zieht / Then wandert die `+ Pause`-Lücke mit ihrem Item, die jetzt
  letzte Etappe hat keine Lücke, ein Klick auf die Lücke nach Position i ruft `onPauseInsert(i)`
  mit dem aktuellen Index, und der `+ Etappe`-Knopf bleibt sichtbar neben der Zone (am Strip-Ende).
  - Test: Komponententest/E2E: nach dem Umsortieren existiert
    `etappen-strip-pause-after-{n-2}`, aber nicht `etappen-strip-pause-after-{n-1}`;
    `+ Pause`-Klick fügt die Pause an der erwarteten Position ein; `+ Etappe` sichtbar und
    klickbar (legt Etappe an).

- **AC-4:** Given der Nutzer hält eine Karte gezogen / When der Zeiger über eine Pause-Lücke fährt
  und deren Breite per Hover von 8 auf 56 px animiert / Then bricht das Ziehen nicht ab, die Karte
  lässt sich weiter ablegen, und die Reihenfolge ist danach korrekt.
  - Test: E2E: Drag über mindestens zwei Lücken hinweg (Zeigerpfad quer durch die Lücken), danach
    erwartete Reihenfolge und genau ein finalize.

- **AC-5:** Given der Strip ist `locked` (Antwort auf die Kaskaden-Rückfrage wird geschrieben) /
  When der Nutzer versucht, eine Karte zu ziehen / Then bleibt die Reihenfolge unverändert, der
  Strip trägt `data-locked="true"` und `aria-busy`, hat `opacity: 0.5`, und die testid
  `etappen-strip` sowie der Eyebrow-Text „DRAG ZUM SORTIEREN" sind weiterhin vorhanden.
  - Test: bestehende Specs Z. ~1383-1555 (`data-locked`, Sperre während Kaskaden-Antwort) auf
    Pointer-Drag umgestellt; `waypoints-editor.spec.ts`/`issue-407-…spec.ts` prüfen testid weiter.

- **AC-6:** Given `SortableList` ohne Prop `direction` (alle Bestandskonsumenten: Orte, Metriken,
  Buckets, mobile Etappenliste) / When sie gerendert werden / Then ist die Zone weiterhin
  vertikal (`flex-direction: column`) und ihr Verhalten unverändert; nur mit
  `direction="horizontal"` läuft sie als Zeile.
  - Test: Komponententest: berechneter Stil der Zone ohne Prop = `column`, mit Prop = `row`;
    bestehende Orte-/Metriken-Drag-Specs laufen unverändert grün.

- **AC-7:** Given der Strip im Desktop-Editor / When der Nutzer mit Tab zu einer Karte navigiert,
  die Leertaste drückt und mit den Pfeiltasten verschiebt / Then trägt jeder Griff ein
  `aria-label`, die Zone und die Items sind beschriftet, die Etappe wird per Tastatur umsortiert und
  nach erneutem Leertasten-Druck genau einmal gemeldet (finalize).
  - Test: Playwright-Tastaturtest (Fokus auf `drag-handle`, Space, ArrowRight, Space) und
    Prüfung der Labels; analog zum Tastatur-AC aus ADR-0024 (AC-4).

- **AC-8:** Given ein Trip mit so vielen Etappen, dass der Strip horizontal überläuft
  (`overflow-x:auto`) / When der Nutzer eine Karte gezogen an den rechten bzw. linken Rand des
  sichtbaren Strips hält / Then scrollt der Strip automatisch waagerecht (Autoscroll) und die
  Karte lässt sich an einer zuvor unsichtbaren Position ablegen.
  - Test: E2E lokal/Staging: `scrollLeft` vor und nach dem Halten am Rand wächst um mindestens eine
    Kartenbreite, danach Ablegen am Strip-Ende und Prüfung der neuen Reihenfolge (verbindlich, nicht
    „nach Möglichkeit"). Falls `svelte-dnd-action` den Autoscroll im überlaufenden Flex-Container
    nicht liefert, ist das ein Befund dieses Tickets (Behebung hier, kein Ausnahme-Antrag).

- **AC-9:** Given ADR-0024 / When diese Spec umgesetzt ist / Then enthält ADR-0024 keine
  Strip-Ausnahme mehr (Pkt. 7 und der `GroupSection`-Hinweis sind gestrichen, die Folgepflicht
  „EtappenStrip bleibt die einzige geduldete HTML5-Ausnahme" ist gestrichen) und das Changelog
  trägt einen Eintrag zu #2288.
  - Test: bestehender `tests/test_adr_index_drift.py` bleibt grün; Review-Punkt für den Adversary
    (kein neuer Dateiinhalt-Test).

- **AC-10:** Given ein Trip mit mindestens drei Etappen im Desktop-Strip auf einem Gerät mit
  Touch-Bedienung (Playwright-Kontext `hasTouch: true`, Desktop-Breite, z. B. Tablet quer oder
  Touch-Laptop) / When der Nutzer eine Etappenkarte per Fingergeste (Touch-Ereignisse über das
  Chrome-DevTools-Protokoll: touchStart, mehrere touchMove, touchEnd) auf eine andere Position
  zieht / Then wird die Reihenfolge der Etappen geändert und gespeichert, genau wie beim
  Maus-Ziehen (AC-1: nur beim Ablegen gemeldet), und die Seite scrollt dabei nicht statt zu
  ziehen. Scheitert die Geste, ist das ein Befund dieses Tickets (Behebung hier, kein
  Ausnahme-Antrag).
  - Test: E2E-Spec mit Touch-Kontext (neu, Helfer `dragDndZoneItemTouch` in
    `frontend/e2e/helpers.ts`, gleiche zustandsbasierte Wartestrategie auf `finalize` wie
    `dragDndZoneItem`, #1771). Der Test MUSS echte Touch-Ereignisse senden, keine Mausereignisse.

## Geplante Tests (AC → Test)

| AC | Test |
|----|------|
| AC-1 | E2E `issue-498-stage-date-autosave.spec.ts` (Zwischenstationen-Test #1393 R2-F002 neu, `dragDndZoneItem`) |
| AC-2 | `no_native_draggable_guard.test.ts` (`# doc-compliance-test`) |
| AC-3 | Komponenten-/E2E-Test Pause-Lücke + `+ Etappe` |
| AC-4 | E2E Drag quer über Lücken |
| AC-5 | E2E-Specs Z. ~1383-1555 umgestellt; `waypoints-editor.spec.ts` |
| AC-6 | Komponententest `SortableList` Richtung; bestehende Orte-/Metriken-Specs |
| AC-7 | Playwright-Tastaturtest |
| AC-8 | E2E Autoscroll |
| AC-9 | `test_adr_index_drift.py` + Review |
| AC-10 | E2E Touch-Geste (`hasTouch`, CDP-Touch-Ereignisse), Helfer `dragDndZoneItemTouch` |

Echte Verhaltenstests, kein Mock-Theater. `issue_585_waypoint_editor_jsx.test.ts` (Dateiinhalt) wird
nur mitgezogen, wenn sich Texte/Maße ändern.

## Mutations-Hinweise (für den Adversary, per String-Ersetzung mit Sicherungskopie)

- Reorder bei `consider` statt `finalize` feuern lassen (z. B. `onDndReorder` im
  consider-Handler aufrufen) → AC-1 muss rot werden (Zwischenstand sichtbar / Rückfrage mitten in
  der Geste).
- `+ Pause`-Bedingung auf `i < stages.length` ändern → AC-3 muss rot werden (Lücke nach letzter
  Etappe).
- Pause-Lücke als Sibling außerhalb des Item-Snippets rendern → AC-3 muss rot werden (Lücke wird
  von `dndzone` entfernt).
- `draggable={true}` in `EtappenStrip.svelte` wieder einfügen → AC-2 muss rot werden.
- `direction`-Default auf `'horizontal'` setzen → AC-6 muss rot werden.
- Touch-Ereignisse im Helfer durch Mausereignisse ersetzen bzw. `touch-action` am Griff/an der Karte so setzen, dass der Browser scrollt statt zieht → AC-10 muss rot werden.
- `pointer-events:none` bei `locked` entfernen → AC-5 muss rot werden.
- Frage je Mutation: Ist die Zusicherung dort geprüft, wo sie WIRKT (Browser-Geste), nicht nur im
  Quelltext?

## Risiken

- Pointer-DnD statt HTML5: alle nativen `dragTo`-E2E-Tests brechen planmäßig (siehe Source).
- Autoscroll bei `overflow-x:auto` ist nicht gesichert (AC-8 misst es); Touch-Ziehen (AC-10) ebenso — beides wird gemessen, nicht angenommen.
- Die Hover-Breitenanimation verschiebt Items während des Ziehens (AC-4).
- `dndzone` entfernt Nicht-Item-Kinder: jede Lücke/jeder Knopf in der Zone wäre ein Defekt.
- Strukturtests lesen `GroupSection.svelte`: beim Löschen müssen alle vier Testdateien angepasst
  werden, sonst bricht die CI (E-1).

## Known Limitations

- Keine bekannten Einschränkungen zu `draggable=` (GroupSection ist gelöscht).

## Out of Scope

- Mobil-Zweig der Etappenliste (nutzt `SortableList` bereits).
- Visuelles Redesign des Strips, Änderung der Kaskaden-Logik.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0024 (Anpassung, kein neues ADR)
- **Rationale:** Die dort dokumentierte Strip-Ausnahme entfällt, weil der Non-Item-Kinder-Konflikt
  gelöst wird; die Entscheidung „ein Sortier-Baustein" wird dadurch vollständig, nicht revidiert.

## Changelog

- 2026-10-06: Initial spec created (#2288, Epic #2345 Etappe P2)
- 2026-10-07: Abweichungen bei der Umsetzung nachgetragen (Adversary Runde 2, R2-F1), siehe unten.

## Abweichungen bei der Umsetzung

Bei der Umsetzung (GREEN + Adversary) ergaben sich Abweichungen von den obigen Annahmen. Sie sind
gemessen (lokaler E2E-Stack), die ACs bleiben unverändert gültig:

1. **Speichern beim Ablegen:** `EditStagesPanelNew.handleReorderEnd` speichert die Reihenfolge jetzt
   beim Ablegen (vorher gab es keinen Autosave-Aufruf, `handleStagesReorder` setzte nur den Zustand).
   Bei offener Kaskaden-Rückfrage wird wie beim Löschen aufgeschoben (`deferSave`); ein
   `cascadeBusy`-Riegel gilt wie in `handleStagesReorder`. Wirkt auch auf die mobile Etappenliste.
   Der Abschnitt „Source" (EditStagesPanelNew: „Logik unverändert") ist damit überholt.
2. **`flipDurationMs={0}` am Strip:** `svelte-dnd-action` tastet die Zeigerposition nur alle
   `flipDurationMs*1,07` ab; bei 200 ms übersprangen schnelle Gesten Stationen. Folge: Nachbarkarten
   springen ohne Gleiten um.
3. **128-px-Polster rechts an der Zone:** Der „+ Etappe"-Knopf liegt absolut darüber; ohne Polster
   wurde ein Ablegen am rechten Rand als `droppedOutsideOfAny` verworfen (AC-8).
4. **Platzhalter-Zeile:** In der horizontalen Zone rendert `SortableList` den Platzhalter der
   Bibliothek mit derselben Zeile wie das gezogene Element (sonst 0 px breit, Karte springt eine
   Position zu weit).
5. **Tastatur-Vertrag des Bausteins:** Die Bibliothek meldet nach jedem Pfeilschritt `finalize`.
   `SortableList` puffert das bei eigener Tastatur-Geste und meldet erst beim Ablegen genau einmal
   (Escape: nichts, Fokusverlust: nach 150 ms melden, Griffwechsel: Rest melden). Dokumentiert in
   ADR-0024.
6. **`SortableList` Initialisierung:** `dndItems` wird per `untrack` aus `items` initialisiert
   (sonst blieb der SSR-Render leer).
