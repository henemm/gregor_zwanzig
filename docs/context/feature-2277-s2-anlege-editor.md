# Context: feature-2277-s2-anlege-editor

## Request Summary

Issue #2277 ("Anlege-Strecke: `/trips/new` und `/compare/new` sind zwei Implementierungen mit
anderer Reiterfolge") ist Teil von Epic #2345 (Parität Ortsvergleich↔Trip), Nachfolger von
#2276 (Hub-Speicherweg, abgeschlossen). Zielbild: EIN Anlege-Editor `NewEditor` mit
`context="route"|"vergleich"`, geteilter Rahmen + geteilte Organismen.

**S1 ist live** (PR #2426, Prod `92252757`): `/trips/new` mountet im Alerts-Reiter jetzt den
geteilten `AlarmeTab` (`createMode`) statt `AlertRulesEditor`.

**Laut letztem PO-Kommentar (2026-09-25) ist der VERBLEIBENDE Umfang von S2 explizit nur:**
1. „`/compare/new`-Angleichung"
2. „Wertebereiche im Trip-Anlegen"

Die übrigen Acceptance Criteria aus dem Issue-Entwurf (AC-3 Reiter-Identität, AC-5 Aufräumen
der Alt-Module, AC-6/AC-7 Mobile-Rahmen) sind Kandidaten, aber laut PO-Formulierung nicht
zwingend Teil dieser Scheibe — siehe Schnitt-Vorschlag.

## Related Files

| Datei | Zeilen | Relevanz |
|---|---|---|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | 1227 | Trip-Anlege-Editor. Reiter `route,etappen,wegpunkte,metriken,zeitplan,alerts` (`:69-75`). Mountet `WeatherMetricsTab` (`:898`), `AlarmeTab` (`:910,1157`), `VersandTab`+`EditReportConfigSection` (`:879,1137`). **Kein `CorridorEditor`-Mount** (0 Treffer im ganzen File). Save: EIN `POST /api/trips` (`:404-429`, Funktion `buildAndSave`). Mobile-Header: eigener 44×44-Icon-Button ohne `aria-label` (`:483-489`), kein `PageHeader`/`EditorStickyFooter` (0 Treffer für beide). |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | 227 | Lock-Engine (`unlockedTabs`/`doneTabs`/`progressCount`/`canSave`, `:24-80`) + `CreateTripState`/`buildCreateTripPayload` (`:100-227`). Kein `idealwerte`/Wertebereiche-Feld in `TabId` (`:20`) oder `CreateTripState` (`:100-112`) — Korridore können heute gar nicht in den Anlege-Payload. |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | 578 | Compare-Anlege-Editor. Reiter `vergleich,orte,metriken,idealwerte,alarme,versand` (`:96-103`). Mountet `WeatherMetricsTab` (`:383,484`), `CorridorEditor`/`CorridorEditorMobile` (`:392,488`), `AlarmeTab` (`:401,492`), `VersandTab` (`:409,495`) — alle über `*PropsAus(wiz)`-Bündel (`:46-49`). Nutzt `getContext<CompareWizardState>('compare-wizard-state')` (`:68`), Save: `wiz.saveNewPreset()` in `handleActivate` (`:197-207`), EIN POST analog Trip-Muster. Mobile-Header nutzt bereits `PageHeader` (`:420`) + `EditorStickyFooter` (`:501-516`) — **hier ist Compare bereits weiter als Trip**, nicht umgekehrt. |
| `frontend/src/lib/components/compare-new/compareNewLogic.ts` | 69 | Eigene Lock-Engine, strukturell gespiegelt aus `tripNewLogic.ts` (Kommentar `:1-17`), inkl. `idealwerte` in der Freischalt-Kette (`:19-46`). Keine Payload-Builder-Funktion (Speichern läuft über `wiz.saveNewPreset()`, nicht über eine reine Funktion wie `buildCreateTripPayload`). |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | — | Wizard-Context-Klasse. Importiert von: `CompareNewEditor.svelte`, `routes/compare/new/+page.svelte` (setzt Context), **und** `Step2Orte.svelte` **und** `CompareTabs.svelte` (Hub, `:80` Import, `:334` eigene Instanz `new CompareWizardState()`). Kein reiner Anlege-Baustein mehr — Hub braucht die Klasse ebenfalls. |
| `frontend/src/lib/components/compare/*PropsAus.ts` (`alarmePropsAus.ts`, `corridorPropsAus.ts`, `versandPropsAus.ts`, `wetterMetrikenPropsAus.ts`) | — | Aus #2276 S6c/S6d: EIN Bündel-Bauer je Organismus, von ALLEN drei Compare-Mounts (Hub + Anlege Desktop + Mobil) gespeist. `corridorPropsAus.ts:9-14` dokumentiert explizit **„hat bewusst kein Trip-Pendant"** — der `route`-Zweig braucht keine Zwischenschicht, weil er `trip`/`onTripUpdate` direkt reicht. |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | — | Geteilter Organismus. Props (`:43-66`): `context`, `trip`/`onTripUpdate`/`saveController` (route) vs. `preset`/`corridors`/`idealRanges`/... (vergleich, Wertprops). **Kein `createMode`-Prop** (0 Treffer im ganzen File — anders als `AlarmeTab.svelte`/`WeatherMetricsTab.svelte`). `maybeSchedule()` (`:277-296`) ruft für `context==='route'` **unbedingt** `saveController?.schedule(buildSaveFn())`; `buildSaveFn()` (`:245-255`) liest `trip!.id` und baut ein PUT über `baueTripSpeicherung`. Ohne `saveController` ist das ein No-Op (optional chaining) — aber dann gibt es auch keinen Rückkanal (kein `onCorridorsChange`-Aufruf im route-Zweig, das passiert nur via `syncToWizard()` im vergleich-Zweig, `:263-271`). |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | — | `createMode`-Prop vorhanden (`:76,148,415`): `if (!trip || createMode) return;` unterdrückt PUT, Änderungen laufen über `onChannelToggle`/`onThresholdChange`/etc. an den Aufrufer. Muster, dem `CorridorEditor` für AC-2 fehlt. |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | — | `createMode`-Prop vorhanden (12 Fundstellen, u. a. `:158,209,682,717,727,989,1012`) — vollständiges Dual-Mode-Muster (Anlege- vs. Hub-Speicherweg). |
| `frontend/src/routes/trips/new/+page.svelte`, `+page.server.ts` | 9 / 33 | `+page.server.ts:22-30` lädt `templateTrip` per `?from=<id>` GET `/api/trips/{fromId}`, gibt es im `load`-Return zurück (`:32`). **Aber**: `+page.svelte` deklariert `let { data } = $props();` und übergibt **nichts** an `<TripNewEditor />` (`:9`) — `templateTrip` wird nirgends im Frontend konsumiert (0 Treffer für `templateTrip` außerhalb der Server-Load-Datei). Die „Vorlage"-Funktion ist serverseitig vorbereitet, aber **im Trip-Editor selbst aktuell tot/unverdrahtet**. |
| `frontend/src/routes/compare/new/+page.svelte`, `+page.server.ts` | 24 / 26 | Kein `from`/Vorlage-Handling überhaupt (0 Treffer `searchParams`/`from` in beiden Dateien). AC-4 („`/compare/new?from=<id>`") ist komplett neu zu bauen — und muss dabei auch erst die kaputte Trip-Referenz (`templateTrip` unverdrahtet) mit reparieren oder bewusst separat lassen. |
| `frontend/src/routes/+layout.svelte` | — | `:212` `const isWizard = $derived(page.url.pathname.startsWith('/trips/new'));`, `:271` `{#if !isWizard}` blendet die globale Tabbar aus — **nur** für `/trips/new`, nicht für `/compare/new` (AC-6 unerfüllt, bestätigt Mobile-Audit-Nachtrag). |
| `frontend/src/lib/components/edit/TripEditView.svelte` | — | Trip-**Hub** (Detail-Editor, nicht Anlegen!). Importiert weiterhin `AlertRulesEditor` (`:10`) und mountet es (`:205`). Migration auf `AlarmeTab` ist dort **nicht** passiert — S1/S2 betreffen nur `/trips/new`. Das ist der Grund, warum `AlertRulesEditor` trotz S1 noch einen produktiven Importeur hat. |
| `frontend/src/lib/components/shared/VersandTab.svelte` | — | Mountet intern weiterhin `EditReportConfigSection`-Muster (Kommentare `:136,200,232` referenzieren es als Vorbild/Quelle für Feldnamen) — `EditReportConfigSection` selbst ist über ~20 Dateien verdrahtet (siehe unten), kein isolierbares Alt-Modul. |

## Existing Patterns

- **Progressive-Tab-Rahmen** (beide Editoren, strukturell identisch aber doppelt implementiert):
  Tab-Definitionsliste (`TAB_DEFS`) mit `id`/`label`/`lockHint` (Trip `:69-75`, Compare `:96-103`),
  `unlocked`/`done`-Sets aus reiner Logikdatei, Fortschrittsbalken aus Segmenten, XOR
  Desktop/Mobile-Mount über `isMobileViewport`/CSS-Klassen (`.tn-desktop`/`.tn-mobile` vs.
  `.cm-desktop`/`.cm-mobile`).
- **Geteilte Organismen werden bereits `context`-parametrisiert gemountet** in beiden Editoren
  (`WeatherMetricsTab`, `AlarmeTab`, `VersandTab`) — nur `CorridorEditor` fehlt im Trip-Zweig.
- **Zwei unterschiedliche Speicher-Idiome** für denselben Zweck „EIN POST beim Anlegen":
  Trip baut eine reine Funktion (`buildCreateTripPayload(state)`) aus lokalem `$state`, Compare
  hält seinen State direkt im `CompareWizardState`-Objekt (Context) und ruft `wiz.saveNewPreset()`.
  Eine Übertragung des Compare-Verhaltens auf den Trip-Payload-Stil (oder umgekehrt) ist NICHT
  Teil des Issues explizit gefordert und würde die Bündel-Test-Familie (`tripNewLogic.test.ts`,
  `compareNewLogic.test.ts`) aufbrechen.
- **`*PropsAus.ts`-Bündel-Pattern** (#2276 S6c/S6d) ist der aktuelle Standard für den
  `vergleich`-Zweig geteilter Organismen — bewusst OHNE Trip-Pendant laut
  `corridorPropsAus.ts:9-14`, weil der `route`-Zweig direkt `trip`/`onTripUpdate` reicht. Für
  AC-2 folgt der neue Trip-Mount also NICHT dem PropsAus-Muster, sondern dem
  `trip={stubTrip} createMode={true}`-Muster von `AlarmeTab`/`WeatherMetricsTab` in
  `TripNewEditor.svelte:910,898`.
- **`createMode`-Dual-Mode-Konvention**: `AlarmeTab`/`WeatherMetricsTab` unterscheiden explizit
  Hub-Speicherweg (PUT via `saveController`) und Anlege-Speicherweg (Rückruf-Props, kein PUT).
  `CorridorEditor` hat diese Unterscheidung für `context="route"` **nicht** — das ist die
  zentrale technische Lücke für AC-2 (siehe Risiken).

## Dependencies (Upstream/Downstream)

- **Upstream:** #2276 (Hub-Speicherweg auf Wertprops, abgeschlossen, `main`) — liefert das
  `*PropsAus.ts`-Muster, das S2 für den Compare-Zweig weiterverwenden kann/soll.
- **Downstream/Geschwister:** #2285 (Go-PUT Patch-DTO vs. Voll-Dekodierung), #2284 (Hub-Kopf),
  #2283 (Vorschau), #2287/#2288 (Reiter-Kennungen/DnD im Hub) — alle Teil von Epic #2345, aber
  NICHT Gegenstand von S2.
- **Betroffene Gates:**
  - `pendant_gate.py` (`.claude/hooks/pendant_gate.py:1-60`) — blockiert neu angelegte Dateien
    unter `frontend/src/lib/components/compare-new/` oder `trip-new/` ohne
    `gz-eigenstaendig:`-Begründung; `shared/` ist ausgenommen. Relevant, falls S2 z. B. eine neue
    `EditorHeader`/`MobileShell`-Komponente NUR für einen der beiden Editoren anlegt.
  - HERKUNFT-Zweig-Ratsche (`docs/reference/gates_und_ratschen.md:310-389`,
    `context_herkunft_zweige_eingefroren.test.ts`) — Dauer-Gate seit S6h, zählt final 47
    `context ===`-Verzweigungen (27 FACHLICH, 6 DARSTELLUNG, 14 HERKUNFT). Ein `createMode`-Zweig
    in `CorridorEditor.svelte` für `context==='route'` würde voraussichtlich NEUE
    `context`/`createMode`-Verzweigungen einführen — gegen die eingefrorene Liste prüfen, bevor
    committet wird.
  - `ci_e2e_specs.txt` (`.github/ci_e2e_specs.txt:320`) — nur `e2e/issue-661-trip-new-mobile.spec.ts`
    ist für `trip-new` registriert, **kein** Eintrag für `compare-new` gefunden. Neue/geänderte
    E2E-Specs zu `/compare/new` müssten ggf. neu aufgenommen werden.
  - LoC-Limit 250/Workflow (`workflow.py status`) — AC-2 (CorridorEditor-Dual-Mode + Mount +
    Payload-Feld) und AC-1/AC-4 (Angleichung + `?from=`) zusammen sprengen das vermutlich
    (siehe Schnitt-Vorschlag).

## Existing Specs

- `docs/specs/modules/fix_2277_s1_alarme_tab_route.md` — S1-Spec (Alerts-Reiter/AlarmeTab), als
  Formvorlage für eine S2-Spec verwendbar.
- `docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md` — Ursprungs-Spec von
  `CompareNewEditor.svelte` (Epic #1301 F2a).
- `docs/specs/modules/feat_1301_f2b_editor_loeschung.md` — Löschung des Alt-`CompareEditor.svelte`.
- `docs/specs/modules/feat_1301_f3_deadcode_offscreen.md` — Folge-Aufräumarbeit nach F2a/F2b.
- **Keine** existierende Spec für S2 selbst — Phase 1 (Kontext) ist der richtige Einstieg, `/30-write-spec` folgt danach.
- Referenz zum Mobile-Nachtrag: `docs/analysis/mobile-audit-2026-09-19.md` (Befund P2-1/P4-3, Ticket T4).

## Risks & Considerations

1. **CorridorEditor fehlt `createMode` für `context="route"`** (siehe oben,
   `CorridorEditor.svelte`). Ein naiver Mount analog `AlarmeTab` würde entweder (a) ohne
   `saveController` den Rückkanal verlieren (Wertebereiche gehen beim Anlegen verloren — Verstoß
   gegen „Bestandsdaten/Datenerhalt"-Grundsatz, wenngleich hier Neuanlage statt Bestandsdaten) oder
   (b) mit `saveController` einen PUT gegen eine noch nicht existierende Trip-ID auslösen. **Muss
   in der Spec-Phase als eigene technische Änderung an `CorridorEditor.svelte` (neuer
   `createMode`-Zweig + `onCorridorsChange`-artige Rückrufe für `route`) benannt werden**, nicht
   nur als Editor-Verdrahtung.
2. **`templateTrip`/`?from=` ist bereits im Trip-Pfad kaputt** (Server lädt, Client konsumiert
   nicht). AC-4 verlangt „Trip-Verhalten" für Compare — aber das Trip-Verhalten existiert aktuell
   nicht wirklich. Klären, ob S2 (a) den Trip-Bug nebenbei mitbehebt, (b) das kaputte Verhalten
   1:1 auf Compare spiegelt (dann bleibt AC-4 unerfüllt in beiden), oder (c) AC-4 aus S2
   herausschneidet. Nebenbefund-Triage (CLAUDE.md) spricht für eigenes Issue nur bei
   nutzersichtbarem Fehlverhalten — das ist hier der Fall (Vorlage wirkt nie), aber die Ursache
   liegt im Trip-Editor, nicht im Compare-Editor.
3. **`compareWizardState`/`compareNewLogic` fallen NICHT „ersatzlos"** wie in der
   Kontext-Anfrage vermutet: `compareWizardState.svelte.ts` hat mit `CompareTabs.svelte:334`
   einen zweiten, vom Anlege-Editor unabhängigen Importeur (Hub instanziiert seine eigene
   `CompareWizardState`). Eine vollständige Ablösung dieses Moduls beträfe auch den Hub — außerhalb
   von S2s Scope. `compareHubWizardBridge` und `ModeCard` existieren dagegen **als Dateien gar
   nicht mehr** (0 Treffer) — vermutlich bereits in #2276 oder früheren Slices entfernt; für diese
   beiden ist DoD-1 schon erreicht.
4. **`AlertRulesEditor`/`EditReportConfigSection` haben Importeure außerhalb der
   Anlege-Editoren**: `AlertRulesEditor` lebt in `TripEditView.svelte` (Trip-**Hub**, nicht
   Anlegen) weiter — dessen Migration ist nicht Gegenstand von S2. `EditReportConfigSection` ist
   in ~20 Dateien verdrahtet (u. a. `VersandTab.svelte` selbst als Referenzmuster) und damit kein
   isolierbares totes Modul, sondern aktiv querschnittlich genutzt (bekanntes Duplikat-Problem
   C4-22, separates Issue #1986). AC-5 („kein produktiver Importeur mehr") ist für diese beiden
   Module in S2 **nicht erreichbar**, ohne #1986 und die Hub-Migration von `AlertRulesEditor`
   vorzuziehen.
5. **Mobile-Rahmen-Asymmetrie geht in beide Richtungen**: Trip fehlt `PageHeader`/
   `EditorStickyFooter` (die Compare bereits nutzt), UND die globale Tabbar-Logik (`isWizard`)
   kennt nur `/trips/new`. Eine „Angleichung" muss also teils Compare-Muster auf Trip übertragen
   (Header/Footer-Bausteine), teils `+layout.svelte` für beide Routen gleich behandeln.
6. **Datenerhalt/Cross-User**: Anlegen ist Schreiben eines neuen Objekts (kein Read-Modify-Write
   auf Bestand), daher greift BUG-DATALOSS-Klasse hier nicht direkt — aber der `alarm`-Payload in
   `tripNewLogic.ts:207-224` demonstriert bereits das Muster (additiv auf `display_config`
   mergen), das ein neues `corridors`/`idealRanges`-Feld im Trip-Payload ebenso befolgen muss.
   Kein nutzerbezogener Endpoint wird neu berührt (POST erstellt für den eingeloggten Nutzer);
   trotzdem mit zwei Nutzern testen, sobald `?from=` (fremde Trip-/Compare-ID als Vorlage)
   eingebaut wird — Cross-User-Leck wäre, eine fremde ID als Vorlage laden zu können.
7. **LoC-Limit 250**: CorridorEditor-Dual-Mode-Erweiterung (neuer Zweig + Tests) + Trip-Editor-Mount
   + Payload-Feld + ggf. Mobile-Rahmen-Angleichung + `?from=` für Compare sprengen realistisch
   250 LoC in einer Scheibe.

## Schnitt-Vorschlag

Empfehlung: **S2 in drei technisch klar getrennte Unterscheiben schneiden**, weil sie
unabhängige Risikoprofile und unabhängige Dateien berühren (kein Datenfluss zwischen ihnen):

- **S2a — Wertebereiche im Trip-Anlegen (AC-2).** Kern: `CorridorEditor.svelte` um einen
  `createMode`-Zweig für `context="route"` erweitern (Muster `AlarmeTab.svelte:76,148,415`:
  `if (!trip || createMode) return` vor dem PUT, Rückruf-Props statt `saveController`), dann
  Mount in `TripNewEditor.svelte` (analog `:898-905` AlarmeTab-Block) + neues `TabId`/`TAB_DEFS`-
  Segment „Wertebereiche" in `tripNewLogic.ts` + Payload-Erweiterung in `buildCreateTripPayload`.
  **Größtes technisches Risiko der ganzen Restarbeit** (Punkt 1 oben) — verdient eigene Spec/RED/
  Adversary-Runde, weil es einen geteilten Organismus verändert, den auch der Hub nutzt (Regressionsgefahr
  für die bestehende Hub-Korridor-Speicherung).
- **S2b — Mobile-/Rahmen-Angleichung (AC-3, AC-6, AC-7).** Kein Datenmodell-Risiko, reines
  Layout/Markup: `TripNewEditor.svelte` auf `PageHeader`/`EditorStickyFooter` umstellen (Compare
  ist hier bereits Vorbild), `+layout.svelte:212` `isWizard`-Bedingung auf beide Routen
  ausweiten, Reiter-Labels/Reihenfolge/Lock-Hints textlich angleichen soweit fachlich identisch
  (Trip hat zusätzliche eigene erste Reiter Route/Etappen/Wegpunkte, das bleibt Kind-eigen laut
  CLAUDE.md).
- **S2c — `?from=`-Vorlage für Compare (AC-4).** Erst NACH Klärung von Risiko 2 (kaputte
  Trip-Vorlage): entweder den Trip-Bug als Vorbedingung fixen (kleiner, klar abgegrenzter Fix,
  ggf. eigenes Mini-Issue wegen nutzersichtbarem Fehlverhalten) oder das Verhalten bewusst separat
  für Compare neu und korrekt bauen, dokumentiert in der Spec als Abweichung vom „Trip-Vorbild".

**AC-5 (Modul-Aufräumen) explizit NICHT als eigene Scheibe jetzt**, sondern nur der Teil, der
durch S2a/S2b organisch wegfällt (aktuell: nichts, da `AlertRulesEditor`/`EditReportConfigSection`
Importeure außerhalb der Anlege-Editoren haben) — Restarbeit gehört in ein Folge-Ticket, sobald
die Hub-Migration von `AlertRulesEditor` und #1986 (EditReportConfigSection-Duplikat) entschieden
sind.

Reihenfolge-Empfehlung: S2a zuerst (höchstes Risiko, blockiert nichts Nachgelagertes), S2b und
S2c können parallel/in beliebiger Reihenfolge folgen, da sie unterschiedliche Dateien berühren.

## Analysis

### Type
Feature (Rework, Epic #2345). **Dieser Workflow ist die Scheibe S2a „Wertebereiche im Trip-Anlegen“.**
Tech-Lead-Entscheid: Der PO-Kommentar vom 25.09. nennt die Reste im Plural als Scheiben. S2a kommt zuerst, weil sie das höchste Risiko trägt: Sie ändert einen geteilten Organismus, den auch Hub und Compare nutzen. **Die `/compare/new`-Angleichung (AC-3/6/7) und `?from=` (AC-4) folgen als eigene Workflows. AC-5 (Aufräumen) gehört nicht zu S2.**

### Verifizierte Fakten (27.09., Worktree == origin/main)
- **Das Backend braucht keine Änderung.**
  - Go `CreateTripHandler` (`internal/handler/trip.go:158-218`) dekodiert das komplette `model.Trip` inkl. `Corridors` (`internal/model/trip.go:123`, `json:"corridors"`) und speichert es (`:207`).
  - Python liest `trip.corridors` (`src/output/renderers/trip_report.py:247`, Markierung in `email/html.py:1051`).
- **CorridorEditor, route-Zweig:**
  - `maybeSchedule()` (`CorridorEditor.svelte:284-298`) ruft `saveController?.schedule(buildSaveFn())` auf.
  - `buildSaveFn()` (`:245-256`) macht ein PUT auf `trip!.id` mit `{corridors, display_config}`.
  - Es gibt keinen `createMode`-Prop.
  - Der Rückruf `onCorridorsChange` existiert (`:65`), wird aber bisher nur im vergleich-Zweig bedient (`syncToWizard`, `:262-271`).
- **HERKUNFT-Ratsche** (`shared/__tests__/context_herkunft_zweige_eingefroren.test.ts`):
  - Sie zählt NUR `context ===`/`context !==` in `shared/` (`:108-110`).
  - Eingefroren sind 47 `Datei:Zeile`-Einträge (`:187-254`), dazu kommt die `BLEIBT_MIT_INHALT`-Fesselung (`:272-462`).
  - `createMode`-Guards werden NICHT gezählt; AlarmeTab `:415` und WeatherMetricsTab `:673` sind auf diesem Weg durchgekommen.
  - Das Einfügen in CorridorEditor verschiebt ~11 Einträge. Diese werden **nachgeführt (Zeile + Fessel-Inhalt). Es kommen keine neuen Einträge dazu, und bei Rot wird nie einfach nachgezogen.**
- **Lock-Engine Compare** (`compareNewLogic.ts`):
  - `idealwerte` wird nach `metrikenVisited` freigeschaltet (`:36`) und gilt als done, sobald besucht (`:55`).
  - `alarme` wird nach `idealsVisited` freigeschaltet.
  - Label „Wertebereiche“, lockHint „erst Wetter-Metriken öffnen“ (`CompareNewEditor.svelte:100`).
  - Zum Vergleich Trip (`tripNewLogic.ts`): `zeitplan` wird nach dem Besuch der Metriken freigeschaltet, `canSave` bedeutet „zeitplan done“ (`:78-80`).
- **`?from=`/`templateTrip`:** Kein UI-Link führt auf `/trips/new?from=` (grep: 0 Treffer). Das ist toter Code ohne nutzersichtbaren Fehler. Er wird als Nebenbefund in #1199 gebucht und gehört nicht zu S2a.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | MODIFY | Prop `createMode` (default `false`). Im route-Zweig von `maybeSchedule()` bei `createMode` statt PUT: `onCorridorsChange?.(buildCorridorSavePayload(rows, originalLevels, routeUnknownCorridors).corridors)`. KEIN neuer `context`-Zweig. |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | `TabId` bekommt `'wertebereiche'` zwischen `metriken` und `zeitplan`. Freischaltung nach dem Besuch der Metriken; `zeitplan` wird nach dem Besuch der Wertebereiche freigeschaltet (Kette wie Compare). Neu: `CreateTripState.corridors`. `buildCreateTripPayload` setzt `trip.corridors` additiv (Muster Alarm-Teil `:207-224`). `canSave` bleibt unverändert. |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | `TAB_DEFS`-Eintrag „Wertebereiche“ (Label/lockHint wie Compare), `corridors`-State mit Rückkanal, Mount `CorridorEditor context="route" createMode` für Desktop und Mobil. Dauerhaft gemountet per `style:display` (Muster S1). |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | Zeilen der CorridorEditor-Einträge nachführen (Anzahl bleibt 47). |
| `frontend/src/lib/components/trip-new/__tests__/tripNewLogic.test.ts` + neue Verhaltens-Testdatei(en) | MODIFY/CREATE | Lock-Kette; Payload trägt Korridore aus echtem Editor-Rückruf; Hub-Pfad (`createMode` falsy) unverändert. |

### Scope Assessment
- Files: 3 produktiv + 2–3 Tests
- Estimated LoC: produktiv ca. +70–90 (Plan-Agent), gesamt < 250 ⇒ kein Override nötig
- Risk Level: MEDIUM. Der geteilte Organismus birgt Regressionsgefahr für den Hub; ansonsten ist die Änderung isoliert, das Backend bleibt unverändert.

### Technical Approach
Das `createMode`-Muster von AlarmeTab (S1) wird auf CorridorEditor übertragen. Der Trip-Anlege-Editor bekommt einen Reiter samt Mount. Die Korridore fließen über den Rückruf in `CreateTripState` und mit dem einen `POST /api/trips` in den neuen Trip.

**Randbedingungen für die Spec:**
1. `createMode` ist per Default `false`. Damit bleibt der Hub-/Edit-Pfad (`context="route"`, PUT via `saveController`) bitgleich. Die bestehenden Tests bleiben grün:
   - `wertebereiche_speicherung_nur_im_vergleich_hub.test.ts`
   - `trip_corridors_write_test.go`
   - `test_corridor_persistence.py`
   - e2e `compare-wertebereiche-*.spec.ts`
2. Mindestens EIN Test lässt das Produkt das Feld schreiben: echter Editor-Rückruf → State → `buildCreateTripPayload` → `trip.corridors`. Die Fixture darf `corridors` nicht selbst setzen.
3. `corridors` fließt NICHT in `stubTrip` zurück; das würde eine Effekt-Schleife auslösen (vgl. Kommentar zum `alarm`-Stand). Der Tab bleibt dauerhaft gemountet, beim Reiterwechsel gibt es keinen Remount, sonst ginge der Stand verloren.
4. Im createMode gibt es kein PUT, auch nicht bei vorhandenem `saveController` (Guard vor `schedule`).
5. Ratsche: Die Anzahl bleibt 47, es wird nur nachgeführt.
6. Ein zusätzlicher Zwei-Nutzer-Test ist nicht nötig, weil kein neuer Endpoint entsteht; der POST legt den Trip für den eingeloggten Nutzer an. Auf Staging wird ein Trip mit Korridor angelegt und die Persistenz per GET geprüft.

### Dependencies
Upstream ist #2276 (live). Kein Eingriff ins Backend. Folge-Workflows: S2b Rahmen-/Reiter-Angleichung, S2c `?from=` für Compare.

### Open Questions
- [ ] (Spec, technisch) Folgt der Metrik-Pool des route-Zweigs (`trip.display_config.metrics`) im Anlege-Modus live der Auswahl im Reiter Wetter-Metriken, obwohl der Tab dauerhaft gemountet ist? In `/40` per Test festnageln. `stubTrip` muss dafür die gewählten Metriken tragen.
- Keine offene Produktfrage an den PO.
