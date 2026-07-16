# Context: refactor-1272-drag-sort

Issue: [#1272](https://github.com/henemm/gregor_zwanzig/issues/1272) — „Sortierung vereinheitlichen: drag-to-sort überall (Editor-Layout nutzt noch Pfeil-Buttons)"
Track: Full Process (Intake-Score 5) · Stand: 2026-07-16

## Request Summary

Die Metrik-Sortierung im Layout-Tab des Orts-Vergleich-Editors nutzt ▲/▼-Pfeil-Buttons,
während Trip-Etappen und Compare-Hub-Orte per Ziehen sortiert werden. Ticket-Soll (#1256):
Reihenfolge per Ziehen, durchgängig — über einen **geteilten Baustein**, nicht nachgebaut.
PO-Entscheid Intake 2026-07-16: Umfang = zusätzlich gemeinsamen Baustein bauen.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte:139-176` | **Der eigentliche Befund**: SMS-Zweig = flache Liste, NUR ▲/▼, kein Ziehen. Signaturen Z.51/55. |
| `frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte:81-99` | ▲/▼ je Bucket-Zeile (`metric-up-{id}`/`metric-down-{id}`), Props `isFirst`/`isLast`/`onReorder`. |
| `frontend/src/lib/components/trip-detail/BucketSection.svelte:41-58,79-84` | Fläche 1: `svelte-dnd-action`, `$effect`-Spiegel `dndItems`, kein Handle (ganze Zeile zieht). |
| `frontend/src/lib/components/compare/CompareTabs.svelte:208-221,1001-1011` | Fläche 2: `svelte-dnd-action`, Handle-SVG 16×16, schreibt via `persistPickedIds` → PUT-Queue. |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte:2-6,53-90` | Fläche 3: HTML5 — **dokumentierter Ausschlussgrund**, s. Risiken. |
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte:6,22,57-77` | Fläche 4: HTML5, Handle-SVG 10×14, `onDndReorder(fromId,toId)`. Kommentar Z.6: „#848 — Drag & Drop ersetzt Pfeiltasten." |
| `frontend/src/lib/components/compare/GroupSection.svelte:26-27,86-89` | Fläche 5: HTML5, **kein Svelte-Konsument** — mutmaßlich tot. |
| `frontend/src/lib/components/compare/CompareEditor.svelte:917-930` | Einziger Konsument von `OutputLayoutEditor` (`onReorder`/`onDndReorder`). |
| `claude-code-handoff/current/jsx/layout-tab.jsx:14,104-120` | **Design-Quelle** (kanonisch lt. #1256): Compare-Liste = ⋮⋮-Griff, KEINE Pfeile; Handle nur `!dense`. |
| `claude-code-handoff/current/jsx/screen-trip-edit-v2-weather.jsx:136-184` | Design-Quelle Trip: Griff **UND** ▲/▼ (`WM2_Arrow`) nebeneinander. |
| `docs/specs/modules/issue_433_layout_dnd.md:21,243-249` | Alt-Spec: Pfeile bewusst als barrierefreier Zweitweg; SMS bewusst ohne Ziehen (AC-3/AC-4). |
| `frontend/package.json:38` | `svelte-dnd-action ^0.9.69` bereits installiert. |

## Existing Patterns

- **`svelte-dnd-action` + `$effect`-Spiegel** (BucketSection → CompareTabs kopiert, inkl.
  Warnkommentar „NICHT die abgeleitete Variante"): `dndzone` mutiert die Liste während der
  consider-Phase mit einem Platzhalter, deshalb `$effect` statt `$derived`. **Kern-Kandidat
  für die Extraktion.**
- **HTML5 Drag API** (EtappenStrip, WeatherV2Reihenfolge, GroupSection) — jeweils handverdrahtet.
- **Präzedenzfall Extraktion:** `shared/layout-tab/LTCutLine.svelte` (Issue #1232, Scheibe 3b)
  hat dupliziertes Cut-Line-Markup durch ein geteiltes Primitiv ersetzt. Gleiches Vorgehen,
  gleicher Ablageort.
- **Dekoratives Handle:** beide Handle-SVGs sind `aria-hidden`, gezogen wird die ganze Zeile.

## Dependencies

- **Upstream:** `svelte-dnd-action@^0.9.69`, `svelte/animate` (`flip`).
- **Downstream:** `CompareEditor.svelte` (einziger `OutputLayoutEditor`-Konsument),
  `WeatherMetricsTab.svelte:649` (rendert `WeatherV2Reihenfolge`).
- **E2E-Abdeckung:** `frontend/e2e/compare-hub-inline-edit.spec.ts:116-137,178-182`
  (`hub-orte-row` inkl. Persistenz nach Reload), `frontend/e2e/layout-tab-route.spec.ts`
  + `frontend/e2e/epic-138-metriken-editor.spec.ts:158-162` (`wm2-reihenfolge-row`).
- **Testfrei:** `metric-up-`/`metric-down-` haben **null** Treffer außerhalb der Komponente —
  die ▲/▼-Fläche ist ungeschützt. `drag-handle` ist repo-weit frei.

## Existing Specs

- `docs/specs/modules/issue_433_layout_dnd.md` — *widerspricht #1272 direkt* (s. Risiken).
- `docs/specs/modules/issue_1256_compare_ui_rewire.md` — Ticket-Herkunft; setzt die JSX als
  kanonische Optik-Quelle und die Trip/Compare-Teilungs-Invariante als bindende Prüfgröße.
- Epic #1230 (Briefing-Abo-Chassis) — Heimat des geteilten `LayoutTab`-Organismus.

## Risks & Considerations

1. **Widerspruch zur Alt-Spec #433.** Deren AC-3/AC-4 halten die ▲/▼ als *barrierefreien*
   Zweitweg und den SMS-Zweig bewusst ziehen-frei fest. #1272 kippt beides. Muss in der
   Spec als Ersetzung dokumentiert werden, sonst schweigender Spec-Konflikt.
2. **Barrierefreiheit.** `svelte-dnd-action` hat eingeschränkten Tastatur-Support (#433
   „Out of Scope"). Fallen die Pfeile ersatzlos, gibt es für Tastatur-Nutzer keinen
   Sortier-Weg mehr. Trip hat diesen Schritt mit #848 bereits vollzogen — Präzedenz besteht.
3. **Design widerspricht „überall".** JSX zeigt für Compare Griff-ohne-Pfeile, für Trip
   Griff-**mit**-Pfeilen. Der Code (`WeatherV2Reihenfolge`, #848) weicht hier bereits vom
   JSX ab. Entweder ist das JSX an dieser Stelle stale oder #848 war ein Fidelity-Bruch —
   PO-Entscheidung nötig, da „JSX ist immer die Wahrheit" gilt.
4. **EtappenStrip kann nicht mitziehen.** Dokumentiert in `EtappenStrip.svelte:4-6`:
   HTML5 statt `svelte-dnd-action`, weil letztere Nicht-Item-Kinder (Pause-Lücken,
   „+ Etappe") aus dem DOM entfernt. Ein `dndzone`-basierter Baustein deckt die Fläche nur
   ab, wenn diese Kinder aus der Zone wandern — eigener Umbau, nicht Teil von #1272.
5. **GroupSection ist mutmaßlich tot.** Kein `<GroupSection`-Vorkommen in irgendeiner
   `.svelte`-Datei; nur Quelltext-Regex-Tests
   (`compare/__tests__/issue_453_locations_rail.test.ts:19-39`) halten sie am Leben.
   Vor Migration klären — passt thematisch zu #1206 (toter Compare-Code).
6. **Vier Vertragsformen für eine Operation.** `onDndReorder` heißt zweimal gleich und
   bedeutet Verschiedenes: `(newOrder: string[])` (BucketSection) vs. `(fromId, toId)`
   (WeatherV2Reihenfolge); dazu `(stages: Stage[])` (EtappenStrip) und `onDragStart`/`onDrop`
   (GroupSection). Der Baustein muss einen Vertrag setzen; die Umstellung von
   `WeatherV2Reihenfolge` ist damit ein Verhaltens-Refactor, kein reines Verschieben.
7. **`animate:flip`-Constraint.** Nur auf nativen Elementen, nicht auf Komponenten — ein
   Wrapper-`div` je Zeile bleibt nötig (`issue_433_layout_dnd.md:286`).
8. **LoC.** Realistisch 250–400 → `loc_limit_override` nötig; braucht PO-Erlaubnis.
9. **Regel-Budget.** Rein additive Arbeit, kein neues Gate — Regel-Budget nicht berührt.

## Analysis (Phase 2, 2026-07-16)

### Type

**Feature** (Refactor mit nutzersichtbarer Verhaltensänderung) — kein Bug.

### Schlüssel-Befund: E1 ist fast gratis

`svelte-dnd-action@0.9.69` hat **eingebauten Tastatur-Support** — verifiziert in
`frontend/node_modules/svelte-dnd-action/README.md:30,170-176`: Tab auf Item →
Space/Enter startet Drag-Modus → Pfeiltasten verschieben → Space/Enter/Escape beendet;
Screenreader-Ansagen automatisch (`autoAriaDisabled` schaltet ab). Zusätzlich exportiert
die Bibliothek fertige Handle-Wrapper: `dragHandleZone` + `dragHandle`
(`src/index.js:2`, `src/wrappers/withDragHandles.js:24-145`) — `dragHandle` setzt
`role="button"` + `tabIndex=0` und reagiert auf Enter/Space (Z.92-126).

→ Die Aussage der Alt-Spec #433 („eingeschränkter Keyboard-Support", Out of Scope) ist
für die installierte Version **überholt**. E1 kostet kein Eigenbau-Handling, nur:
`dragHandleZone`/`dragHandle` statt nacktem `dndzone`, `aria-label` ergänzen, ▲/▼ raus.
Einschränkung: Die Bibliothek markiert Accessibility selbst als „(beta)".

### Technischer Ansatz (Empfehlung)

- **Vertrag:** `onDndReorder(newOrder: string[])`, gefeuert **nur bei `finalize`**.
  `BucketSection` (Z.30,57) hat ihn bereits; `CompareTabs` baut intern dieselbe Form.
  `WeatherV2Reihenfolge`s `(fromId, toId)` (Z.22) ist ein Artefakt der HTML5-Handverdrahtung
  — `WeatherMetricsTab.svelte:395-406` rechnet daraus per `splice`/`indexOf` ohnehin wieder
  eine Liste zurück; mit `newOrder` entfällt der Umweg (Code wird **kürzer**).
- **Wrapper-Komponente, keine reine `use:`-Action.** Eine Action kann den `$effect`-Spiegel
  nicht kapseln: sie hängt an einem fertig gerenderten Knoten und kann kein `{#each}` mit
  `<div animate:flip>`-Wrappern selbst rendern (`animate:flip` nur auf nativen Elementen).
  Der Extraktionsgewinn (State + `$effect`-Sync + consider/finalize + Flip-Wrapper) liegt
  genau im Render-Loop. → `shared/dnd/SortableList.svelte` (Snippet-basiert) +
  optionales `shared/dnd/DragHandle.svelte` als dünnes Atom um `use:dragHandle`.
- **Pflicht-Fähigkeit des Bausteins:** bedingtes Markup **innerhalb** des Item-Wrappers
  (Telegram-Divider `BucketSection.svelte:85-89`, Cut-Line `WeatherV2Reihenfolge.svelte:47-51`).
  `dndzone` verbietet Nicht-Item-Kinder in der Zone — die Cut-Line muss deshalb vom Sibling
  **in** den Wrapper wandern.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/shared/dnd/SortableList.svelte` | CREATE | Baustein: `$state`-Spiegel + `$effect`-Sync, `dragHandleZone`, consider/finalize, Flip-Wrapper, `aria-label`. |
| `frontend/src/lib/components/shared/dnd/DragHandle.svelte` | CREATE | Griff-Atom um `use:dragHandle`, Punkt-SVG vereinheitlicht. |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte:139-176` | MODIFY | **Pilot**: SMS-Liste bekommt Ziehen, ▲/▼ raus. Testids `sms-row-{id}`, `sms-budget-display` erhalten. |
| `frontend/src/lib/components/trip-detail/BucketSection.svelte:41-84` | MODIFY | dndzone-Block → `SortableList`. Divider-Escape-Hatch. Testids `bucket-section-{bucket}`, `telegram-divider` erhalten. |
| `frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte:81-99` | MODIFY | ▲/▼ + `isFirst`/`isLast`/`onReorder` raus. |
| `frontend/src/lib/components/compare/CompareTabs.svelte:208-221,1001-1011` | MODIFY | Inline-dndzone → `SortableList`. `hub-orte-row` + `data-loc-id` und PUT-Vertrag erhalten. |
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | MODIFY | **Höchstes Risiko**: HTML5 → dndzone. Cut-Line in den Wrapper. `wm2-reihenfolge-row` + `data-metric-id` erhalten. |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte:395-406` | MODIFY | `(fromId,toId)`-splice-Logik → `list = newOrder`. |
| `frontend/e2e/layout-tab-route.spec.ts:153-216` | MODIFY | **Bricht sicher**: nutzt Playwrights natives `dragTo()` (HTML5-DataTransfer); dndzone hört auf Pointer-Events. Auf Pointer-Simulation umschreiben. |
| `frontend/e2e/` (neu, SMS-Reorder + Tastatur-Pfad) | CREATE | Für SMS existiert kein Drag-Test (war bewusst ziehen-frei). |

### Scope Assessment

- Dateien: **10** (2 CREATE, 6 MODIFY Source, 2 E2E)
- LoC: netto **+130…+230**, Churn **350–450**
- Risiko: **MEDIUM–HIGH** (Risiko-Träger: `WeatherV2Reihenfolge`, E2E-Umschreibung, Persistenz-Kante Compare-Orte)
- LoC-Override **500 reicht**, aber mit wenig Puffer (E4).

### Reihenfolge der Umsetzung

1. **`SortableList` + SMS-Zweig** — Pilot: kein Vorcode, keine Divider-Verschachtelung,
   kein brechender Bestandstest. Hier wird auch der Tastatur-Pfad erstverifiziert.
2. **BucketSection** — schon `dndzone`; etabliert Divider-Escape-Hatch + Handle-Muster.
3. **Compare-Orte** — schon `dndzone`, aber scharfe E2E-Kante (Persistenz nach Reload).
4. **WeatherV2Reihenfolge** — zuletzt: einziger echter Technikwechsel, findet den Baustein
   ausgereift vor statt als Pionierfläche zu dienen.

### Neue Risiken aus der Analyse

10. **`layout-tab-route.spec.ts:160` bricht garantiert.** `source.dragTo(target)` feuert
    natives HTML5-DnD; `dndzone` reagiert nur auf Pointer-Events. Umschreiben auf das
    bereits existierende Pointer-Muster `dragDndZoneItem`
    (`frontend/e2e/compare-hub-inline-edit.spec.ts:22-38`) ist **Pflichtarbeit**.
11. **BucketSection zieht heute die ganze Zeile** (kein Handle). E1 verlangt einen
    fokussierbaren Griff → sichtbare UI-Änderung, nicht nur Code-Verschiebung.
12. **CSS-Parität `WeatherV2Reihenfolge`.** Die Klassen `drag-over`/`dragging`
    (Z.54-56,163-169) sind Eigenbau aus manuellem State. `dndzone` verwaltet
    Placeholder/Shadow selbst — exakte Optik nur über `dropTargetClasses`/
    `transformDraggedElement` nachbaubar. Sonst akzeptierte visuelle Abweichung (PO/Design).
13. **Reorder-Zeitpunkt ändert sich** bei `WeatherV2Reihenfolge`: heute erst beim Loslassen
    (`ondrop`, Z.63-69), künftig Live-Reflow während des Ziehens (consider-Phase) — wie es
    BucketSection/Compare-Orte heute schon tun, aber Abweichung vom #848-Verhalten.

## PO-Entscheidungen (2026-07-16, Intake + Kontext-Phase)

- **E1 (Barrierefreiheit):** Tastatur-Sortierung wandert **in den Baustein** — ▲/▼-Buttons
  entfallen, das Handle wird fokussierbar und per Pfeiltasten bedienbar. Ersetzt AC-3 der
  Alt-Spec #433 (Pfeile als barrierefreier Zweitweg) durch einen gleichwertigen Ersatz.
- **E2 (Design-Konflikt):** **#848 gilt**, das JSX ist an der Trip-Stelle
  (`screen-trip-edit-v2-weather.jsx:164-165`, `WM2_Arrow`) **stale**. Trip bleibt
  griff-only. → Nachzieh-Hinweis in `docs/design-requests/` ablegen.
- **E3 (Umfang):** Baustein für **3 lebende Flächen** (`BucketSection`, Compare-Orte in
  `CompareTabs`, `WeatherV2Reihenfolge`) **+ neue SMS-Liste** im `OutputLayoutEditor`.
  `EtappenStrip` ausgeklammert (Risiko 4, dokumentierter Technik-Constraint),
  `GroupSection` ausgeklammert (Risiko 5, mutmaßlich tot → Sammel-Eintrag/#1206).
  Beide Ausklammerungen sind in der Spec unter „Out of Scope" zu begründen.
- **E4 (LoC):** Override auf 500 vom PO im Intake mitgetragen (Umfang „gemeinsamen
  Baustein bauen" explizit gewählt) — vor Phase 6 setzen.
