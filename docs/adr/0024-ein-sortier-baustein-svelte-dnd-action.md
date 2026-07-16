# ADR-0024: Ein geteilter Sortier-Baustein auf svelte-dnd-action; Pfeil-Buttons weichen dem eingebauten Tastatur-Pfad

- **Status:** Akzeptiert (PO-Freigabe „go" am 2026-07-16)
- **Datum:** 2026-07-16
- **Bezug:** GitHub-Issue #1272 (aus Prod-Audit 2026-07-16, Befund 7), Spec
  `docs/specs/modules/issue_1272_shared_sortable.md`, Kontext
  `docs/context/refactor-1272-drag-sort.md`. Löst Teile von
  `docs/specs/modules/issue_433_layout_dnd.md` ab (dort AC-3 und AC-4).

## Kontext

Das Umsortieren von Listen ist im Frontend fünfmal unabhängig gebaut worden, mit zwei
verschiedenen Techniken und vier verschiedenen Verträgen für dieselbe Operation:

| Fläche | Technik | Vertrag nach außen |
|---|---|---|
| `trip-detail/BucketSection.svelte` | `svelte-dnd-action` | `onDndReorder(newOrder: string[])` |
| `compare/CompareTabs.svelte` (Orte) | `svelte-dnd-action` | keiner — persistiert selbst via PUT-Queue |
| `trip-detail/WeatherV2Reihenfolge.svelte` | HTML5 Drag API | `onDndReorder(fromId, toId)` |
| `waypoints/EtappenStrip.svelte` | HTML5 Drag API | `onStagesReorder(stages: Stage[])` |
| `compare/GroupSection.svelte` | HTML5 Drag API | `onDragStart(id)` / `onDrop(targetId)` |

`onDndReorder` heißt dabei zweimal gleich und bedeutet Verschiedenes. Der heikelste Teil —
ein `$state`-Spiegel, der per `$effect` (nicht `$derived`) mit der Quelle synchronisiert
wird, weil `dndzone` die Liste während der consider-Phase mit einem Phantom-Platzhalter
mutiert — ist bereits von `BucketSection.svelte:41-58` nach `CompareTabs.svelte:208-212`
kopiert worden, samt Warnkommentar. Eine dritte Kopie stünde an.

Nutzerseitig fällt das als Bedien-Bruch auf (Issue #1272): die SMS-Liste im Layout-Tab
(`shared/OutputLayoutEditor.svelte:139-176`) lässt sich als einzige Fläche **gar nicht**
ziehen — nur ▲/▼. In den Blöcken daneben stehen ▲/▼ und Ziehen doppelt nebeneinander.

Die Alt-Spec #433 hatte die ▲/▼ bewusst als *barrierefreien Zweitweg* festgeschrieben
(`issue_433_layout_dnd.md:21`, AC-3) und den SMS-Zweig bewusst ziehen-frei gelassen (AC-4),
mit der Begründung, `svelte-dnd-action` habe nur eingeschränkten Tastatur-Support. Diese
Begründung trifft für die installierte Version **nicht mehr zu**: `0.9.69` bringt
vollständigen Tastatur-Support (Space/Enter → Drag-Modus, Pfeiltasten → verschieben,
Escape → abbrechen) samt automatischer Screenreader-Ansagen mit
(`node_modules/svelte-dnd-action/README.md:30,170-176`) und exportiert dafür die fertigen
Wrapper `dragHandleZone`/`dragHandle` (`src/index.js:2`,
`src/wrappers/withDragHandles.js:24-145`).

Rahmenbedingung: Die geschäftsweite Trip/Ortsvergleich-Teilungs-Invariante (CLAUDE.md)
verlangt, dass eine Compare-Komponente mit Trip-Pendant geteilt wird — und für jede
Nicht-Teilung eine dokumentierte Begründung.

## Entscheidung

1. **Es gibt genau einen Sortier-Baustein:**
   `frontend/src/lib/components/shared/dnd/SortableList.svelte`, ergänzt um das Griff-Atom
   `shared/dnd/DragHandle.svelte`. Er kapselt den `$state`-Spiegel, den `$effect`-Sync, die
   Zone-Bindung, consider/finalize und den `animate:flip`-Wrapper je Zeile.
2. **`svelte-dnd-action` ist die einzige zulässige Technik** für neue Sortier-Flächen.
   Handverdrahtete HTML5-Drag-Logik wird nicht mehr neu geschrieben; `WeatherV2Reihenfolge`
   wird auf den Baustein umgestellt.
3. **Der Baustein wird als Komponente gebaut, nicht als `use:`-Action.** Eine Action hängt
   an einem bereits gerenderten Knoten und kann weder den `{#each}`-Loop noch die
   `<div animate:flip>`-Wrapper selbst rendern (`animate:flip` ist nur auf nativen
   Elementen erlaubt). Der Extraktionsgewinn liegt genau im Render-Loop.
4. **Ein Vertrag: `onDndReorder(newOrder: string[])`**, gefeuert ausschließlich bei
   `finalize`. Die Form `(fromId, toId)` entfällt.
5. ~~**Die Zonen werden über `dragHandleZone`/`dragHandle` gebunden**, nicht über nacktes
   `dndzone`.~~ **KORRIGIERT 2026-07-16 (s. Changelog) — sachlich falsch.** Gültig ist:
   **Die Zonen werden über nacktes `dndzone` gebunden; der Griff ist ein eigenes,
   fokussierbares Element (`shared/dnd/DragHandle.svelte`), das kein `<button>` sein darf.**

   Begründung (an der installierten Version verifiziert):
   - `dragHandleZone` setzt `dragDisabled: userDragDisabled.get() || isItemsDragDisabled.get()`
     mit `isItemsDragDisabled` initial `true` (`src/wrappers/withDragHandles.js:5,10`), und
     `pointerAction.js:645` hängt den `mousedown`-Listener nur bei `!dragDisabled` an.
     Ergebnis: Ziehen an der **Zeile** ist tot, nur der Griff zieht. Das bricht AC-1
     (`e2e/sortable-list-shared.spec.ts:147` greift die Zeilenmitte) und — schlimmer —
     den Bestandstest AC-3 (`e2e/compare-hub-inline-edit.spec.ts:120-128`, ebenfalls
     Zeilenmitte), dessen Weiterlaufen die Spec ausdrücklich verlangt.
   - Der Tastatur-Gewinn hängt **nicht** an `dragHandleZone`: `keyboardAction.js:324`
     registriert `keydown` auf dem Item selbst. Space auf dem Griff blubbert zur Zeile
     hoch und startet den Drag; Pfeiltasten wirken danach unverändert.
   - Der Griff muss ein `<span role="button">` sein, **kein `<button>`**:
     `keyboardAction.js:178` verwirft Space/Enter, wenn `e.target.disabled !== undefined` —
     was auf jedes `<button>` zutrifft und den Tastatur-Pfad still abschalten würde.

   Die Acceptance Criteria der Spec bleiben von dieser Korrektur **unberührt** — sie
   beschreiben Verhalten, nicht Mechanismus.
6. **Die ▲/▼-Buttons entfallen ersatzlos als Buttons** — ihre Funktion übernimmt der
   eingebaute Tastatur-Pfad der Bibliothek auf dem fokussierbaren Griff. Damit werden AC-3
   und AC-4 der Spec #433 ungültig; ihre Begründung ist durch die Versionslage entfallen.
7. **Zwei Flächen bleiben bewusst draußen** (Begründungspflicht der Teilungs-Invariante
   erfüllt durch diesen Eintrag):
   - `waypoints/EtappenStrip.svelte` — `svelte-dnd-action` entfernt Nicht-Item-Kinder aus
     der Zone; dort müssen Pause-Lücken und der „+ Etappe"-Knopf zwischen den Items im
     normalen Fluss bleiben (dokumentiert in `EtappenStrip.svelte:4-6`). Eine Übernahme
     setzt voraus, diese Kinder zuvor aus der Zone zu lösen — eigener Umbau, eigenes Ticket.
   - `compare/GroupSection.svelte` — verwaist: kein `<GroupSection`-Vorkommen in irgendeiner
     `.svelte`-Datei, seit ihr einziger Konsument `LocationsRail.svelte` in #1256 Scheibe 1
     als Totcode gelöscht wurde. Gemeldet an #1206. Tote Flächen werden nicht migriert.

## Verworfene Alternativen

- **Nur die SMS-Liste ziehbar machen, Pfeile stehen lassen** — hätte den nutzersichtbaren
  Bruch behoben, aber die doppelte Bedienung und die dritte Kopie des `$effect`-Spiegels
  zementiert. Verstößt gegen das Ticket-Soll („durchgängig") und gegen die
  Teilungs-Invariante.
- **`use:`-Action statt Komponente** — dedupliziert nur Optionen und Event-Wiring, nicht
  State und Render-Loop; der teuerste und fehleranfälligste Teil (der Spiegel) bliebe
  dreifach kopiert. Siehe Entscheidung 3.
- **HTML5 Drag API als gemeinsame Technik** (statt `svelte-dnd-action`) — hätte
  `EtappenStrip` mit abgedeckt, aber Tastatur-Bedienung, Screenreader-Ansagen und
  FLIP-Animation müssten von Hand nachgebaut werden. Genau diese Eigenleistung ist die
  Schuld, die abgetragen werden soll.
- **Pfeil-Buttons als Tastatur-Pfad behalten** (Alt-Spec #433, AC-3) — die Begründung
  („eingeschränkter Keyboard-Support") ist für `0.9.69` faktisch überholt; die Buttons
  wären ein zweiter, testfreier Pfad auf dieselbe Operation.
- **Design-Treue für die Trip-Reihenfolge** (`screen-trip-edit-v2-weather.jsx:164-165` zeigt
  Griff **und** Pfeile) — verworfen per PO-Entscheid 2026-07-16: #848 („Drag & Drop ersetzt
  Pfeiltasten") gilt weiter, das JSX ist an dieser Stelle stale. Nachzieh-Hinweis an das
  Design geht raus.

## Konsequenzen

- **Positiv:** Eine Sortier-Bedienung statt drei; eine Vertragsform statt vier. Der
  `$effect`-Spiegel samt seiner Falle existiert genau einmal und ist einmal testbar.
  Tastatur- und Screenreader-Bedienung entstehen an allen vier Flächen als Nebenprodukt —
  heute hat keine davon ein `aria-label`. Der Konsument von `WeatherV2Reihenfolge`
  (`WeatherMetricsTab.svelte:395-406`) wird kürzer, weil die `splice`/`indexOf`-Rückrechnung
  aus `(fromId, toId)` entfällt.
- **Negativ / Preis:** Die Bibliothek markiert ihren Accessibility-Zweig selbst als
  „(beta)" — wir binden die Barrierefreiheit an fremde Reife. `BucketSection` zieht heute an
  der ganzen Zeile und bekommt einen sichtbaren Griff: optische Änderung, kein reines
  Aufräumen. `WeatherV2Reihenfolge` reordert künftig live während des Ziehens statt erst
  beim Loslassen, und die Eigenbau-Klassen `drag-over`/`dragging` sind nur über
  `dropTargetClasses`/`transformDraggedElement` 1:1 nachbaubar — sonst bleibt eine
  akzeptierte optische Abweichung. `frontend/e2e/layout-tab-route.spec.ts:160` bricht
  garantiert (natives `dragTo` spricht HTML5-DataTransfer, `dndzone` hört auf Pointer-Events)
  und muss auf das Pointer-Muster `dragDndZoneItem`
  (`frontend/e2e/compare-hub-inline-edit.spec.ts:22-38`) umgeschrieben werden.
- **Folgepflichten:**
  - Neue Sortier-Flächen konsumieren `SortableList`. Eine neue handverdrahtete
    Drag-Implementierung ist ein Review-Befund, kein Stilfrage.
  - `EtappenStrip` bleibt die einzige geduldete HTML5-Ausnahme; wird der
    Non-Item-Kinder-Konflikt dort gelöst, ist die Fläche nachzuziehen.
  - Jede Fläche, die `SortableList` konsumiert, setzt `aria-label` auf Zone und Items —
    sonst ist der gewonnene Tastatur-Pfad unbeschriftet.
  - Bedingtes Markup zwischen Zeilen (Telegram-Divider, Cut-Line) gehört **in** den
    Item-Wrapper, nie als Sibling in die Zone — sonst entfernt `dndzone` es aus dem DOM.
  - Der Griff bleibt ein `<span role="button">`. Wird er je zu einem `<button>`, fällt der
    Tastatur-Pfad still aus (`keyboardAction.js:178`) — ohne dass ein Test es merkt, solange
    keiner den Tastatur-Pfad prüft. AC-4 ist genau dieser Test.

## Changelog

- **2026-07-16 (initial):** ADR erstellt und mit der Spec zu #1272 vom PO freigegeben.
- **2026-07-16 (Korrektur Entscheidung 5):** Die Festlegung auf `dragHandleZone`/`dragHandle`
  war sachlich falsch und wurde vor der Umsetzung zurückgenommen. Der Fehler entstand beim
  Verfassen der ADR aus der README-Lektüre („dedizierte Handle-Wrapper vorhanden"), ohne den
  Quelltext der Wrapper zu prüfen. Der Developer-Agent hat den Widerspruch bei der Umsetzung
  gemeldet, statt ihn zu überdecken; die Behauptungen wurden anschließend am Quelltext der
  installierten Version 0.9.69 nachgeprüft und bestätigt
  (`withDragHandles.js:5,10`, `pointerAction.js:645`, `keyboardAction.js:178,324`).
  **Wirkung auf das Produkt: keine** — die ACs beschreiben Verhalten, nicht Mechanismus, und
  bleiben unverändert gültig. Die Korrektur verhindert im Gegenteil einen Bruch von AC-1 und
  des Bestandstests zu AC-3. Lehre: Bibliotheks-Zusagen aus der README gehören vor einer
  Architektur-Festlegung am Quelltext verifiziert.
