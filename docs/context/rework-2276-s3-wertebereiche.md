# Kontext: Issue #2276 Scheibe S3 — Wertebereiche-Reiter speichert selbst

> Analyse-Dokument fuer `/30-write-spec`. Keine Implementierung, keine Spec-Datei.
> Workflow: `rework-2276-s3-wertebereiche` (Epic #2345, Issue #2276 bleibt offen bis S6).

## 0. Wichtigste Abweichung von der Auftragsannahme

Der Auftrag ging davon aus, der Wertebereiche-Reiter befinde sich heute im selben
Vor-S2-Zustand wie einst der Alarme-Reiter (reiner Wrapper-Sammel-Mechanismus,
kein `saveController.schedule()`). **Das stimmt nicht mehr.** Zwischen S2-Planung
und heute hat ein ANDERES Ticket (#2317 „Speicherung beim Neuladen", Baustein 2,
unabhaengig von Epic #2345) den `vergleich`-Zweig von `CorridorEditor(Mobile).svelte`
bereits teilweise auf `saveController.schedule()` umgestellt — aus einem anderen
Grund (Keepalive/`beforeNavigate`-Absicherung beim Verlassen der Seite, nicht aus
Epic #2345). Das Ergebnis ist kein sauberer Vor-Zustand, sondern ein **Hybrid**,
der GENAU an der Stelle bereits erkannt und dokumentiert ist:
`saveStatusStore.svelte.ts` Kommentar bei `markPristine()` (Issue #1703 S8):
„Eine Geste kann mehrere Commits ausloesen (direkter `onCompareCommit` + Wrapper-
Ereignis in CompareTabs.svelte)." — der Doppel-Commit-Pfad ist ein bekannter,
bewusst nicht behobener Nebeneffekt des heutigen Zustands.

S3 ist damit **kein Repeat von S2's Schnittmuster**, sondern zusaetzlich eine
**Entflechtung** von zwei redundanten Schreibpfaden zu einem einzigen — analog
zu dem, was S2 fuer Alarme bereits sauber erreicht hat.

## 1. Ist-Zustand (Datei:Zeile)

### 1.1 Zwei parallele Ausloese-Pfade fuer denselben PUT

`frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`
(analog `CorridorEditorMobile.svelte`, praktisch identische Struktur):

- **Pfad A — reaktiv aus dem Editor selbst:** `maybeSchedule()` (:217-235). Im
  `vergleich`-Zweig (:218-231): bei jeder `patch()`/`add()`/`remove()`-Aenderung
  wird zuerst `syncToWizard()` (:194-205) aufgerufen — schreibt reaktiv in die
  Svelte-Context-Runen `ws.corridors`/`ws.idealRanges`/`ws.activeMetricKeys`/
  `ws.metricAlertLevels` — und danach, wenn `saveGateDecision(rows) === 'schedule'`,
  `saveController?.schedule(async (init) => { await onCompareCommit?.(init); })`.
- **Pfad B — DOM-Ereignisse am Hub-Wrapper:**
  `frontend/src/lib/components/compare/CompareTabs.svelte:1331-1348` — der
  `.hub-corridor-wrap`-Div hat `onfocusout`/`onclick`, die `commitAusGeste()`
  (:433-435) aufrufen, was `handleCorridorCommit()` **direkt**, **ausserhalb**
  des `saveController`-Takts, ausloest. Zusaetzlich ein
  `<svelte:window onpointerup={handleWindowPointerUp}>` (:450-453), das ueber
  `shouldFlushOnWindowPointerUp()` (`compareHubWizardBridge.ts`) denselben
  `commitAusGeste()` ein drittes Mal ausloesen kann (Band-Drag-Release
  ausserhalb des Wrapper-Subtrees — genau das deckt
  `frontend/e2e/compare-hub-inline-edit.spec.ts:267-320` ab).

Beide Pfade fuehren letztlich zu `handleCorridorCommit`
(`frontend/src/lib/components/compare/korridorCommit.ts:36-71`, `baueKorridorCommit`),
das **selbst** `ctl.setSaving()/setSaved()/setError()` aufruft — **nicht** ueber
`saveController.doSave()`. Pfad A haengt es nur als Payload einer
`schedule()`-Huelle ein (der `SaveFn` selbst ruft am Ende wieder `handleCorridorCommit`
auf, das seinerseits `ctl.setSaving()` erneut aufruft — doppelte Zustandssetzung
im selben Vorgang). Das ist strukturell anders und schlanker geloest bei Alarme
(S2): dort gibt es **nur** Pfad A, kein Wrapper-Div, kein zweiter Ausloeser.

### 1.2 Speicherlogik liegt weiterhin in der Compare-Klebeschicht

- `flushPendingCorridorSave`, `snapshotForRollback`, `hydrateWizardStateFromPreset`,
  `createPutQueue` (Typ `PutQueue`) — alle in
  `frontend/src/lib/components/compare/compareHubWizardBridge.ts` (heute 683
  Zeilen, S2 hat bereits ~130 Zeilen Alarm-Anteil herausgezogen).
- `korridorCommit.ts` (72 Zeilen, aus #2317) ist bereits **Svelte-frei** und
  generisch (`KorridorCommitQuelle<S,P>`) — anders als die
  `flushPendingAlarmSave`-Vorgaengerfunktion ist das schon eine saubere,
  testbare Einheit. Sie liegt aber unter `compare/`, nicht unter `shared/` —
  ein Laufzeit-Import aus `shared/CorridorEditor.svelte` in eine `compare/`-Datei
  wuerde (wie bei Alarme vor S2) die Grenzregel „`shared/` importiert aus
  `compare/` nur Typen" verletzen. Aktuell **umgeht** `CorridorEditor.svelte`
  das, indem sie `korridorCommit.ts` NICHT importiert — es wird ausschliesslich
  von `CompareTabs.svelte` aufgerufen und der fertige `handleCorridorCommit`
  nur als `onCompareCommit`-Prop durchgereicht (kein Laufzeit-Import-Verstoss,
  aber die Orchestrierung sitzt eine Ebene hoeher als bei Alarme, wo sie
  komplett in `shared/alarmeVergleichSpeicherung.ts` steckt).
- Zustandshaltung in `CompareTabs.svelte`: `wizardState` (Svelte-Context,
  :333-334), `lastPersistedCorridorSnapshot`/`currentCorridorSnapshot()`
  (:336-356), Hydration `hydrateIdealwerteTab()` (:364-377, wartet auf
  `loadCompareSelectionEntries()`), `$effect` fuer Lazy-Hydration beim ersten
  Tab-Besuch (:379-385).

### 1.3 `preset`/`enqueueHubWrite`/`onCompareUpdate` fehlen bislang als Props

Anders als `AlarmeTab` (nimmt `preset`, `enqueueHubWrite`, `onCompareUpdate` als
Props entgegen, S2) bekommt `CorridorEditor`/`CorridorEditorMobile` heute NUR
`context`, `saveController`, `onCompareCommit` (:39-49 in `CorridorEditor.svelte`).
Die eigentliche Preset-Basis, die Queue und die Rueckmeldung bleiben vollstaendig
in `CompareTabs.svelte`/`korridorCommit.ts` verdrahtet — der Organism selbst hat
keinen Bezug zur Preset-Entitaet, nur zum Svelte-Context `ws`.

### 1.4 Cross-Tab-Kopplung: `wiz.metricAlertLevels` wird von ZWEI Reitern beschrieben

`AlarmeTab.svelte:220-227` (`handleMetricLevelChange`, vergleich-Zweig) schreibt
`wiz.metricAlertLevels` direkt. `CorridorEditor.svelte` liest es nur einmalig
als `originalLevels` (:56-60, zum Erkennen entfernter Metriken) und schreibt es
ueber `syncToWizard()` (:199-204) bei jeder Wertebereich-Aenderung zurueck (u. a.
um entfernte Metriken auf `"off"` zu setzen — `buildCompareCorridorSavePayload`).
Beide Reiter teilen sich also **dasselbe** Feld auf demselben `wizardState`-Objekt.
Das funktioniert heute nur, weil beide PUTs seriell durch dieselbe `hubPutQueue`
laufen und ihre jeweilige Nutzlast **live** aus `wiz` zum Ausfuehrungszeitpunkt
lesen (nicht aus einem beim Planen eingefrorenen Wert) — dasselbe Prinzip wie
AC-3 in der S2-Spec. Eine neue `wertebereicheVergleichSpeicherung.ts` MUSS diese
Lese-bei-Ausfuehrung-Eigenschaft fuer `metricAlertLevels` **explizit** erhalten,
sonst verliert das Entfernen einer Metrik-Zeile die "off"-Markierung, sobald sie
zeitgleich mit einer Alarm-Aenderung im selben Hub-Besuch landet (siehe Risiko 4).

### 1.5 `context ===`-Verzweigungen (Stand heute, fuer AC-2 des Epics)

`CorridorEditor.svelte`: 12 Vorkommen (:51, 57, 67, 73, 218, 250, 284, 297, 300,
306, 327, 456). `CorridorEditorMobile.svelte`: analog 12. Fachlich (bleiben nach
S3 bestehen): Prefill-aus-Aktivitaetsprofil bei Compare-Neuanlage (:69-79, nur
sinnvoll fuer Vergleich), Ladezustand fuer den Compare-Metrikkatalog (:110-132,
297-304, 327-339 — der `route`-Zweig hat einen eigenen, synchronen Katalog),
`supportsMark()`/Neutralitaets-Hinweis (:456-467, C1-Entscheidung „kein Score
im Vergleich"). NICHT fachlich, sondern reiner Speicherweg-Unterschied und faellt
mit S3: die `context === 'vergleich'`-Verzweigung in `maybeSchedule()` (:218-231,
`syncToWizard()` + `schedule(onCompareCommit)` statt `schedule(buildSaveFn())`) —
das ist die eine Verzweigung, die durch eine dedizierte
`wertebereicheVergleichSpeicherung.ts`-Orchestrierung ersetzt werden soll (ANALOG
zu Alarme, NICHT identisch, weil `ws` als Wertquelle bleibt — s. Abschnitt 2).

## 1.6 Fakten aus `saveStatusStore.svelte.ts` (`schedule`/`flush`/`cancel`, :181-249)

Nachgelesen, nicht mehr Annahme:

- **`_pendingFn` ist ein EINZIGER Slot pro `SaveStatus`-Instanz**, nicht eine
  Queue. `schedule(saveFn)` ueberschreibt ihn **unbedingt** (:184-189, plus
  Timer-Reset) — ein zweiter `schedule()`-Aufruf eines ANDEREN Aufrufers
  verwirft den vorherigen `_pendingFn` kommentarlos, wenn dieser noch nicht
  gefeuert hat. Genau das beschreibt der Kommentar in `AlarmeTab.svelte:308-314`
  fuer den route-Zweig als vermiedene Gefahr.
- **`flush(init?)`** (:196-202) fuehrt IMMER den aktuell in `_pendingFn`
  stehenden Save sofort aus (Timer-Cancel + `doSave()`), unabhaengig davon,
  welcher Reiter ihn dort abgelegt hat.
- **`schedule()` setzt sofort `setSaving()`**, der Debounce betraegt 700ms
  Default. Der Handle-Drag-Regressionstest
  (`compare-hub-inline-edit.spec.ts:293-310`) wartet mit `page.waitForResponse`
  OHNE verkuerztes Timeout auf den PUT — das 700ms-Fenster ist also toleriert,
  **kein** sofortiges Feuern noetig. Damit ist Abschnitt 2 Punkt 5 auflösbar:
  der `<svelte:window onpointerup>`-Handler in `CompareTabs.svelte` kann bei
  vollstaendiger Umstellung auf `schedule()`-basierte Persistenz **ersatzlos
  entfallen** (Debounce feuert unabhaengig vom DOM-Subtree, in dem der Pointerup
  stattfindet) — keine Restkomponente noetig, kein Vorbehalt mehr.

## 1.7 Neues Risiko durch S3: zwei Selbst-Speicherer auf EINEM `SaveStatus`-Slot

Nach S3 planen **zwei** Reiter (`AlarmeTab`, `CorridorEditor(Mobile)`) im
`vergleich`-Kontext auf denselben, von der Route mitgegebenen `saveController`
(:120-125 in `CompareTabs.svelte`) — und dieser hat, s. 1.6, nur EINEN
`_pendingFn`-Slot. Ein Nutzer, der im Wertebereiche-Reiter etwas aendert
(Slot belegt mit der Corridor-SaveFn) und **innerhalb der 700ms** in den
Alarme-Reiter wechselt und dort ebenfalls etwas aendert, wuerde ohne einen
Flush beim Verlassen des Wertebereiche-Reiters die Corridor-Aenderung
**stillschweigend verlieren** — der zweite `schedule()`-Aufruf ueberschreibt
den ersten.

**Bereits vorhandene Absicherung, aber nur fuer EINEN Reiter:**
`sichereAlarmeVorReiterwechsel(aktiverReiter, zielReiter, saveController)`
(`alarmeVergleichSpeicherung.ts:241-248`) flusht ausschliesslich beim
Verlassen von `'alarme'`. S3 braucht die spiegelbildliche Absicherung beim
Verlassen von `'idealwerte'`.

**Vorbild fuer die richtige Form liefert der Trip, nicht der bisherige
Compare-Ansatz:** `TripTabs.svelte:145-176` loest das GENERISCH — EIN Guard,
der bei Verlassen JEDES der bekannten Selbst-Speicher-Reiter
(`'alerts' | 'weather' | 'briefings' | 'alarme' | 'stages'`) flusht, sofern
`saveController?.hasPending` wahr ist, unabhaengig davon, WELCHER dieser
Reiter den Slot zuletzt belegt hat. Das ist robust gegen genau die Kollision
oben und skaliert automatisch auf einen dritten/vierten Selbst-Speicherer
(S4/S5), ohne dass fuer jeden neuen Reiter eine weitere dedizierte
`sichereXVorReiterwechsel`-Funktion entsteht. **Empfehlung fuer die Spec:**
`sichereAlarmeVorReiterwechsel`/eine neue `sichereWertebereicheVorReiterwechsel`
in `CompareTabs.handleValueChange` durch EINEN generischen, listenbasierten
Guard ersetzen (Trip-Muster), statt eine zweite, fast identische
Einzelreiter-Funktion danebenzustellen. Das ist selbst KEIN Verstoss gegen die
Pendant-Sperre (Trip-Pendant existiert ja schon, es ist die Prop-Form, die
divergiert), sondern deren praezise Anwendung.

**Reachability bestaetigt (kein theoretisches Risiko):** der Timer lebt auf der
`SaveStatus`-Instanz der Route (`routes/compare/[id]/+page.svelte`), NICHT auf
der Tab-Komponente — ein Reiter-Wechsel unmountet `AlarmeTab`/`CorridorEditor`,
aber der `_pendingFn`/Timer bleibt am Controller bestehen und ist fuer den
naechsten `schedule()`-Aufruf eines ANDEREN, frisch gemounteten Reiters
erreichbar. Ohne Flush-Guard ist das Verlustszenario echt auslösbar, nicht nur
hypothetisch.

**Zaehlung der „Bewusste Abweichungen" fuer die S3-Spec:** S2 dokumentierte
„gemischter Controller-Betrieb bis S3–S6" als 1 Selbst-Speicherer (Alarme) +
5 direkt `setSaving()`/`setSaved()`-aufrufende Reiter. Nach S3 sind es 2
Selbst-Speicherer (Alarme, Wertebereiche) + 4 direkte Aufrufer — die
Ueberdeckungs-Gefahr aus S2s Risiko 6 (ein ausstehender `schedule()` kann
optisch von einem direkten Aufruf ueberdeckt werden) bleibt bestehen und sollte
in der S3-Spec mit aktualisierter Zaehlung fortgeschrieben werden, nicht neu
hergeleitet.

## 1.8 Hydration-Reihenfolge als Korrektheitsvoraussetzung (nicht nur Performance)

Die `erstelleAlarmeVergleichSpeicherung`/analoge Wertebereiche-Orchestrierung
darf ERST NACH der Hydration erzeugt werden (`untrack()`-Konstruktion in
`AlarmeTab.svelte:366-377`, Bedingung `context === 'vergleich' && wiz && preset
&& saveController` — bei Wertebereiche zusaetzlich `idealwerteHydrated`, analog
zum bestehenden `{#if idealwerteHydrated}`-Gate in `CompareTabs.svelte:1330`).
Wird die Baseline VOR der Hydration genommen, diffed jede erste Nutzerinteraktion
gegen einen leeren/falschen Ausgangswert — ein starker Mutations-Kandidat fuer
den Adversary (Gate entfernen ⇒ falscher Diff bei der ersten Aenderung nach
Laden). Zusaetzliche Verzahnung: `hydrateAlarmFieldsFromPreset`
(bleibt in der Klebeschicht, s. Abschnitt 1.4) setzt ebenfalls
`corridors`/`activeMetricKeys` — ein Wechsel Wertebereiche→Alarme ist nur
deshalb unkritisch, WEIL der neue Flush-Guard (1.7) die Wertebereiche-Aenderung
vorher abschliesst, nicht weil die beiden Hydrationsfunktionen einander
inhaltlich kennen.

## 1.9 Geltungsbereich der AC-9-Analogie (Laufzeit-Import-Grenze)

S2s AC-9 verbietet praezise NUR den Laufzeit-Import aus
`compareHubWizardBridge.ts` — nicht aus `compare/` insgesamt.
`alarmeVergleichSpeicherung.ts:20` importiert zur Laufzeit bewusst
`buildComparePresetSavePayload` aus `../compare/compareEditorSave.ts` (bleibt
laut S2-Spec „unveraendert... wird vom neuen Alarm-Zweig weiter als
Nutzlast-Baustein verwendet"). Die neue `wertebereicheVergleichSpeicherung.ts`
braucht denselben Import fuer dieselbe Funktion — das ist **kein** Verstoss
gegen die Grenzregel und sollte in der Spec mit demselben engen Wortlaut wie
S2 formuliert werden („kein Laufzeit-Importeur von `compareHubWizardBridge.ts`
mehr", nicht „kein Laufzeit-Importeur aus `compare/`").

## 2. Zielbild fuer S3

**Wichtiger Unterschied zu Alarme:** Bei Alarme lesen/schreiben route UND
vergleich exklusiv ueber Reiter-eigene Felder (route: lokaler `$state`, vergleich:
`wiz.*`) — der Organism selbst haelt gar keinen fuer beide Kontexte gemeinsamen
Zustand. Bei Wertebereiche ist `rows`/`poolLeft` (der eigentliche UI-Zustand)
bereits **kontextuebergreifend gemeinsam** (`$state` im Organism, unabhaengig von
`context`) — `ws` dient nur als **Ausgangswert/Ziel-Spiegel** fuer den
vergleich-Zweig. Das S2-Muster „Organism liest/schreibt Vergleichsfelder aus dem
Context, aber PERSISTIERT ueber `preset`+`saveController`+`enqueueHubWrite`" passt
trotzdem 1:1 — nur dass hier NICHT `alarmSnapshotAus(wiz)` das Aequivalent ist,
sondern ein neues `corridorSnapshotAus(ws)`, das dieselben vier Felder liest, die
`syncToWizard()` heute schreibt (`corridors`, `idealRanges`, `activeMetricKeys`
materialisiert, `metricAlertLevels`).

Zielarchitektur (Vorbild `alarmeVergleichSpeicherung.ts` +
`erstelleAlarmeVergleichSpeicherung`):

1. Neues Modul `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts`
   (bewusst NICHT `shared/` Top-Level, sondern im bestehenden
   `corridor-editor/`-Unterordner, Analogie zu `corridorEditorState.ts` daneben):
   - `type CorridorSnapshot` (die vier o.g. Felder, JSON-Roundtrip wie
     `AlarmSnapshot`).
   - `corridorSnapshotAus(ws)`.
   - `baueWertebereichNutzlast(preset, current)` — **Voll-Spread** ueber
     `buildComparePresetSavePayload` (identische Begruendung wie S2 Design-
     Entscheidung 2: `display_config` wird vom Go-Merge-Kernel nur auf Ebene 1
     gemerged, ein Teil-PUT waere ein Verlustpfad sobald ein Nachbar-Reiter im
     selben Zyklus denselben Ebene-1-Schluessel schreibt — bei Wertebereiche
     UND Alarme ist das exakt `metric_alert_levels`, s. Abschnitt 1.4).
     `metricAlertLevels` MUSS aus `current.metricAlertLevels` (live `ws`-Wert),
     NICHT aus `preset.display_config.metric_alert_levels` befuellt werden —
     sonst geht die „entfernte Metrik → off"-Zusicherung verloren.
   - `flushPendingCorridorSave2(preset, current, before)` (Namensvorschlag,
     endgueltiger Name in der Spec: bestehende `flushPendingCorridorSave` in
     `compareHubWizardBridge.ts` wird durch diese Variante ersetzt/verschoben).
   - `rollbackCorridorSnapshot(ws, before, attempted)` — Diff-basiert wie bei
     Alarme (Feld nur zuruecksetzen, wenn `ws` noch exakt den gescheiterten Wert
     traegt — sonst ueberschreibt ein Rollback einen zwischenzeitlichen
     Alarme-Edit an `metricAlertLevels`).
   - `erstelleWertebereicheVergleichSpeicherung(opt)` — identische Form wie
     `erstelleAlarmeVergleichSpeicherung`: `{client, ws, preset: () => ..., 
     enqueueHubWrite, onCompareUpdate, saveController}` → `{aenderungMelden()}`.
   - `sichereWertebereicheVorReiterwechsel(aktiverReiter, zielReiter, saveController)`
     analog `sichereAlarmeVorReiterwechsel` fuer `handleValueChange`.
2. `CorridorEditor.svelte`/`CorridorEditorMobile.svelte`: neue Props `preset`,
   `enqueueHubWrite`, `onCompareUpdate` (Signatur exakt wie bei `AlarmeTab`).
   `maybeSchedule()`'s vergleich-Zweig ruft nach `syncToWizard()` NICHT mehr
   `saveController?.schedule(async (init) => onCompareCommit?.(init))`, sondern
   meldet die Aenderung an die neue Orchestrierung (`vergleichSpeicherung.aenderungMelden()`,
   erzeugt einmalig via `untrack()` wie bei `AlarmeTab.svelte:366-377`). Das
   `onCompareCommit`-Prop entfaellt komplett.
3. `CompareTabs.svelte`: `.hub-corridor-wrap`-Div (:1331-1348, `onfocusout`/
   `onclick`/`commitAusGeste`), `handleWindowPointerUp`/`shouldFlushOnWindowPointerUp`-
   Aufruf (:450-453), `handleCorridorCommit`/`baueKorridorCommit`-Aufruf (:408-435),
   `currentCorridorSnapshot`/`lastPersistedCorridorSnapshot` (:336-356) entfallen.
   `handleValueChange()` bekommt einen zusaetzlichen Flush-Aufruf fuer den Reiter
   `idealwerte` (Muster :156, `sichereAlarmeVorReiterwechsel` → analog
   `sichereWertebereicheVorReiterwechsel`). `handleToggleActive()` (:916-935)
   braucht einen zusaetzlichen `flush()`-Vorlauf wie bei S2, falls das nicht
   schon generisch ueber `saveController.flush()` (:921, bereits vorhanden — zu
   pruefen ob das ALLE ausstehenden `schedule()`-Eintraege trifft oder nur den
   zuletzt gesetzten, s. Risiko 6).
4. `korridorCommit.ts` und die `flushPendingCorridorSave`/`snapshotForRollback`-
   Altfunktionen in `compareHubWizardBridge.ts` werden entfernt, sofern kein
   anderer Verwender uebrig bleibt (`snapshotForRollback` wird generisch von
   mehreren Snapshot-Typen genutzt — pruefen, ob Versand/Layout sie noch
   brauchen, bevor sie geloescht wird; vermutlich JA, dann bleibt die generische
   Hilfsfunktion, nur der Corridor-spezifische Aufrufer faellt weg).
5. **`.hub-corridor-wrap`-Wrapper-Markup faellt vollstaendig weg** (bestaetigt,
   s. Abschnitt 1.6 — kein Vorbehalt mehr). Test
   `compare-hub-inline-edit.spec.ts:267-320` (Band-Drag-Release ausserhalb des
   Wrapper-Subtrees) wartet ueber `page.waitForResponse` ohne verkuerztes
   Timeout auf den PUT — das 700ms-Debounce-Fenster von
   `saveController.schedule()` ist toleriert, das Ergebnis haengt nicht vom
   DOM-Subtree ab, in dem der Pointerup stattfindet. Der Test muss danach
   unveraendert gruen bleiben, ohne dass es noch einen Wrapper oder einen
   `<svelte:window onpointerup>`-Handler gibt.

## 3. Scoping

| Datei | Aenderungsart | Grobschaetzung |
|---|---|---|
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | NEU | +180 |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | AENDERN (Props, `maybeSchedule` vergleich-Zweig) | +25/-15 |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | AENDERN (identisch zu Desktop) | +25/-15 |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | AENDERN (Wrapper-Div raus, Mount-Props, `handleValueChange`/`handleToggleActive` Flush) | +20/-90 |
| `frontend/src/lib/components/compare/korridorCommit.ts` | LOESCHEN | -72 |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | AENDERN (`flushPendingCorridorSave` raus, `snapshotForRollback`/`hydrateWizardStateFromPreset`-Verwendung pruefen) | -40 |
| Testdateien (neu + umgehaengt, Muster S2: `compare_hub_alarme_bridge.test.ts`-Analogon) | NEU/UMZUG | +180 |
| `frontend/e2e/compare-wertebereiche-speichert-selbst.spec.ts` | NEU (Muster `compare-alarme-speichert-selbst.spec.ts`) | +150 (zaehlt nicht in LoC-Limit, E2E) |

**Kern-LoC-Schaetzung (ohne E2E, ohne reine Testverschiebung):** ≈ +250/-230 →
liegt knapp am 250er-Limit, S2 brauchte `loc_limit_override 500` bei aehnlichem
Zuschnitt (S3 hat zusaetzlich zwei Dateien Loeschung/Rueckbau, tendenziell mehr
Diff als S2). **Empfehlung: `loc_limit_override 500` gleich zu Workflow-Beginn
setzen**, wie bei S2 dokumentiert.

**Effort/Risk wie S2: HIGH** — Persistenzflaeche, zusaetzlich die Entflechtung
zweier bestehender Schreibpfade (Mutations-Risiko: eine Verfaelschung koennte
den Wrapper-Pfad entfernen, ohne dass ein Test es merkt, wenn der neue
alleinige Pfad zufaellig denselben Effekt hat wie einer der beiden alten Pfade
im Gluecksfall — Adversary MUSS beide historischen Pfade gezielt einzeln
ausschalten und pruefen, dass jeweils ein spezifischer Test rot wird).

## 4. Risiken (Delta zu S2)

1. **Doppel-Commit-Regression unsichtbar, wenn nur EIN Pfad getestet wird.**
   Der dokumentierte Zwei-Pfad-Zustand (Abschnitt 1.1) heisst: ein Adversary-
   Test, der nur Pfad A (reaktiv) prueft, kann nicht zeigen, dass Pfad B
   (Wrapper-Div) tatsaechlich entfernt wurde. Mutations-Gegenprobe MUSS beide
   Ausloeser einzeln reaktivieren/entfernen.
2. **`metricAlertLevels`-Kreuzkopplung mit Alarme (Abschnitt 1.4).** Ein Test,
   der eine Wertebereich-Aenderung UND eine Alarm-Aenderung im selben
   Hub-Besuch (zwei echte Reiterklicks) verschraenkt schreiben laesst, ist
   Pflicht — Muster AC-3 in `rework_2276_s2_alarme.md`, aber diesmal
   *zwischen zwei verschiedenen Modulen*, nicht nur innerhalb eines Moduls.
3. **Datenerhalt bei entfernten Metriken (F002/F003, historisch Adversary
   CRITICAL/HIGH in #1258 S4).** `removedMetrics`/`unknownCorridors` (Pass-
   Through-Korridore ausserhalb des Katalogs) duerfen durch die neue
   Voll-Spread-Payload nicht verloren gehen — bestehende Tests
   (`corridorEditorCapeExclusion.test.ts`? pruefen) muessen weiterhin greifen,
   ggf. am neuen Modul statt an `compareHubWizardBridge.ts` haengend.
4. **Band-Drag-Release ausserhalb des Wrapper-Subtrees** (Risiko/Regression,
   Abschnitt 2 Punkt 5) — konkret abgesichert durch
   `compare-hub-inline-edit.spec.ts:267-320`, MUSS nach Wrapper-Entfernung ohne
   Aenderung des Testcodes weiterhin gruen sein (sonst ist die Verhaltens-
   Neutralitaet verletzt).
5. **`handleToggleActive()` (Pausieren/Aktivieren)** muss eine ausstehende
   Wertebereich-Aenderung vor dem PUT flushen — genau das Muster, das bei
   Alarme zum Folgefund #2366 gefuehrt hat (Pausieren/Aktivieren ueberschreibt
   einen 412-Konflikt mit „Gespeichert"). **Diese Scheibe uebernimmt NICHT**
   die Reparatur von #2366 (gehoert laut Issue-Kommentar zur
   Aktiv-Schalter-Scheibe), sollte aber nicht denselben Fehler ein zweites Mal
   fuer Wertebereiche neu einfuehren, ohne ihn zu dokumentieren.
6. **Pendant-Frage (geteilter Baustein):** `CorridorEditor`/`CorridorEditorMobile`
   werden bereits von Trip UND Vergleich geteilt — die neue
   `wertebereicheVergleichSpeicherung.ts` ist WIE `alarmeVergleichSpeicherung.ts`
   bewusst NUR fuer den vergleich-Zweig (kein Pendant im Trip noetig, weil der
   Trip-Zweig `buildSaveFn()`/`baueTripSpeicherung` bereits hat und unveraendert
   bleibt) — kein Verstoss gegen die Pendant-Sperre, aber in der Spec explizit
   zu begruenden (wie bei S2 in „Architektur-Entscheidung (ADR)").
7. **Cross-User/Mandantentrennung:** unveraendert gegenueber S2 (kein neuer
   Endpoint, `preset`/`api.put` unveraendert) — kein neues Risiko, aber wie
   immer mit zwei Nutzern gegenzupruefen, falls ein neuer Endpoint-Zweig
   entstuende (nicht erwartet).
8. **`korridorCommit.ts`-Loeschung koennte einen uebersehenen zweiten Verwender
   haben** — vor dem Loeschen `git grep -rn "korridorCommit\|baueKorridorCommit"`
   pruefen (aktuell nur `CompareTabs.svelte` als Importeur bekannt).
9. **Geteilter Ein-Slot-`saveController` zwischen Alarme und Wertebereiche
   (NEU durch S3, Abschnitt 1.7, HOCH).** `_pendingFn` haelt genau EINEN
   ausstehenden Save; ein `schedule()`-Aufruf aus dem jeweils anderen Reiter
   ueberschreibt ihn kommentarlos. Reachability bestaetigt: der Slot lebt auf
   der Route-Instanz, nicht auf der Tab-Komponente, ueberlebt also den Unmount
   beim Reiterwechsel. Pflicht-Gegenmassnahme: ein generischer Flush-Guard
   (Trip-Muster, `TripTabs.svelte:145-176`) beim Verlassen JEDES
   Selbst-Speicher-Reiters (`'alarme'`, `'idealwerte'`), nicht zwei getrennte
   `sichereXVorReiterwechsel`-Funktionen. Adversary-Mutation: Flush-Guard fuer
   `'idealwerte'` weglassen ⇒ Test mit Wertebereich-Aenderung + schnellem
   Wechsel zu Alarme + Alarm-Aenderung muss die verlorene Wertebereich-Aenderung
   zeigen.

## 5. Offene Punkte — mitnehmen oder bewusst nicht

- **#2366** (Pausieren/Aktivieren ueberschreibt 412-Konflikt) — **NICHT** Teil
  von S3 (gehoert zur Aktiv-Schalter-Scheibe laut Issue-Kommentar), aber Risiko 5
  oben zeigt: S3 sollte den gleichen Fehler nicht zusaetzlich fuer Wertebereiche
  neu einfuehren. Keine Reparatur, nur Vorsicht beim Bauen.
- **#1199 F008/F009/F010** (S2-Nebenbefunde: doppelte Feldliste, Nachspeicher-
  Schleife ohne Obergrenze, kurzzeitig falscher `hasPending`) — bleiben im
  Sammel-Issue, S3 muss sie nicht mitloesen, sollte sie aber nicht fuer den
  Wertebereiche-Pfad NEU einfuehren (dieselbe `for(;;)`-Nachschiebe-Schleife aus
  `erstelleAlarmeVergleichSpeicherung` als Vorbild uebernimmt strukturell
  denselben F009-Kandidaten — falls die Vorlage 1:1 kopiert wird, gilt der
  bestehende Sammel-Eintrag automatisch mit, kein neues Ticket noetig).
- **#2317/„Speicherung beim Neuladen"** — die Keepalive-Absicherung
  (`init`-Weiterreichung), die dieses Ticket fuer den Corridor-Pfad eingefuehrt
  hat, MUSS erhalten bleiben (analog AC-10 in S2). `korridorCommit.ts`s
  `init`-Parameter-Durchreichung ist das Vorbild, nicht wegzuwerfen, sondern in
  die neue `saveFn`-Signatur zu uebernehmen (wie bei `erstelleAlarmeVergleichSpeicherung`s
  `saveFn: SaveFn = async (init) => ...`).
- **Reine Layout-/Anlege-Seite (`/compare/new`)** bleibt unberuehrt — dort
  mountet `CorridorEditor` ohne `preset`/`saveController` (Anlege-Fluss ueber
  `wiz.saveNewPreset()`), das neue Prop-Trio bleibt dort strukturell inaktiv
  wie bei S2 (AC-7-Analogon).

## 6. Angenommene, nicht durch PO bestaetigte Entscheidungen

- **Modulname/-ort:** `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts`
  (statt `shared/wertebereicheVergleichSpeicherung.ts` auf oberster Ebene wie
  bei Alarme) — Begruendung: Wertebereiche hat bereits einen eigenen Unterordner
  mit mehreren Modulen (`corridorEditorState.ts`, `corridorMatch.ts`,
  `compareMetricCatalogLoader.ts`); Konsistenz mit bestehender Ordnerstruktur
  wiegt hoeher als 1:1-Namensanalogie zu Alarme. **Kann in der Spec-Phase
  korrigiert werden, wenn PO/Spec-Writer anders entscheiden.**
- **`korridorCommit.ts` wird vollstaendig geloescht, nicht nur entkoppelt** —
  Annahme, dass kein anderer Aufrufer existiert (Abschnitt 4, Risiko 8: mit
  `git grep` vor der Implementierung zu verifizieren, nicht vorab zu behaupten).
- **Der Wrapper-Pointerup-Handler entfaellt vollstaendig** (Abschnitt 1.6/2
  Punkt 5) — belegt durch das tolerante `waitForResponse`-Timeout im
  bestehenden E2E-Test, kein offener Vorbehalt mehr.
- **Flush-Guard beim Reiterwechsel wird generisch (Trip-Muster) statt
  reiter-spezifisch** (Abschnitt 1.7, Risiko 9) — Annahme, dass
  `/30-write-spec` `sichereAlarmeVorReiterwechsel` mit umbaut statt eine zweite,
  fast identische Funktion fuer `'idealwerte'` danebenzustellen. Fachlich
  gleichwertig, nur die Umsetzungsform ist eine Empfehlung dieser Analyse.
