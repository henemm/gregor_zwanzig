---
entity_id: fix_2277_s2a_wertebereiche_trip_anlegen
type: bugfix
created: 2026-09-27
updated: 2026-09-27
status: draft
version: "1.0"
tags: [trip-new, wertebereiche, corridor-editor, shared-component]
---

# `/trips/new` bekommt einen Wertebereiche-Reiter (Issue #2277 Scheibe S2a)

## Approval

- [ ] Approved

## Purpose

Scheibe **S2a** von #2277 (Anlege-Strecke-Konvergenz, Epic #2345) ergänzt `/trips/new`
um den Reiter **„Wertebereiche"**, gemountet über den geteilten Organismus
`CorridorEditor.svelte` (`context="route"`, neuer Prop `createMode`) — denselben
Baustein, den der Trip-Hub (`TripTabs.svelte`) und der Ortsvergleich bereits nutzen.
Bisher hat `/trips/new` **keinen** `CorridorEditor`-Mount; Wertebereiche lassen sich
beim Anlegen eines Trips gar nicht setzen. `CorridorEditor.svelte` bekommt dafür das
`createMode`-Muster, das `AlarmeTab.svelte`/`WeatherMetricsTab.svelte` für denselben
Zweck bereits haben (S1, #2426) — der Selbst-Speicher-Pfad (PUT über `saveController`)
wird abgeschaltet, Änderungen fließen stattdessen über den bestehenden Rückruf
`onCorridorsChange` nach oben in `CreateTripState.corridors` und mit dem EINEN
`POST /api/trips` in den neuen Trip.

## Source

- **File (Frontend):**
  `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`,
  `frontend/src/lib/components/trip-new/TripNewEditor.svelte`,
  `frontend/src/lib/components/trip-new/tripNewLogic.ts`,
  `frontend/src/lib/components/trip-new/__tests__/tripNewLogic.test.ts` (erweitert),
  `frontend/src/lib/components/trip-new/__tests__/trip_new_wertebereiche_reiter.test.ts`
  (neu, SSR-Render über `tripNewSsr.ts`),
  `frontend/src/lib/components/shared/corridor-editor/__tests__/corridor_editor_create_mode_route.test.ts`
  (neu, Wirkort-Prüfstand),
  `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`
  (Zeilen nachgeführt, Anzahl bleibt 47),
  `frontend/e2e/trip-new-loads-without-effect-loop.spec.ts` (erweitert um den
  Wertebereiche-Zwischenschritt vor „Zeitplan")
- **Identifier:** `CorridorEditor` (neuer Prop `createMode?: boolean`), Mount (A)
  Desktop `TripNewEditor.svelte` (analog `:897-905` AlarmeTab-Block), Mount (B)
  Mobile `TripNewEditor.svelte` (analog `:1147-1160`), `buildCreateTripPayload()`
  (`tripNewLogic.ts:170`), Signaturänderung `unlockedTabs()`/`doneTabs()`
  (`tripNewLogic.ts:24,38`, neuer Parameter `wbVisited`).

> **Schicht-Hinweis:** ausschließlich **Frontend**
> (`frontend/src/lib/components/`). Kein Go-API-Change nötig — `CreateTripHandler`
> (`internal/handler/trip.go:158-218`) dekodiert den POST-Body bereits direkt in
> `model.Trip`; `Corridors []Corridor \`json:"corridors"\`` (`internal/model/trip.go:123`,
> **kein** `omitempty`) ist ein regulärer, bereits vorhandenes Feld. Kein
> Python-Core-Code betroffen (`src/output/renderers/trip_report.py:247` liest
> `trip.corridors` bereits tolerant gegen leere Listen).

## Nicht in dieser Scheibe

- **`/compare/new`-Angleichung (Reiter-Reihenfolge, Mobile-Rahmen,
  `PageHeader`/`EditorStickyFooter`) — Scheibe S2b.** Diese Spec ändert an
  `CompareNewEditor.svelte`/`CompareTabs.svelte`/`+layout.svelte` nichts.
- **`?from=`-Vorlage (`/trips/new?from=`, `/compare/new?from=`) — Scheibe S2c.**
  Kein UI-Link führt heute auf `/trips/new?from=` (0 Treffer); toter Code, gebucht
  als Nebenbefund in #1199, nicht Gegenstand von S2a.
- **AC-5 des Gesamt-Epics (Aufräumen `AlertRulesEditor`/`EditReportConfigSection`)**
  — beide haben Importeure außerhalb der Anlege-Editoren (`TripEditView.svelte`,
  ~20 Dateien), nicht Gegenstand dieser Scheibe.
- **`CorridorEditorMobile.svelte` wird nicht angefasst und nicht gemountet.**
  Der Trip-Hub (`trip-detail/TripTabs.svelte:229`) mountet für `context="route"`
  **ausschließlich** `CorridorEditor` (Desktop-Komponente) — für Route/Trip gibt es
  keinen Mobile-Varianten-Präzedenzfall. `CorridorEditorMobile` wird bislang
  ausschließlich mit `context="vergleich"` verwendet
  (`CompareNewEditor.svelte:488`). S2a folgt dem Hub-Muster: dieselbe
  `CorridorEditor`-Komponente wird für Desktop UND Mobile gemountet (Muster
  `WeatherMetricsTab`/`AlarmeTab` in `TripNewEditor.svelte`, zwei Mounts, XOR über
  `isMobileViewport`), keine neue Datei, keine Berührung der 11 eigenen
  `context===`-Ratschen-Einträge von `CorridorEditorMobile.svelte`.
- **`progressCount()` (`tripNewLogic.ts`) bekommt keinen neuen Schritt.** Die
  Fortschritts-Segmente bleiben `['route', 'etappen', 'metriken', 'zeitplan']` —
  S1 hat den Reiter „Alerts" ebenfalls nicht in diese Liste aufgenommen; S2a folgt
  demselben, bereits etablierten Präzedenzfall.
- **`CompareTabs.svelte`/`compareWizardState.svelte.ts` (Hub) werden nicht
  verändert.** Die Hub-Korridorspeicherung (`context="vergleich"`, PUT-Pfad) ist
  vom neuen `createMode`-Zweig unberührt (Default `false`, siehe AC-4).
- **Kein neuer Adapter (`trip-new/corridorPropsAus.ts`).**
  `compare/corridorPropsAus.ts:9-14` dokumentiert ausdrücklich „hat bewusst kein
  Trip-Pendant" — der route-Zweig reicht `trip`/`onTripUpdate`/`onCorridorsChange`
  direkt, wie es die bestehende Prop-Schnittstelle von `CorridorEditor.svelte`
  bereits vorsieht.

## Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | MODIFY | Neuer Prop `createMode?: boolean` (Default `false`, Destrukturierung `:70-95`). `maybeSchedule()` (`:284-298`): NEUER `if (createMode) { … return; }`-Zweig ZWISCHEN dem `vergleich`-Zweig (`:285-293`) und dem bestehenden route-PUT (`:295-296`) — bei `saveGateDecision(rows) === 'schedule'` ruft er `onCorridorsChange?.(buildCorridorSavePayload(rows, originalLevels, routeUnknownCorridors).corridors)` statt `saveController?.schedule(...)`; bei `'dirty'` passiert nichts (kein `setDirty()`-Äquivalent im Anlege-Modus nötig, s. Known Limitations). Kein neuer `context`-Vergleich — die HERKUNFT-Ratsche bleibt bei 47 Einträgen, nur Zeilen verschieben sich. **Zweiter, neuer `$effect`** direkt nach dem bestehenden route-Katalog-Lade-Effekt (`:214-232`): gated auf `if (!createMode \|\| routeExtraDefs === null) return;` (KEIN `context`-Vergleich, `createMode` reicht als Gate, da der Effekt nur im route-Zweig überhaupt sinnvoll ist und `createMode` dort per Prop-Vertrag nur gesetzt wird), rechnet `poolLeft` aus dem AKTUELLEN `rows`-Stand (`buildCorridorSavePayload(rows, originalLevels, routeUnknownCorridors).corridors` als `corridors`-Argument, NICHT `trip?.corridors` — der bleibt in createMode immer leer) + `trip?.display_config?.metrics` + `routeExtraDefs` neu über `buildRoutePool(...)`, übernimmt aber nur `.poolLeft` — `rows` bleibt unangetastet (kein Datenverlust an bereits eingestellten Zeilen, s. AC-7). |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | `TabId` bekommt `'wertebereiche'` zwischen `'metriken'` und `'zeitplan'` (`:20`). `unlockedTabs()`/`doneTabs()` (`:24,38`) bekommen einen NEUEN Parameter `wbVisited: boolean` (Position zwischen `wtVisited` und `ztVisited`) — **Breaking Change der Signatur**, s. Test-Update-Pflicht unten. Freischalt-Kette: `wtVisited → 'wertebereiche' unlocked`, `wbVisited → 'zeitplan' unlocked` (statt bisher `wtVisited → 'zeitplan' unlocked`), Rest unverändert. `doneTabs()` ergänzt `if (wbVisited) s.add('wertebereiche')` (Muster Compare `idealwerte`, `compareNewLogic.ts:55`). `canSave`/`progressCount` bleiben unverändert (s. „Nicht in dieser Scheibe"). Neu: `CreateTripState.corridors?: Corridor[]`. `buildCreateTripPayload()` setzt `trip.corridors = state.corridors ?? []` (immer gesetzt, additiv neben den bestehenden Feldern — kein Replace anderer `trip`-Felder). |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | `TAB_DEFS`-Eintrag `{ id: 'wertebereiche', label: 'Wertebereiche', lockHint: 'erst Wetter-Metriken öffnen', optional: false }` zwischen `metriken` und `zeitplan` (`:69-75`); `zeitplan`s `lockHint` ändert von `'erst Wetter-Metriken öffnen'` auf `'erst Wertebereiche öffnen'` (Wortlaut exakt wie Compare, `CompareNewEditor.svelte:100-101`). Neuer State `let wbVisited = $state(false);` (neben `wtVisited`/`ztVisited`, `:111-112`), gesetzt in `switchTab()` analog `:240-241` (`if (id === 'wertebereiche') wbVisited = true;`). Neuer Schatten-State `let corridors = $state<Corridor[]>([]);` und Rückkanal `function handleCorridorsChange(c: Corridor[]) { corridors = [...c]; }` (Muster `handleChannelsChange`, kein Inhaltsgleichheits-Guard nötig, da `corridors` NICHT in `stubTrip` einfließt — keine Effektschleifen-Gefahr, s. Implementation Details Punkt 1). Zwei neue Mounts `<CorridorEditor context="route" trip={stubTrip} createMode={true} onCorridorsChange={handleCorridorsChange} />` — Desktop (analog `:897-905`, `{#if !isMobileViewport}` + `style:display={activeTab === 'wertebereiche' ? '' : 'none'}`) und Mobile (analog `:1147-1160`, `{#if isMobileViewport}`). `buildAndSave()` übergibt `corridors` in `CreateTripState` (`:394-410`). |
| `frontend/src/lib/components/trip-new/__tests__/tripNewLogic.test.ts` | MODIFY | Alle 12 bestehenden Aufrufe von `unlockedTabs(...)`/`doneTabs(...)` (Zeilen 43,48,54,59,66,69,78,85,95,99,124,127) bekommen den neuen `wbVisited`-Parameter (Position 5) — **kein Verhaltensverlust**, reine Signaturanpassung; die bestehenden Assertions bleiben inhaltlich identisch, wenn `wbVisited` gleich dem bisherigen `wtVisited`-Wert gesetzt wird (Kompatibilitäts-Fall) ODER bewusst variiert wird, um die neue Stufe zu prüfen. NEUE Tests: `'wertebereiche' unlocked erst nach wtVisited`, `'zeitplan' unlocked erst nach wbVisited (nicht mehr nach wtVisited allein)`, `doneTabs` markiert `'wertebereiche'` bei `wbVisited`. NEUER Test-Block für `buildCreateTripPayload`: echter Aufruf mit `state.corridors` aus einem simulierten Editor-Rückruf (kein von Hand gebautes Fixture-Array, s. AC-2), Rundreise-Assertion `payload.corridors` enthält exakt die übergebenen Werte; separater Test für „kein `corridors`-Feld in `state`" ⇒ `payload.corridors === []`. |
| `frontend/src/lib/components/trip-new/__tests__/trip_new_wertebereiche_reiter.test.ts` *(neu)* | CREATE | Echtes SSR-Rendering über `tripNewSsr.ts`/`renderTripNew()`: Reiter-Reihenfolge/Label/Sperre (AC-1), Ein-Instanz-Zusicherung über die drei Viewport-/Tab-Kombinationen (AC-5, Muster `trip_new_alarme_reiter.test.ts` AC-6). |
| `frontend/src/lib/components/shared/corridor-editor/__tests__/corridor_editor_create_mode_route.test.ts` *(neu)* | CREATE | Wirkort-Test im Kern über `umgebungFuer()`/`effekteVon()` (`svelteInstanzPruefstand.ts`) gegen `CorridorEditor.svelte` — anders als bei `AlarmeTab` liegt der Guard hier in einer PLAIN FUNCTION (`maybeSchedule()`, kein `$effect`-Rumpf), `umgebungFuer()` bindet Funktionsdeklarationen direkt auf `u` (`svelteInstanzPruefstand.ts:143-152`); Tests rufen `u.add(metric)`/`u.patch(metric, {...})` **direkt** auf, kein Effekt-Sammel-Mechanismus nötig (AC-2/AC-3). Der neue Pool-Refresh-`$effect` (AC-7) läuft dagegen wirklich über `$effect` und wird über `effekteVon(ast, quelle, u, 'poolLeft')` eingesammelt. |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | Die 11 `corridor-editor/CorridorEditor.svelte:*`-Zeilen (aktuell `:141,184,216,285,313,347,360,363,369,390,519`) verschieben sich um die Anzahl neu eingefügter Zeilen oberhalb jedes Fundorts (neuer Prop + neuer `if (createMode)`-Zweig + neuer `$effect`). Zahl bleibt 47, es werden NUR die Zeilennummern nachgeführt — kein neuer Eintrag, keine `BLEIBT_MIT_INHALT`-Fesselung wird inhaltlich verändert. |
| `frontend/e2e/trip-new-loads-without-effect-loop.spec.ts` | MODIFY | Der bestehende Klick-Pfad (`:154` „Zeitplan-Tab besuchen") klickt den Zeitplan-Tab direkt nach dem Wetter-Reiter an. Mit der neuen Sperrkette ist `zeitplan` erst nach Besuch von `wertebereiche` freigeschaltet — ein ungegateter Klick würde am `unlocked.has('zeitplan') === false`-Zweig von `makeMobileTabHandler` abprallen (Toast statt Tab-Wechsel, `TripNewEditor.svelte:377-386`) und den Test rot machen. Fix: VOR dem Zeitplan-Klick den Wertebereiche-Tab antippen (`tabbar.getByRole('tab', { name: /Wertebereiche/ }).click({ force: true })`). Das ist eine **notwendige Testanpassung an die neue, gewollte Sperrkette**, keine Regression. |

## Estimated Scope

- **LoC (produktiv, geschätzt):** ca. +90 / −5 — unter dem 250-LoC-Limit.
  `workflow.py status` ist vor jeder Override-Ankündigung in `/50` die
  maßgebliche Quelle, nicht diese Schätzung.
- **Files:** 3 produktiv (`CorridorEditor.svelte`, `TripNewEditor.svelte`,
  `tripNewLogic.ts`), 4 Testdateien (2 neu, 1 erweitert Kern, 1 erweitert E2E) —
  Testdateien zählen nicht gegen das LoC-Limit.
- **Effort:** medium.
- **Risk Level: MEDIUM.** `CorridorEditor.svelte` ist ein produktiv genutzter,
  geteilter Organismus mit drei weiteren Mounts (Trip-Hub, Vergleichs-Hub,
  2× Compare-Anlege) — der neue Guard und der neue Pool-Effekt sind additiv und
  `createMode`-gated (Default `false`), Blast Radius durch die bestehenden Tests
  der anderen Mounts absicherbar (s. AC-4). Größtes Einzelrisiko: der neue
  Pool-Refresh-`$effect` liest `trip?.display_config?.metrics` reaktiv — ein
  Fehler dort (z. B. `rows` statt nur `poolLeft` überschreiben) würde bereits
  eingestellte Korridore beim Wechsel des Wetter-Metriken-Reiters stillschweigend
  löschen (BUG-DATALOSS-Klasse, auch wenn hier Neuanlage statt Bestandsdaten).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlarmeTab.svelte` (`createMode`-Prop, S1/#2426) | component | Lebender Präzedenzfall für „Selbst-Speicher-Pfad per Guard abschalten, Rückruf statt PUT" — hier auf eine PLAIN FUNCTION (`maybeSchedule`) statt einen `$effect`-Rumpf übertragen. |
| `WeatherMetricsTab.svelte` (`createMode`-Prop, `onWeatherMetricsChange`) | component | Liefert `trip.display_config.metrics` reaktiv an `stubTrip` — Quelle des Signals, dem der neue Pool-Refresh-Effekt in `CorridorEditor.svelte` folgt (AC-7). Emittiert im `createMode` bereits beim eigenen Katalog-Laden einen Default-Metrik-Satz (`WeatherMetricsTab.svelte:717-719`, `catalogLoaded`-Gate) — dieser Timing-Punkt ist die Ursache dafür, dass `CorridorEditor`s Metrik-Pool ohne AC-7-Fix racy bzw. dauerhaft auf dem Startwert einfriert. |
| `corridorEditorState.ts` (`buildRoutePool`, `buildCorridorSavePayload`, `saveGateDecision`, `ROUTE_METRIC_DEFS`) | module | Reine Logik, unverändert wiederverwendet — `buildCorridorSavePayload(...).corridors` liefert die EINE Mapping-Stelle rows→`Corridor[]`, sowohl für den Save-Rückruf (AC-2/AC-3) als auch für den Pool-Refresh-Effekt (AC-7), statt die Row→Corridor-Abbildung ein zweites Mal von Hand zu schreiben. |
| `trip-detail/TripTabs.svelte:229` (`<CorridorEditor {trip} {onTripUpdate} {saveController} />`) | component | Beleg, dass der Hub für `context="route"` KEINE `CorridorEditorMobile`-Variante kennt — Begründung für den Mount-Entscheid in „Nicht in dieser Scheibe". |
| `internal/handler/trip.go:158-218` (`CreateTripHandler`) | Go-Handler | Dekodiert POST-Body direkt in `model.Trip` — akzeptiert `corridors` bereits ohne Änderung (`internal/model/trip.go:123`, kein `omitempty`, additiv). |
| `trip-new/__tests__/tripNewSsr.ts` (`renderTripNew`, `countTestid`) | Prüfstand | Bereits vorhandene SSR-Render-Harness (Issue #1738) — wiederverwendet für AC-1/AC-5, keine neue Infrastruktur. |
| `shared/__tests__/svelteInstanzPruefstand.ts` (`umgebungFuer`, `effekteVon`) | Prüfstand | Bindet Funktionsdeklarationen des Instanz-Skripts direkt auf die Test-Umgebung `u` (`:143-152`) — Grundlage dafür, `u.add()`/`u.patch()` in AC-2/AC-3 direkt aufzurufen, statt Effekt-Rümpfe zu simulieren. |
| `docs/specs/modules/fix_2277_s1_alarme_tab_route.md` | spec | Formvorbild dieser Spec (Detailtiefe, Wirkort-je-Zusicherung, Mutations-Gegenproben, `createMode`-Muster). |

## Implementation Details

### Design-Entscheidungen

1. **`corridors` fließt NICHT in `stubTrip` zurück.** Wie beim Alarm-Schatten-State
   (S1, `TripNewEditor.svelte:99`) würde eine Rückkopplung in `stubTrip` ($derived)
   bei jeder Korridor-Änderung eine neue `trip`-Prop-Referenz erzeugen und damit
   potenziell einen `trip`-lesenden Effekt in `CorridorEditor` erneut auslösen
   (dieselbe `effect_update_depth_exceeded`-Fehlerklasse). `corridors` lebt daher
   als eigener, unabhängiger `$state` in `TripNewEditor.svelte`, gefüttert
   ausschließlich über `onCorridorsChange`.

2. **`maybeSchedule()` bekommt den `createMode`-Zweig VOR dem bestehenden
   route-PUT, nicht als Ersatz dafür.** Reihenfolge in der Funktion:
   `vergleich` → `createMode` (neu) → route-PUT (unverändert, nur erreichbar wenn
   `createMode` falsy ist). Kein neuer `context`-Vergleich — `createMode` ist ein
   eigenständiges Gate, das (per Prop-Vertrag dieser Scheibe) nur zusammen mit
   `context="route"` gesetzt wird; die HERKUNFT-Ratsche zählt ausschließlich
   `context ===`/`context !==`-Tokens (`context_herkunft_zweige_eingefroren.test.ts:108-110`)
   und bleibt dadurch bei 47.

3. **Kein `setDirty()`-Äquivalent im Anlege-Modus.** Der Hub-Pfad ruft bei
   `saveGateDecision(rows) === 'dirty'` (mind. eine Zeile hat weder Min noch Max
   gesetzt, `corridorEditorState.ts::validateCorridorRows`) `saveController?.setDirty()`
   auf, um den Speicher-Indikator umzuschalten. Im Anlege-Modus gibt es keinen
   `saveController` und keinen separaten Speicher-Indikator für den
   Wertebereiche-Reiter — bei `'dirty'` passiert im `createMode`-Zweig schlicht
   nichts: der zuletzt gültige `onCorridorsChange`-Stand bleibt unverändert
   erhalten, bis die Zeile wieder gültig ist. Das ist bewusst identisch zum
   Hub-Verhalten (ungültige Zwischenstände werden nie persistiert), nur ohne
   eigene UI-Rückmeldung — dokumentiert unter Known Limitations, kein eigenes AC
   (der Fall ist mit den fünf fest verdrahteten `ROUTE_METRIC_DEFS` praktisch
   nicht erreichbar, da jede Definition mindestens einen `defaultMin`/`defaultMax`
   ungleich `null` hat, `corridorEditorState.ts:44-49` — `addRow()` liefert direkt
   eine gültige Zeile).

4. **Pool-Refresh-Effekt löst NIE `rows` neu auf, nur `poolLeft`.** Der
   bestehende, einmalige Lade-Effekt (`CorridorEditor.svelte:214-232`) baut `rows`
   aus `trip?.corridors ?? []` — im Anlege-Modus ist das immer `[]` (Punkt 1), ein
   erneuter Aufruf von `computeInitialRoute()` würde deshalb jede bereits
   eingestellte Zeile stillschweigend löschen. Der neue Effekt umgeht das, indem
   er `buildRoutePool()` mit dem AKTUELLEN `rows`-Stand (in `Corridor[]`
   zurückübersetzt über `buildCorridorSavePayload(...).corridors`) als erstes
   Argument aufruft — bereits eingestellte Zeilen bleiben über `present.get()`
   (`corridorEditorState.ts::buildRoutePool`) erhalten, nur `.poolLeft` (das
   Angebot im „+ Metrik"-Dropdown) wird übernommen.

5. **`CreateTripState.corridors` ist immer gesetzt, nie `undefined` im Payload.**
   `internal/model/trip.go:123` hat kein `omitempty` — ein fehlendes
   `corridors`-Feld im POST-Body ergibt serverseitig eine `nil`-Slice, die beim
   GET als `"corridors": null` zurückkäme (uneinheitlich ggü. einem später über
   den Hub gespeicherten Trip, wo immer `[]` oder eine gefüllte Liste steht).
   `buildCreateTripPayload()` setzt deshalb IMMER `trip.corridors = state.corridors
   ?? []` — ein frisch angelegter Trip ohne Wertebereiche-Interaktion liefert per
   GET `"corridors": []`, nie `null`, nie ein Fehler.

### Wirkort je Zusicherung

- **`maybeSchedule()` ruft in `createMode` `onCorridorsChange`, nie
  `saveController.schedule` (AC-2/AC-3)** → **Kern**, `umgebungFuer()` gegen
  `CorridorEditor.svelte`. Da `add`/`patch`/`maybeSchedule` reguläre
  `FunctionDeclaration`s im Instanz-Skript sind, bindet `umgebungFuer()` sie
  direkt auf `u` (`svelteInstanzPruefstand.ts:143-152`) — der Test ruft
  `u.add('wind_gust')` bzw. `u.patch('wind_gust', { max: 80 })` **direkt** auf,
  kein Effekt-Sammel-Umweg wie bei `AlarmeTab` nötig (dort lag der Guard in
  einem `$effect`-Rumpf). `saveController` wird als Spion-Objekt
  `{ schedule: spion1, setDirty: spion2 }` gesät, `onCorridorsChange` als
  zweiter Spion.
- **Pool folgt `trip.display_config.metrics`, ohne `rows` zu verlieren (AC-7)**
  → **Kern**, derselbe Prüfstand, aber über `effekteVon(ast, quelle, u,
  'poolLeft')`, da dieser Guard tatsächlich in einem `$effect` liegt. Testrezept:
  `u.rows` mit einer bereits eingestellten Zeile säen, `u.trip.display_config.metrics`
  NACH `umgebungFuer()` gezielt ändern, Effekt ausführen, assert `u.poolLeft`
  spiegelt die neue Metrik-Auswahl UND `u.rows` ist unverändert (Länge/Inhalt
  identisch zum Sä-Wert).
- **Reiter-Reihenfolge, Sperre, Ein-Instanz (AC-1, AC-5)** → **Kern, echtes
  SSR-Rendering** über `tripNewSsr.ts` (Issue #1738), wie in S1. Reine
  Quelltext-Regex-Checks sind vermeidbar, weil die Render-Harness bereits
  existiert.
- **Rundreise Payload → GET (AC-2, Staging-Teil)** → **Kern** (reiner
  Funktionsaufruf `buildCreateTripPayload()`, kein Netzwerk) **+ Live-E2E bei
  `/70-deploy`**: ein Trip mit mind. einem Wertebereich wird auf Staging
  angelegt, `GET /api/trips/{id}` liefert denselben Korridor zurück
  (`docs/reference/operations_playbook.md`-Pflicht „Staging-validiert" bei
  UI-Änderungen).
- **Hub-/Edit-Pfad bleibt bitgleich (AC-4)** → bestehende Tests, unverändert
  ausgeführt: `wertebereiche_speicherung_nur_im_vergleich_hub.test.ts`,
  `trip_corridors_write_test.go`, `test_corridor_persistence.py`, e2e
  `compare-wertebereiche-*.spec.ts`. Kein neuer Test nötig — die Zusicherung IST
  „diese Tests bleiben grün, unverändert".

## Expected Behavior

- **Input:** Im Reiter „Wertebereiche" von `/trips/new` (Desktop und Mobile,
  freigeschaltet nach Besuch von „Wetter-Metriken") stellt der Nutzer Min-/Max-
  Grenzen für die vom Wetter-Metriken-Reiter ausgewählten Größen ein — dieselben
  Bedienelemente wie im Trip-Hub, nur ohne eigenen Speicherpfad.
- **Output:** Änderungen bleiben lokal im Anlege-Dialog (kein PUT), bis der
  Nutzer auf „Speichern" klickt — dann fließen sie als `corridors` im EINEN
  `POST /api/trips` in den neuen Trip. „Zeitplan" bleibt gesperrt, bis
  „Wertebereiche" mindestens einmal geöffnet wurde.
- **Side effects:** Keine zusätzlichen Netzwerkzugriffe gegenüber dem
  bestehenden `/api/metrics`-Ladepfad (S1) und dem `loadRouteExtraMetricDefs()`-
  Aufruf, den `CorridorEditor` bereits für `context="route"` macht
  (`compareMetricCatalogLoader.ts`, geteilter Promise-Cache mit dem
  Ortsvergleich).

## Acceptance Criteria

- **AC-1:** Given `/trips/new` zeigt heute die Reiterfolge `Route, Etappen &
  GPX, Wegpunkte prüfen, Wetter-Metriken, Briefing-Zeitplan, Alerts`
  (`TripNewEditor.svelte:69-75`) ohne einen Wertebereiche-Reiter / When der neue
  `TAB_DEFS`-Eintrag `{ id: 'wertebereiche', label: 'Wertebereiche' }` zwischen
  `metriken` und `zeitplan` eingefügt wird / Then zeigt
  `renderTripNew({activeTab: 'route', isMobileViewport: false})` die Reiterfolge
  `…, Wetter-Metriken, Wertebereiche, Briefing-Zeitplan, Alerts` UND der
  Wertebereiche-Tab ist erst anklickbar (nicht in `unlocked`), nachdem der
  Wetter-Metriken-Tab besucht wurde, UND „Briefing-Zeitplan" ist erst anklickbar,
  nachdem „Wertebereiche" besucht wurde (nicht mehr direkt nach
  „Wetter-Metriken").
  - Test: Kern — `trip_new_wertebereiche_reiter.test.ts` (Reiter-Reihenfolge via
    SSR) + `tripNewLogic.test.ts` (neue Fälle für `unlockedTabs`, s. Affected
    Files).
  - Mutations-Gegenprobe: `if (wtVisited) s.add('zeitplan')` (alt) statt
    `if (wbVisited) s.add('zeitplan')` (neu) beibehalten ⇒ „Zeitplan" wäre bereits
    nach „Wetter-Metriken" anklickbar, ohne „Wertebereiche" je besucht zu haben
    ⇒ Test wird rot.

- **AC-2:** Given ein Nutzer stellt im Wertebereiche-Reiter über die ECHTEN
  Bedienelemente (Editor-Funktion `add('wind_gust')` gefolgt von
  `patch('wind_gust', { max: 80 })`, nicht eine von Hand gebaute Fixture) einen
  Grenzwert ein / When „Speichern" geklickt wird und `buildCreateTripPayload()`
  mit dem daraus resultierenden `state.corridors` aufgerufen wird / Then enthält
  das Payload-`trip.corridors` exakt `{ metric: 'wind_gust', range: [null, 80],
  notify: true, mark: false }`, UND ein GET auf den frisch angelegten Trip
  (Kern: `buildCreateTripPayload()`-Rückgabe direkt gelesen; Staging: echtes
  `GET /api/trips/{id}`) liefert denselben Wert zurück.
  - Test: Kern — `corridor_editor_create_mode_route.test.ts` treibt
    `u.add()`/`u.patch()` echt, liest den `onCorridorsChange`-Spion-Aufruf,
    übergibt dessen Argument an `buildCreateTripPayload()`
    (`tripNewLogic.test.ts`). Staging: manueller Klick-Durchlauf bei
    `/70-deploy` (Trip mit einem Wertebereich anlegen, GET prüfen).
  - Mutations-Gegenprobe: `onCorridorsChange?.(...)` durch ein No-Op ersetzen
    ⇒ `state.corridors` bleibt `undefined` ⇒ Payload-`corridors` wird `[]` statt
    dem gesetzten Wert ⇒ Test wird rot.

- **AC-3:** Given der route-PUT in `maybeSchedule()` (`buildSaveFn()` →
  `baueTripSpeicherung(api, trip!.id, …)`) feuert heute bei jeder Korridor-
  Änderung, sobald `saveGateDecision(rows) === 'schedule'` ist / When `stubTrip`
  (Id `__new__`) als `trip` UND `createMode={true}` gesetzt sind UND zusätzlich
  ein `saveController`-Spion (`{ schedule: spion, setDirty: spion2 }`) gesät
  wird / Then wird nach `u.add('wind_gust')` UND `u.patch('wind_gust', {max:
  80})` **kein einziges Mal** `schedule` oder `setDirty` auf dem
  `saveController`-Spion aufgerufen — auch dann nicht, wenn ein
  `saveController` überhaupt übergeben wird (Guard wirkt unabhängig davon, ob
  ein `saveController` vorhanden ist).
  - Test: Kern — `corridor_editor_create_mode_route.test.ts`, Positiv-Gegenprobe
    im selben Testblock: dieselben Aufrufe mit `createMode: undefined` ⇒
    `schedule`-Spion wird genau 1× aufgerufen (bestehendes Hub-Verhalten bleibt
    nachweisbar erreichbar).
  - Mutations-Gegenprobe: den `if (createMode) { … return; }`-Zweig entfernen
    ⇒ `schedule` wird auch mit `createMode: true` aufgerufen ⇒ Test wird rot.

- **AC-4:** Given `CorridorEditor.svelte` wird von drei weiteren Mounts
  produktiv genutzt (Trip-Hub `TripTabs.svelte:229`, Vergleichs-Hub
  `CompareTabs.svelte:1032`, Compare-Anlege `CompareNewEditor.svelte:392`) —
  keiner davon setzt `createMode` / When der neue Prop `createMode?: boolean`
  mit Default `false` eingeführt wird / Then bleiben
  `wertebereiche_speicherung_nur_im_vergleich_hub.test.ts`,
  `trip_corridors_write_test.go`, `test_corridor_persistence.py` und die e2e
  `compare-wertebereiche-*.spec.ts` **unverändert grün** (Default-Verhalten
  bitgleich, kein Aufrufer muss angepasst werden).
  - Test: Bestehende Tests, unveränderter Lauf — PLUS die Positiv-Gegenprobe
    aus AC-3 in `corridor_editor_create_mode_route.test.ts` (route-Mount wie im
    Trip-Hub, `createMode` NICHT gesetzt, `saveController`-Spion ⇒ `schedule`
    genau 1×). Sie ist der Wächter am Wirkort: die Go-/Python-Tests prüfen nur
    den Server und sehen eine falsche Voreinstellung im Frontend-Baustein
    strukturell nicht.
  - Mutations-Gegenprobe: Default von `createMode` auf `true` ändern (statt
    `false`) ⇒ der Trip-Hub-Mount verliert seinen PUT-Pfad ⇒ die
    Positiv-Gegenprobe in `corridor_editor_create_mode_route.test.ts` wird rot
    (`schedule` 0× statt 1×). `trip_corridors_write_test.go`/
    `test_corridor_persistence.py` werden dabei NICHT rot und gelten nur als
    Server-Regressionsschutz, nicht als Wächter dieser Voreinstellung.

- **AC-5:** Given der heutige `TAB_DEFS`-Wechsel würde ein neu gemountetes
  `CorridorEditor` bei jedem Tab-Wechsel neu initialisieren, wenn es NICHT nach
  dem `WeatherMetricsTab`/`AlarmeTab`-Muster (dauerhaft im DOM,
  `style:display`) gemountet wird — jede bereits eingestellte Wertebereich-Zeile
  ginge beim Verlassen und Zurückkehren zum Reiter verloren / When
  `CorridorEditor` wie `WeatherMetricsTab`/`AlarmeTab` gemountet wird
  (`{#if !isMobileViewport}`/`{#if isMobileViewport}`-Gate, EINE dauerhafte
  Instanz je Viewport, Sichtbarkeit über `style:display`) / Then liefert
  `countTestid(renderTripNew({...}), 'corridor-editor')` (oder das existierende
  Root-Testid der Komponente) in JEDER der drei Kombinationen
  `{activeTab:'wertebereiche', isMobileViewport:false}`,
  `{activeTab:'wertebereiche', isMobileViewport:true}`,
  `{activeTab:'route', isMobileViewport:false}` GENAU 1 — in KEINER Kombination
  existieren zwei Instanzen gleichzeitig, in KEINER verschwindet die einzige
  Instanz vollständig aus dem DOM.
  - Test: Kern — `trip_new_wertebereiche_reiter.test.ts`, `renderTripNew()` +
    `countTestid()` über die drei Kombinationen (Muster
    `trip_new_alarme_reiter.test.ts` AC-6).
  - Mutations-Gegenprobe: das `isMobileViewport`-Gate entfernen (zurück zu
    ungegatetem `{:else if activeTab === 'wertebereiche'}`) ⇒ bei
    `{activeTab:'route', isMobileViewport:false}` liefert `countTestid` `0`
    statt `1` ⇒ Test wird rot.

- **AC-6:** Given `CreateTripState.corridors?: Corridor[]` bleibt `undefined`,
  solange der Nutzer den Wertebereiche-Reiter nie öffnet oder öffnet, ohne eine
  Zeile hinzuzufügen / When `buildCreateTripPayload(state)` ohne `corridors`-Feld
  in `state` aufgerufen wird / Then liefert `payload.corridors` exakt `[]`
  (nicht `undefined`, nicht `null`, keine Exception) — ein per GET
  nachgeladener, so angelegter Trip zeigt `"corridors": []`.
  - Test: Kern — `tripNewLogic.test.ts`, direkter Aufruf von
    `buildCreateTripPayload({... ohne corridors})`.
  - Mutations-Gegenprobe: `trip.corridors = state.corridors ?? []` durch
    `trip.corridors = state.corridors` (ohne Fallback) ersetzen ⇒
    `payload.corridors === undefined` ⇒ JSON-Serialisierung ließe das Feld im
    POST-Body ganz weg ⇒ Test wird rot.

- **AC-7:** Given der einmalige Lade-Effekt in `CorridorEditor.svelte`
  (`:214-232`) berechnet `poolLeft` nur EINMAL, beim ersten erfolgreichen Laden
  der Zusatz-Metrik-Definitionen — im Anlege-Modus (dauerhaft gemountet ab
  Seitenaufruf) geschieht das, bevor der Nutzer den Wetter-Metriken-Reiter
  überhaupt besucht hat, und `WeatherMetricsTab` emittiert im `createMode` zudem
  asynchron einen Default-Metrik-Satz (`WeatherMetricsTab.svelte:717-719`) —
  ohne Nachbesserung friert das Angebot im „+ Metrik"-Dropdown auf einem
  Zufalls-Zeitpunkt der beiden nebenläufigen Ladevorgänge ein und folgt späteren
  Änderungen im Wetter-Metriken-Reiter NIE / When der neue, zweite
  `createMode`-gated `$effect` `trip?.display_config?.metrics` reaktiv liest und
  `poolLeft` (nicht `rows`) neu berechnet / Then zeigt das „+ Metrik"-Dropdown
  nach einer Änderung der Metrik-Auswahl im Wetter-Metriken-Reiter (Metrik neu
  aktiviert/deaktiviert) die AKTUALISIERTE Auswahl, UND eine bereits im
  Wertebereiche-Reiter eingestellte Zeile bleibt dabei unverändert erhalten
  (Wert UND Anwesenheit).
  - Test: Kern — `corridor_editor_create_mode_route.test.ts`, Rezept: `u.rows`
    mit einer Zeile säen, `u.trip.display_config.metrics` nachträglich ändern,
    `effekteVon(ast, quelle, u, 'poolLeft')` ausführen, assert `u.poolLeft`
    spiegelt die neue Auswahl UND `u.rows` ist bit-identisch zum Sä-Wert.
  - Mutations-Gegenprobe: den neuen Effekt so verfälschen, dass er zusätzlich
    `rows = rebuilt.rows` setzt (statt nur `poolLeft`) ⇒ die gesäte,
    bereits eingestellte Zeile verschwindet aus `u.rows` ⇒ Test wird rot
    (Datenverlust-Regression).

## Known Limitations

- **Kein eigener „ungespeichert"-Hinweis für eine unvollständige
  Wertebereiche-Zeile im Anlege-Modus.** Bleibt eine hinzugefügte Zeile ohne
  Min/Max-Wert (nur bei Katalog-Zusatzmetriken ohne Default möglich, keine der
  fünf fest verdrahteten `ROUTE_METRIC_DEFS` betroffen — Implementation Details
  Punkt 3), wird sie beim Speichern schlicht nicht in `corridors` übernommen;
  der Trip wird trotzdem angelegt. Der Hub zeigt in diesem Fall einen
  Dirty-Indikator über `saveController`, der Anlege-Modus hat kein Pendant dazu.
  Bewusst akzeptiert für S2a — praktisch nicht erreichbar über die Standard-
  Metriken, kein nutzersichtbarer Datenverlust (die Zeile ist im UI weiterhin
  sichtbar, nur nicht Teil des Speicherstands).
- **`display_config.metric_alert_levels` wird beim Anlegen nicht über
  `CorridorEditor` gesetzt.** `buildCorridorSavePayload(...).metric_alert_levels`
  wird nur für den Save-Rückruf berechnet, aber NICHT an `onCorridorsChange`
  übergeben (der Rückruf nimmt nur `Corridor[]`) — Alarm-Empfindlichkeit bleibt
  exklusiv Sache des Alarme-Reiters (S1), unverändert zum Hub-Verhalten
  (`CorridorEditor.svelte`-Kommentar zu Issue #1371).
- **Kein neues Live-E2E-Spec in dieser Scheibe** über das erweiterte
  `trip-new-loads-without-effect-loop.spec.ts` hinaus. Der volle
  Erstell-Durchlauf ist über AC-2 im Kern bit-genau nachgewiesen (echter
  Editor-Rückruf + echter Payload-Builder); der manuelle Staging-Klick-
  Durchlauf (Pflicht bei jeder UI-Änderung) bleibt bei `/70-deploy` bestehen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Der `createMode`-Guard folgt exakt dem in S1
  (`fix_2277_s1_alarme_tab_route.md`) und ursprünglich `WeatherMetricsTab.svelte`
  etablierten Muster (Selbst-Speicher-Pfad abschalten, Rückruf statt PUT) —
  kein neuer Architekturentscheid, sondern dieselbe, bereits akzeptierte Lösung
  auf einen dritten Organismus angewendet. Der Verzicht auf
  `CorridorEditorMobile.svelte` als Mobile-Mount ist ebenfalls keine
  Architekturentscheidung, sondern folgt dem bereits bestehenden Hub-Präzedenzfall
  (`TripTabs.svelte:229`, ein Component für beide Viewports im route-Kontext).

## Changelog

- 2026-09-27: Initial spec created (Scheibe S2a von #2277, Epic #2345).
