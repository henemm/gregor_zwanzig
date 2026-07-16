---
entity_id: issue_1272_shared_sortable
type: module
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
workflow: refactor-1272-drag-sort
tags: [frontend, svelte, dnd, drag-and-drop, shared-component, layout-editor, bucket-section, compare, issue-1272, issue-433, issue-848]
---

# Issue #1272 — Geteilter Sortier-Baustein (Drag-to-Sort überall)

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-07-16, inklusive der Known Limitations
      (Beta-Accessibility, sichtbarer Griff in BucketSection als optische Änderung,
      Live-Reorder statt Reorder-beim-Loslassen in WeatherV2Reihenfolge, möglicher
      CSS-Paritäts-Verlust, Pflicht-Umschreiben von `layout-tab-route.spec.ts`).

## Purpose

Die Reihenfolge von Metriken und Orten wird an vier Stellen im Frontend per Ziehen
festgelegt oder festgelegt werden soll — bisher mit vier verschiedenen, teils
duplizierten Implementierungen (zwei davon per Hand mit dem HTML5-Drag-API gebaut,
zwei mit `svelte-dnd-action`, aber ohne gemeinsamen Vertrag). Der SMS-Zweig des
Layout-Editors hat bislang **kein** Ziehen, nur ▲/▼-Buttons, obwohl die
Standard-Ansicht daneben längst ziehbar ist. Dieses Modul führt einen einzigen
geteilten Baustein (`SortableList` + `DragHandle`) ein, der alle vier Flächen
bedient — inklusive eines eingebauten Tastatur-Sortier-Pfads, der die bisherigen
▲/▼-Buttons als Barrierefreiheits-Ersatz ablöst.

## Source

- **Schicht:** Reines Frontend (SvelteKit). Kein Go-Backend, kein Python-Backend.
- **Neue Dateien:**
  - `frontend/src/lib/components/shared/dnd/SortableList.svelte`
  - `frontend/src/lib/components/shared/dnd/DragHandle.svelte`
- **Geänderte Dateien:** siehe „Scope" unten.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `svelte-dnd-action` v0.9.69 — `frontend/node_modules/svelte-dnd-action` | npm-Library (bereits installiert, `frontend/package.json:38`) | `dndzone` (`src/index.js:1`) — liefert eingebauten Tastatur-Sortier-Pfad inkl. Screenreader-Ansagen über `keyboardAction.js:324` (Listener sitzt am Item, nicht an der Zone). **Korrektur 2026-07-16:** die `dragHandleZone`/`dragHandle`-Wrapper werden NICHT verwendet — sie setzen `dragDisabled` initial auf `true` (`withDragHandles.js:5,10`) und töten damit das Ziehen an der Zeile, was AC-1 und den Bestandstest zu AC-3 bricht. Siehe ADR-0024 Changelog. |
| `flip` — `svelte/animate` | Svelte-Built-in | CSS-FLIP-Animation beim Umsortieren, `flipDurationMs: 200` (Konsistenz mit bestehenden `dndzone`-Nutzungen) |
| `frontend/src/lib/components/trip-detail/BucketSection.svelte` | Svelte-Komponente (geändert) | Fläche 1: bereits `svelte-dnd-action`-basiert (Issue #433), wird auf `SortableList` umgestellt, bekommt zusätzlich einen sichtbaren Griff |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Svelte-Komponente (geändert) | Fläche 2: Orte-Liste, bereits `svelte-dnd-action`-basiert, schreibt über `persistPickedIds` in die PUT-Queue |
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | Svelte-Komponente (geändert) | Fläche 3: bisher handverdrahtetes HTML5-Drag-API (Issue #848), wird auf `SortableList` migriert — größter Technikwechsel |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | Svelte-Komponente (geändert) | Fläche 4 (NEU): SMS-Zweig bekommt Ziehen, hatte bisher nur ▲/▼ |
| `frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte` | Svelte-Komponente (geändert) | ▲/▼-Buttons + `isFirst`/`isLast`/`onReorder`-Props entfallen |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Svelte-Komponente (geändert) | Consumer von `WeatherV2Reihenfolge`; `(fromId,toId)`-splice-Logik wird durch direkte `newOrder`-Übernahme ersetzt |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Svelte-Komponente (unverändert, nur Konsument) | Einziger Konsument von `OutputLayoutEditor` — Vertrag (`onDndReorder`) bleibt kompatibel |
| `frontend/src/lib/components/shared/layout-tab/LTCutLine.svelte` | Svelte-Komponente (unverändert, Referenz-Präzedenz) | Vorbild für die Extraktion eines geteilten Primitivs aus dupliziertem Markup (Issue #1232, Scheibe 3b) |
| `docs/specs/modules/issue_433_layout_dnd.md` | Spec (ersetzt in Teilen) | AC-3 (▲/▼ bleiben) und AC-4 (SMS ohne DnD) werden durch diese Spec ungültig — s. „Ersetzt/Widerspricht" |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/dnd/SortableList.svelte` | CREATE | Geteilter Baustein: `$state`-Spiegel + `$effect`-Sync gegen `items`-Prop, `dndzone`, `onconsider`/`onfinalize`, Flip-Wrapper-`div` je Zeile, `aria-label`. Vertrag: `items: string[]`, `onDndReorder: (newOrder: string[]) => void`, Snippet-Prop für Zeileninhalt (inkl. bedingtes Markup wie Divider/Cut-Line innerhalb des Item-Wrappers). |
| `frontend/src/lib/components/shared/dnd/DragHandle.svelte` | CREATE | Griff-Atom, vereinheitlichtes Punkt-SVG (`aria-hidden` am Icon). **Muss ein `<span role="button">` sein, kein `<button>`** — `keyboardAction.js:178` verwirft Space/Enter bei Elementen mit `disabled`-Eigenschaft und würde den Tastatur-Pfad still abschalten. Siehe ADR-0024 Changelog. |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte:112-188` | MODIFY | SMS-Zweig: ▲/▼-Buttons raus, `SortableList` rein. Testids `sms-row-{id}`, `sms-budget-display` bleiben erhalten. |
| `frontend/src/lib/components/trip-detail/BucketSection.svelte:41-111` | MODIFY | Bestehender `dndzone`-Block → `SortableList`. Telegram-Divider wandert als bedingtes Markup in den Item-Wrapper (Escape-Hatch). Testids `bucket-section-{bucket}`, `telegram-divider` bleiben erhalten. Bekommt zusätzlich einen sichtbaren `DragHandle` (bisher zog die ganze Zeile). |
| `frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte:81-99` | MODIFY | ▲/▼-Buttons (`metric-up-{id}`/`metric-down-{id}`) sowie `isFirst`/`isLast`/`onReorder`-Props entfallen ersatzlos. |
| `frontend/src/lib/components/compare/CompareTabs.svelte:208-221,1001-1011` | MODIFY | Inline-`dndzone`-Nutzung → `SortableList`. Testid `hub-orte-row` + `data-loc-id` sowie der bestehende PUT-Persistenz-Vertrag bleiben erhalten. |
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | MODIFY | Größtes Risiko: handverdrahtetes HTML5-Drag-API → `SortableList`. Cut-Line (`wm2-cut-line`) wandert in den Item-Wrapper. Testids `wm2-reihenfolge-row` + `data-metric-id` bleiben erhalten. Vertrag ändert sich von `onDndReorder(fromId, toId)` auf `onDndReorder(newOrder: string[])`. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte:395-406` | MODIFY | `(fromId,toId)`-splice/indexOf-Logik entfällt, Handler übernimmt `newOrder` direkt (Code wird kürzer). |
| `frontend/e2e/layout-tab-route.spec.ts:153-216` | MODIFY | Zeile 160 nutzt Playwrights natives `dragTo()` (HTML5-`DataTransfer`) — bricht garantiert, da `dndzone` nur auf Pointer-Events reagiert. Umschreiben auf das bestehende Pointer-Muster `dragDndZoneItem` (`frontend/e2e/compare-hub-inline-edit.spec.ts:22-38`). |
| `frontend/e2e/` (neue Datei, SMS-Reorder + Tastatur-Pfad) | CREATE | Für den SMS-Zweig existiert bisher kein Drag-Test (war bewusst ziehen-frei laut Alt-Spec #433 AC-4). Zusätzlich mindestens ein Tastatur-Sortier-Test (Tab → Space → Pfeiltaste → Space). |

### Estimated Changes

- Files: 10 (2 CREATE Source, 6 MODIFY Source, 2 E2E)
- LoC: netto +130…+230, Churn geschätzt 350–450 (LoC-Override auf 500 vom PO im Intake mitgetragen, vor Phase 6 zu setzen)

## Implementation Details

### Vertrag

`onDndReorder(newOrder: string[])`, gefeuert **ausschließlich bei `finalize`** (nicht
während `consider`). Alle vier Flächen sprechen künftig diesen einen Vertrag —
bisher gab es vier verschiedene Formen (`(newOrder: string[])` in `BucketSection`,
`(fromId, toId)` in `WeatherV2Reihenfolge`, dazu abweichende Muster in
`EtappenStrip`/`GroupSection`, die beide nicht migriert werden, s. „Out of Scope").

### Komponente statt Action

`SortableList` ist eine Wrapper-Komponente (Snippet-basiert), keine reine
`use:`-Action. Begründung: Eine Action kann den nötigen `$effect`-Spiegel
(lokaler `$state`-Array, der während der `dndzone`-consider-Phase mit einem
Phantom-Placeholder mutiert wird) nicht kapseln, weil sie an einem bereits
gerenderten Knoten hängt und kein eigenes `{#each}` mit
`<div animate:flip>`-Wrappern rendern kann — `animate:flip` funktioniert nur auf
nativen Elementen, nicht auf Komponenten (Svelte-Constraint, bereits in
Issue #433 dokumentiert). Der Extraktionsgewinn (State-Sync, consider/finalize,
Flip-Wrapper) liegt genau in diesem Render-Loop, der deshalb im Baustein selbst
liegen muss.

### Pflicht-Fähigkeit: bedingtes Markup im Item-Wrapper

`dndzone` erlaubt keine Nicht-Item-Kinder in der Zone. Telegram-Divider
(bisher `BucketSection.svelte:85-89`) und Cut-Line (bisher
`WeatherV2Reihenfolge.svelte:47-51`) müssen deshalb als bedingtes Markup
**innerhalb** des Item-Wrappers gerendert werden, nicht als Sibling der Zeile.
`SortableList` muss das über seine Snippet-Schnittstelle ermöglichen.

### Umsetzungsreihenfolge (aus Analyse übernommen)

1. `SortableList` + SMS-Zweig als Pilot (kein Vorcode, kein Divider, kein
   brechender Bestandstest) — hier wird auch der Tastatur-Pfad erstverifiziert.
2. `BucketSection` — etabliert Divider-Escape-Hatch + sichtbares Handle.
3. Compare-Orte in `CompareTabs` — schärfste E2E-Kante (Persistenz nach Reload).
4. `WeatherV2Reihenfolge` zuletzt — einziger echter Technikwechsel (HTML5 →
   dndzone), findet den Baustein ausgereift vor.

## Ersetzt/Widerspricht

Diese Spec ersetzt Teile von `docs/specs/modules/issue_433_layout_dnd.md`:

- **AC-3** („die ▲▼-Buttons sind weiterhin funktional und unverändert") wird
  **ungültig**. Ersatz ist nicht „nichts", sondern der eingebaute
  Tastatur-Sortier-Pfad der Bibliothek (Tab auf Griff → Space/Enter startet
  Drag-Modus → Pfeiltasten verschieben → Space/Enter/Escape beendet,
  Screenreader-Ansagen automatisch) — verifiziert in
  `frontend/node_modules/svelte-dnd-action/README.md:170-176` und
  `frontend/node_modules/svelte-dnd-action/src/wrappers/withDragHandles.js:92-126`.
- **AC-4** („kein DnD im SMS-Branch") wird **ungültig**. Der SMS-Zweig bekommt
  Ziehen wie die anderen Flächen.
- **AC-1/AC-2/AC-5/AC-9/AC-10** (Maus-Drag, Touch-Drag, kein Cross-Bucket-Drag,
  FLIP-Animation, Consumer-Übernahme) bleiben inhaltlich **gültig** — sie werden
  hier für `SortableList` neu formuliert (s. „Acceptance Criteria").
- **AC-6/AC-7/AC-8** (`$effect`-Spiegel, `newOrder`-Form, Divider-Index) sind
  Implementierungsdetails, keine ACs mehr — s. „Implementation Details" oben.

## Acceptance Criteria

**AC-1:** Given der Nutzer ist im Layout-Tab des Orts-Vergleich-Editors auf dem SMS-Kanal (`OutputLayoutEditor` wird ausschließlich von `CompareEditor.svelte:917` konsumiert — der Trip-Editor hat mit `WeatherV2Reihenfolge` seine eigene Fläche) / When er eine Metrik-Zeile mit der Maus an eine andere Position zieht und loslässt / Then steht sie an der neuen Position, ohne dass ▲/▼-Buttons benutzt werden mussten, und ohne Seiten-Reload.
  - Test: Playwright-Pointer-Drag im SMS-Zweig, Prüfung der resultierenden Reihenfolge über `sms-row-{id}`-Reihenfolge im DOM.

**AC-2:** Given eine Bucket-Liste (Spalten oder Detail-Werte) im Trip- oder Compare-Editor hat mindestens zwei Metriken / When der Nutzer eine Zeile am Griff greift und per Maus oder Touch an eine andere Position zieht / Then zeigt die Liste nach dem Loslassen die neue Reihenfolge, und die Änderung bleibt beim erneuten Öffnen des Tabs sichtbar.
  - Test: Playwright-Pointer-Drag über `bucket-section-{bucket}`, danach Tab-Wechsel und zurück, Reihenfolge erneut prüfen.

**AC-3:** Given der Nutzer plant im Orts-Vergleich-Editor die Reihenfolge der verglichenen Orte / When er eine Orts-Zeile per Maus zieht und loslässt / Then übernimmt die App die neue Reihenfolge sofort in der Ansicht UND nach einem vollständigen Neuladen der Seite bleibt sie erhalten.
  - Test: Playwright-Pointer-Drag über `hub-orte-row` + `data-loc-id`, danach `page.reload()`, Reihenfolge erneut per DOM-Order prüfen (bestehendes Muster `frontend/e2e/compare-hub-inline-edit.spec.ts:116-137,178-182`).

**AC-4:** Given der Nutzer möchte die Reihenfolge der Wetter-Metriken in der Trip-Detail-Ansicht ändern, hat aber keine Maus (z.B. reine Tastaturbedienung) / When er mit Tab zum Sortier-Griff einer Zeile navigiert, mit Leertaste den Sortier-Modus startet, mit den Pfeiltasten die Zeile verschiebt und mit Leertaste bestätigt / Then landet die Zeile an der neuen Position, ohne dass Maus oder Touch nötig waren.
  - Test: Playwright-Tastatur-Interaktion (Tab, Space, ArrowDown/ArrowUp, Space) auf `wm2-reihenfolge-row`, resultierende Reihenfolge prüfen.

**AC-5:** Given eine der vier Sortier-Flächen (SMS-Liste, Bucket-Sektion, Orts-Vergleich-Liste, Wetter-Metriken-Reihenfolge) wird angezeigt / When der Nutzer nach ▲- oder ▼-Schaltflächen zum Sortieren sucht / Then findet er keine mehr — die einzige Sortier-Interaktion ist Ziehen (Maus/Touch) oder der Tastatur-Pfad des Griffs.
  - Test: Playwright-Query auf die alten Testids `metric-up-{id}`/`metric-down-{id}` in allen vier Flächen erwartet null Treffer.

**AC-6:** Given der Nutzer sortiert Metriken im Trip-Editor auf dem Telegram-Kanal, deren Anzahl das Telegram-Spaltenlimit überschreitet / When er Metriken so zieht, dass sich die Position relativ zur Limit-Grenze ändert / Then erscheint der Telegram-Trenner (Bucket-Sektion) bzw. die Telegram-Schnittlinie (Wetter-Metriken-Reihenfolge) weiterhin genau an der richtigen Position in der neuen Reihenfolge.
  - Test: Metriken über die Limit-Grenze hinweg ziehen, `telegram-divider` bzw. `wm2-cut-line` per DOM-Position relativ zu den umgebenden Zeilen prüfen.

**AC-7:** Given zwei Bucket-Sektionen (Spalten und Detail-Werte) sind im Trip-Editor gleichzeitig sichtbar / When der Nutzer versucht, eine Metrik-Zeile aus der einen Sektion per Ziehen in die andere Sektion abzulegen / Then verweigert die App das Ablegen dort — die Metrik bleibt in ihrer ursprünglichen Sektion, ein Wechsel der Sektion ist weiterhin nur über den bestehenden Verschieben-Button-Pfad möglich.
  - Test: Pointer-Drag von einer `bucket-section-primary`-Zeile über `bucket-section-secondary` und Loslassen dort; Zeile bleibt in `primary`.

## Known Limitations

- `svelte-dnd-action` markiert seinen Accessibility-/Tastatur-Support selbst als
  „(beta)" — kein voll ausgereifter ARIA-DnD-Standard, aber funktionsfähiger
  Tastatur-Pfad (verifiziert, s. „Ersetzt/Widerspricht").
- `BucketSection` zieht heute die gesamte Zeile als Drag-Quelle (kein Griff).
  Der Baustein verlangt einen fokussierbaren Griff für den Tastatur-Pfad — das
  ist eine sichtbare optische Änderung an dieser Fläche, nicht nur eine
  Code-Verschiebung.
- `WeatherV2Reihenfolge` reordert künftig live während des Ziehens
  (consider-Phase, wie `BucketSection`/Compare-Orte es heute schon tun) statt
  erst beim Loslassen wie im bisherigen `ondrop`-Handler (Issue #848-Verhalten).
- `WeatherV2Reihenfolge` hat aktuell handgebaute CSS-Klassen `drag-over`/
  `dragging` für Zwischenzustände. `dndzone` verwaltet Placeholder/Shadow
  selbst; exakte optische Parität ist nur über `dropTargetClasses`/
  `transformDraggedElement` nachbaubar und wird als akzeptierte visuelle
  Abweichung behandelt, falls nicht 1:1 erreichbar (PO/Design bereits
  informiert, s. Kontext-Dokument Risiko 12).
- `frontend/e2e/layout-tab-route.spec.ts:160` bricht mit dieser Änderung
  garantiert (natives `dragTo()` vs. Pointer-Events von `dndzone`). Das
  Umschreiben auf das Pointer-Muster `dragDndZoneItem`
  (`frontend/e2e/compare-hub-inline-edit.spec.ts:22-38`) ist Pflichtarbeit
  dieser Spec, nicht optional.

## Out of Scope

- **`frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte`** —
  bleibt bei ihrer bestehenden HTML5-Drag-Implementierung. Dokumentierter
  Technik-Konflikt (`EtappenStrip.svelte:4-6`): `dndzone` entfernt Nicht-Item-
  Kinder (Pause-Lücken, „+ Etappe"-Button) aus dem DOM, weil sie nicht Teil der
  Zonen-Item-Liste sind. Eine Migration auf `SortableList` würde verlangen,
  diese Kinder aus der Zone herauszunehmen — ein eigenständiger Umbau, nicht
  Teil dieser Spec.
- **`frontend/src/lib/components/compare/GroupSection.svelte`** — bleibt
  unverändert. Kein `<GroupSection`-Vorkommen in irgendeiner konsumierenden
  `.svelte`-Datei gefunden; nur ein Quelltext-Regex-Test
  (`compare/__tests__/issue_453_locations_rail.test.ts:19-39`) referenziert sie
  noch. Mutmaßlich toter Code — Migration eines toten Bausteins wäre
  verschwendete Arbeit und verdeckt den eigentlichen Befund. Ursache verifiziert:
  ihr einziger Konsument `LocationsRail.svelte` wurde in #1256 Scheibe 1 als
  Totcode gelöscht, `GroupSection` stand nicht auf der Löschliste jener Scheibe
  (Beleg: `compare/__tests__/issue_453_locations_rail.test.ts:6-12`). **Bereits
  an Issue #1206 gemeldet** (toter Compare-Code, Kommentar vom 2026-07-16) —
  nicht hier mit-repariert.
- **Cross-Bucket-Drag** (Spalten ↔ Detail-Werte per Ziehen) bleibt weiterhin
  nicht möglich — unverändert dem bestehenden Verschieben-Button-Pfad
  vorbehalten (`dropFromOthersDisabled: true`).
- **Design-Konflikt Trip vs. Compare (Griff mit/ohne ▲▼ im JSX):** PO-Entscheid
  E2 — Issue #848 gilt als maßgeblich, das JSX an der Trip-Stelle
  (`screen-trip-edit-v2-weather.jsx:164-165`, `WM2_Arrow`) wird als stale
  eingestuft. Trip bleibt griff-only wie Compare. Nachzieh-Hinweis **liegt bereits**:
  `docs/design-requests/issue_1272_sortier_bedienung.md` (nicht Teil dieser
  Implementierung, kein Blocker).
- **Griff auf Mobil:** `layout-tab.jsx:111` zeigt den Griff nur bei `!dense` — auf
  Mobil also gar keinen. Da ohne Griff dort keinerlei Sortierung möglich wäre,
  wird der Griff auch im dichten Modus gerendert. Rückfrage an das Design läuft
  (s. Design-Request oben); Antwort ist kein Blocker für diese Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0024
- **Rationale:** Vier Flächen mit vier unterschiedlichen Sortier-Verträgen
  (`(newOrder: string[])`, `(fromId, toId)`, plus zwei handverdrahtete
  HTML5-Varianten) sind ein Verstoß gegen die Trip/Compare-Teilungs-Invariante
  und erschweren jede künftige Sortier-Änderung um den Faktor vier. Die
  Entscheidung, einen Snippet-basierten Wrapper-Komponenten-Baustein statt einer
  reinen `use:`-Action zu bauen, ist architektonisch relevant genug (Render-Loop-
  Kapselung, `$effect`-Spiegel-Zwang, Ablösung eines etablierten
  Barrierefreiheits-Musters durch ein bibliotheks-eigenes) für eine eigene ADR.
  Details der Abwägung (Action vs. Komponente, Vertragswahl `newOrder: string[]`)
  siehe ADR-0024-Datei.

## Changelog

- 2026-07-16: Initial spec erstellt für Issue #1272 (geteilter Sortier-Baustein).
  Ersetzt AC-3/AC-4 aus `docs/specs/modules/issue_433_layout_dnd.md`. Umfang laut
  PO-Entscheidungen E1-E4 aus `docs/context/refactor-1272-drag-sort.md`.
