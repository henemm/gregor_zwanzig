---
entity_id: issue_1395_s4_conflict_retry
type: module
created: 2026-07-31
updated: 2026-07-31
status: draft
version: "1.0"
tags: [frontend, svelte, trip, etag, if-match, concurrency, save-status]
---

<!-- Issue #1395 Scheibe S4 — Nochmal speichern (Retry bei ETag-Konflikt) -->

# Issue #1395 Scheibe S4 — Nochmal speichern (Retry bei ETag-Konflikt)

## Approval

- [ ] Approved

## Purpose

S3 hat den `412`-Konflikt real gemacht — er wird ausgeloest, sobald zwei
Schreibvorgaenge auf dieselbe Tour ohne Absprache aufeinandertreffen — aber
am Speicher-Anzeiger sieht ihn der Nutzer heute wie jeden anderen Fehler:
`'error'` mit deutscher Servermeldung und sonst nichts. Es gibt keinen Weg
zurueck ausser Seite neu laden und die Aenderung von Hand wiederholen. Diese
Scheibe gibt dem Konflikt einen eigenen Zustand (`'conflict'`) und einen
Ausweg direkt am Anzeiger: ein "Nochmal speichern"-Knopf, der zuerst den
veralteten Stand in der ETag-Registry auffrischt und danach automatisch
denselben Speichervorgang wiederholt, den der Nutzer ohnehin schon ausgeloest
hatte — ohne dass er etwas erneut eingeben oder die Seite neu laden muss.

## Source

- **File:** `frontend/src/lib/stores/saveStatusStore.svelte.ts` — `SaveState`
  um `'conflict'` erweitert; `SaveStatus` bekommt optionalen
  `tripId`-Konstruktorparameter, merkt sich bei `412` den fehlgeschlagenen
  Speichervorgang und stellt `retryConflict()` bereit
- **File:** `frontend/src/lib/api.ts` — neue Funktion `refreshTripEtag(tripId)`
- **File:** `frontend/src/lib/components/ui/SaveIndicator.svelte` — neuer
  `'conflict'`-Zweig mit Wiederholen-Knopf
- **File:** `frontend/src/routes/trips/[id]/+page.svelte` —
  `createSaveStatus()` → `createSaveStatus(trip.id)`

> **Schicht-Hinweis:** ausschliesslich Frontend (`frontend/src/...`,
> SvelteKit). Kein Go-, kein Python-Code betroffen — der Server-Vertrag
> (`412`, `ETag`-Header) ist seit S2 fertig und wird von dieser Scheibe nur
> konsumiert.

## Estimated Scope

- **LoC:** ~290 von 600 freigegebenen Zeilen (siehe „Zeilenrahmen")
- **Files:** 4 Produktivdateien (alle geaendert, keine neue), 3 neue Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/etag.go` + `GET/PUT /api/trips/{id}`-Vertrag (S2) | HTTP-Vertrag | Liefert den `412`-Statuscode, den diese Scheibe als eigenen UI-Zustand behandelt |
| `frontend/src/lib/etagRegistry.ts` (S3) | TS-Modul | Bleibt in dieser Scheibe UNVERAENDERT — `refreshTripEtag()` nutzt ausschliesslich den bereits vorhandenen Seiteneffekt (`setKnownEtagIfUnchanged` bei jedem erfolgreichen GET auf einen Trip-Pfad) |
| `frontend/src/lib/api.ts` (S3) | TS-Modul | Trichter, dessen bestehende ETag-Capture-Logik den Refresh traegt; `refreshTripEtag()` ist ein duenner Wrapper darauf |
| `frontend/src/lib/types.ts` (S3) | TS-Modul | `ApiError.status?: number` — in S3 EXTRA fuer S4 vorbereitet, um `412` von anderen Fehlern zu unterscheiden (s. S3-Spec, Abschnitt „Was S4/S5/S6 erben") |
| `docs/specs/modules/issue_1395_s3_etag_registry.md` | Spec | Direkter Vorlaeufer, definiert den Trichter und die Registry, auf denen diese Scheibe aufbaut |
| `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md` | ADR | Grundsatzentscheidung, auf der S2–S4 aufbauen — kein neues ADR noetig |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/api.ts` | MODIFY | + `refreshTripEtag(tripId)` — duenner Wrapper um `api.get(\`/api/trips/${tripId}\`)`, Rueckgabewert verworfen |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | MODIFY | `SaveState` + `'conflict'`; Konstruktorparameter `tripId?: string`; `_lastFailed`-Feld; `doSave()`-Catch-Zweig unterscheidet `412` von generischen Fehlern; neue Methode `retryConflict()` |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | MODIFY | Neuer `'conflict'`-Zweig: Servermeldung + Button „Nochmal speichern" (`onclick={() => controller.retryConflict()}`) |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | `createSaveStatus()` → `createSaveStatus(trip.id)` (eine Zeile) |
| `frontend/src/lib/stores/__tests__/saveStatusConflictRetry.test.ts` | CREATE | Store-Transitions: `'conflict'`-Eintritt, Retry-Ablauf, Re-Konflikt, Ohne-`tripId`-Rueckfall |
| `frontend/src/lib/__tests__/apiRefreshTripEtag.test.ts` | CREATE | `refreshTripEtag()`: nutzt bestehenden Trichter, Rueckgabewert wird nicht weitergereicht, aktualisiert Registry ueber den bestehenden GET-Seiteneffekt |
| `frontend/src/lib/components/ui/__tests__/saveIndicatorConflictBranch.test.ts` | CREATE | Quelltext-Verhaltenspruefung (kein Svelte-5-Runen-Render-Harness im `node:test`-Setup, Praezedenz `weatherMetricsTabDayWindowSave.test.ts`): Konflikt-Zweig hat Button, Fehler-Zweig hat KEINEN |

### Estimated Changes

- Files: 7 (4 Produktiv, 3 Tests)
- LoC: +290/-10 (Schaetzung, siehe „Zeilenrahmen")

## Implementation Details

### `'conflict'` als eigener Zustand — nicht als Sonderfall von `'error'`

`SaveState` wird zu `'idle' | 'dirty' | 'saving' | 'error' | 'conflict'`. Ein
zusaetzliches Bool-Flag neben `error` (z. B. `isConflict: boolean`) waere
technisch aequivalent, macht aber jede bestehende `if (state === 'error')`-
Verzweigung in Aufrufern (u. a. `SaveIndicator.svelte`) zu einer stillen Falle
— sie muesste zusaetzlich das Flag pruefen, sonst zeigt sie bei einem Konflikt
weiterhin den generischen Fehlertext ohne Knopf. Ein eigener `state`-Wert
zwingt jede Konsumentenstelle, sich explizit zu entscheiden, wie sie damit
umgeht (TypeScript kennt beide Zustaende, `switch`/`if`-Ketten ohne
`'conflict'`-Zweig faellt fuer diesen Fall einfach durch, statt fehlzuraten).

### `doSave()` unterscheidet `412` von generischen Fehlern

Der bestehende Catch-Zweig (`this.setError(extractMessage(e))`) wird um eine
Vorpruefung ergaenzt:

```ts
catch (e) {
  const status = (e as ApiError)?.status;
  if (status === 412 && this._tripId) {
    this._lastFailed = { fn: saveFn, init };
    this.state = 'conflict';
    this.error = extractMessage(e);
  } else {
    this.setError(extractMessage(e));
  }
}
```

Wichtig: Dieser Zweig sitzt in `doSave()` selbst, nicht nur in
`retryConflict()`. Damit gilt dieselbe Logik fuer den urspruenglichen
fehlgeschlagenen Speichervorgang UND fuer einen erneuten `412` waehrend eines
Retries (`retryConflict()` ruft am Ende wieder `doSave()` auf) — kein
zweiter, abweichender Code-Pfad noetig. Das ist der Mechanismus, der AC-3
traegt: der Retry laeuft durch dieselbe Fehlerbehandlung wie jeder andere
Speichervorgang und landet bei erneutem `412` wieder sauber in `'conflict'`,
mit dem NEUEN `saveFn`/`init` als `_lastFailed` (identisch mit dem alten,
aber frisch gemerkt).

Ohne `this._tripId` (Instanz ohne Konstruktor-Argument, s. u.) faellt jeder
`412` in den generischen `else`-Zweig — Verhalten exakt wie vor dieser
Scheibe (AC-6).

### `retryConflict()` — Reihenfolge und Wiedereintritts-Schutz

```ts
async retryConflict(): Promise<void> {
  if (this.state !== 'conflict' || !this._lastFailed || !this._tripId) return;
  const { fn, init } = this._lastFailed;
  this._lastFailed = null;
  this.setSaving(); // verlaesst 'conflict' SOFORT — sperrt Doppelklicks
  try {
    await refreshTripEtag(this._tripId);
  } catch (e) {
    this.setError(extractMessage(e));
    return;
  }
  await this.doSave(fn, init);
}
```

**Die Reihenfolge `setSaving()` VOR dem `await refreshTripEtag(...)` ist der
Kern der Idempotenz-Garantie.** Ein zweiter Klick auf den Knopf, waehrend der
Refresh noch laeuft, trifft auf `state === 'saving'` und bricht am ersten
Guard sofort ab — kein zweiter, parallel laufender Refresh, kein doppelt
verbrauchtes `_lastFailed`. Wuerde `setSaving()` erst NACH dem Refresh
gesetzt, bliebe der Zustand waehrenddessen `'conflict'` und ein ungeduldiger
Doppelklick koennte zwei Refresh-Anfragen und am Ende zwei Resend-Versuche
mit demselben `saveFn` auslösen — mit unklarer Reihenfolge am Server.

Schlaegt der Refresh selbst fehl (Netzwerk, Tour zwischenzeitlich geloescht),
geht `_lastFailed` bewusst NICHT wiederhergestellt — der Zustand faellt auf
`'error'`. Ein automatischer zweiter Retry-Versuch ist nicht vorgesehen (s.
„Known Limitations"); der Nutzer muss die Aenderung erneut ausloesen (z. B.
erneut ins Feld klicken, was `schedule()`/`doSave()` neu antriggert).

### `refreshTripEtag()` — Registry-only, kein `trip`-Replace

```ts
export async function refreshTripEtag(tripId: string): Promise<void> {
  await api.get(`/api/trips/${tripId}`);
}
```

`api.get()` laeuft durch denselben Trichter (`request()` in `api.ts`) wie
jeder andere GET auf einen Trip-Pfad. Sein bestehender Seiteneffekt aus S3 —
`setKnownEtagIfUnchanged(tripId, etag, versionAtStart)` bei jeder
erfolgreichen Antwort mit `ETag`-Header — aktualisiert die Registry exakt so,
wie es ein normaler Seitenaufbau auch taete. **Der zurueckgegebene
Trip-Datensatz wird bewusst nicht ausgewertet** — die Funktion liefert
`Promise<void>`, nicht `Promise<Trip>`, damit an keiner Aufrufstelle die
Versuchung entsteht, ihn doch irgendwo zuzuweisen.

**Warum nicht stattdessen die neue Trip-Antwort in den `trip`-`$state` der
Seite schreiben (`trip = updated`, analog `sendStateUpdate()`)?** Der
Trip-Editor teilt EINEN `tripSaveCtl` ueber Header und ALLE Tabs
(`routes/trips/[id]/+page.svelte:39`). Ein Konflikt kann in genau einem Tab
entstehen (z. B. Wetter-Reiter), waehrend ein anderer Tab (z. B. Etappen)
gerade unbeobachtete, noch nicht gespeicherte lokale Aenderungen haelt. Ein
globales `trip = updated` nach dem Refresh wuerde jede Editor-Komponente, die
ihre lokalen `$state`-Variablen aus `trip` ableitet, potenziell erneut
initialisieren oder ihre Anzeige mit dem Server-Stand ueberschreiben — mit
dem Risiko, genau die Aenderung zu verlieren, die der Nutzer gerade macht.
Eine Explore-Recherche im Rahmen dieser Spec ergab zwar, dass die
Tab-Komponenten ihre lokalen Zustandsvariablen heute nur EINMALIG beim Mount
aus `trip` lesen (kein Live-Resync bei spaeteren `trip`-Aenderungen) — die
Registry-only-Loesung braucht diese Eigenschaft aber ausdruecklich NICHT als
Voraussetzung. Sie ist die sicherere Wahl unabhaengig davon, ob sich dieses
Detail der Tab-Implementierung kuenftig aendert, und haelt den Fix auf den
tatsaechlichen Ort des Problems begrenzt: die ETag-Registry, nicht den
sichtbaren Seitenzustand.

### `tripId`-Konstruktorparameter — Rueckwaertskompatibilitaet fuer den Ortsvergleich

```ts
constructor(private _tripId?: string) {}

export function createSaveStatus(tripId?: string): SaveStatus {
  return new SaveStatus(tripId);
}
```

Ohne `tripId` (heutiger Aufruf im Ortsvergleich-Editor, der vor S6 noch
keinen ETag-Schutz hat) kann `412 && this._tripId` in `doSave()` nie
zutreffen — jeder Fehler, auch ein zufaelliger `412` von einem anderen
Grund, faellt in den unveraenderten `else`-Zweig. `retryConflict()` selbst
prueft `!this._tripId` ebenfalls und ist dann grundsaetzlich ein No-Op. Der
Ortsvergleich-Editor braucht fuer diese Scheibe keine einzige Code-Aenderung.

### `SaveIndicator.svelte` — neuer Zweig

Neuer `{:else if controller.state === 'conflict'}`-Zweig zwischen `'saving'`
und `'error'`: zeigt dieselbe Servermeldung wie der Fehler-Zweig
(`controller.error`, weiterhin ueber `extractMessage()` befuellt — keine
Aenderung an dieser Funktion), zusaetzlich einen Button „Nochmal speichern",
der `controller.retryConflict()` aufruft. Der bestehende `'error'`-Zweig
bleibt UNVERAENDERT und bekommt KEINEN Knopf — ein `400`/`500` oder ein
Netzwerkfehler ist damit nicht behoben, dass derselbe Request automatisch
wiederholt wird (z. B. ein Validierungsfehler bliebe bestehen); ein
Retry-Knopf dort waere irrefuehrend.

## Expected Behavior

- **Input:** ein `PUT` auf `/api/trips/{id}` oder `.../weather-config`
  scheitert mit `412`, `SaveStatus` wurde mit `tripId` erzeugt → Anzeiger
  wechselt von `'saving'` zu `'conflict'`, zeigt die deutsche Servermeldung
  und einen „Nochmal speichern"-Knopf
- **Input:** Klick auf „Nochmal speichern" → GET auf dieselbe Tour (Refresh),
  danach automatisch derselbe `PUT` erneut, ohne dass der Nutzer etwas
  eingibt
- **Output (Erfolgsfall):** Anzeiger zeigt „Gespeichert" mit aktuellem
  Zeitstempel, wie nach jedem anderen erfolgreichen Speichervorgang
- **Output (erneuter Konflikt):** Anzeiger bleibt/kehrt zurueck zu
  `'conflict'`, nichts wird still ueberschrieben
- **Side effects:** der Refresh aktualisiert ausschliesslich die
  ETag-Registry — der sichtbare `trip`-Zustand der Seite und alle
  Tab-Komponenten bleiben unberuehrt; keine zusaetzliche Persistenz ausser
  dem einen wiederholten Speichervorgang

## Testplan

Alle Tests unter `node --test` (`--import ./test-lib-loader.mjs
--experimental-strip-types`), Namen nach Verhalten. Fetch wird wie in S3 per
`globalThis.fetch = async (...) => ...` gemockt.

### `frontend/src/lib/stores/__tests__/saveStatusConflictRetry.test.ts`

| Test | Deckt |
|---|---|
| `test_doSave_412WithTripId_entersConflictState_remembersFailedSave` | AC-1 (Vorbedingung) |
| `test_retryConflict_refreshesEtagThenResendsOriginalSaveFn_inOrder` | AC-1 — Aufrufreihenfolge: Refresh vor erneutem `saveFn`-Aufruf, nachgewiesen ueber eine Aufruf-Reihenfolge-Liste in einer Fake-`saveFn`/Fake-`refreshTripEtag` |
| `test_retryConflict_successfulRetry_transitionsToIdleWithSavedAt` | AC-2 |
| `test_retryConflict_freshConflictDuringRetry_returnsToConflictState_notSaved` | AC-3 — Fake-`saveFn` liefert beim zweiten Aufruf erneut einen `412`-Fehler, Endzustand ist `'conflict'`, nicht `'idle'` |
| `test_doSave_genericErrorStatus_setsErrorState_notConflict` | AC-4 |
| `test_retryConflict_noOpWhenStateIsNotConflict` | Wiedereintritts-Schutz: zweiter Aufruf waehrend `'saving'` ist No-Op |
| `test_retryConflict_refreshFailure_fallsBackToErrorState_doesNotRetrySave` | Known-Limitation-Fall: Refresh selbst schlaegt fehl |
| `test_createSaveStatus_withoutTripId_412FallsBackToPlainErrorState` | AC-6 |
| `test_retryConflict_withoutTripId_isNoOp` | AC-6 (Ergaenzung) |

### `frontend/src/lib/__tests__/apiRefreshTripEtag.test.ts`

| Test | Deckt |
|---|---|
| `test_refreshTripEtag_returnsVoid_responseBodyNotExposed` | AC-5 (Teil 1) — Rueckgabewert ist nicht der Trip-Datensatz |
| `test_refreshTripEtag_updatesRegistryViaExistingGetSideEffect` | AC-5 (Teil 2) — nach dem Aufruf liefert `getKnownEtag(tripId)` den neuen Stand, ganz ohne Aenderung an `etagRegistry.ts` |
| `test_refreshTripEtag_propagatesNetworkFailure` | Grundlage fuer die Retry-Fehlerbehandlung |

### `frontend/src/lib/components/ui/__tests__/saveIndicatorConflictBranch.test.ts`

Quelltext-Verhaltenspruefung (kein Svelte-5-Runen-Render-Harness im
`node:test`-Setup — Praezedenz `weatherMetricsTabDayWindowSave.test.ts`).

| Test | Deckt |
|---|---|
| `test_conflictBranch_rendersRetryButtonCallingRetryConflict` | AC-1/AC-4 — der `'conflict'`-Zweig enthaelt einen Button, dessen Klick-Handler `controller.retryConflict()` aufruft |
| `test_errorBranch_hasNoRetryButton` | AC-4 — im `'error'`-Zweig gibt es KEINEN Aufruf von `retryConflict()` |

## Acceptance Criteria

- **AC-1:** Given ein Speichervorgang wird mit `412` (ETag-Konflikt) abgelehnt und die `SaveStatus`-Instanz kennt die Tour-ID / When der Nutzer den „Nochmal speichern"-Button im Speicher-Anzeiger klickt / Then wird automatisch zuerst der ETag aufgefrischt und danach der urspruengliche Speichervorgang wiederholt, ohne dass der Nutzer Daten erneut eingeben muss
  - Test: `test_doSave_412WithTripId_entersConflictState_remembersFailedSave`, `test_retryConflict_refreshesEtagThenResendsOriginalSaveFn_inOrder`, `test_conflictBranch_rendersRetryButtonCallingRetryConflict`

- **AC-2:** Given ein Speichervorgang wurde mit `412` abgelehnt und seither hat niemand sonst die Tour geaendert / When der Nutzer „Nochmal speichern" klickt / Then gelingt der wiederholte Speichervorgang und der Anzeiger zeigt wieder „Gespeichert" mit aktuellem Zeitstempel
  - Test: `test_retryConflict_successfulRetry_transitionsToIdleWithSavedAt`

- **AC-3:** Given ein Speichervorgang wurde mit `412` abgelehnt / When zwischen dem ETag-Refresh und dem erneuten Sendevorgang ein weiterer fremder Schreibvorgang auf dieselbe Tour eintrifft / Then scheitert der Retry erneut mit `412`, der Anzeiger bleibt im Konflikt-Zustand, und der Speichervorgang wird NICHT faelschlich als erfolgreich gemeldet
  - Test: `test_retryConflict_freshConflictDuringRetry_returnsToConflictState_notSaved`

- **AC-4:** Given ein Speichervorgang schlaegt mit einem generischen Fehler fehl (z. B. `400` oder `500`, kein `412`) / When der Speicher-Anzeiger den Fehler zeigt / Then gibt es KEINEN „Nochmal speichern"-Button — der Zustand bleibt der einfache Fehlerzustand ohne Retry-Aktion wie vor dieser Scheibe
  - Test: `test_doSave_genericErrorStatus_setsErrorState_notConflict`, `test_errorBranch_hasNoRetryButton`

- **AC-5:** Given im Trip-Editor laeuft gerade ein Konflikt-Retry (ETag-Refresh) in einem Tab / When der Refresh abgeschlossen ist / Then bleiben ungespeicherte lokale Aenderungen in ANDEREN, nicht am Konflikt beteiligten Tabs der Trip-Seite unveraendert erhalten — der Retry-Mechanismus ersetzt nirgends den sichtbaren `trip`-Zustand der Seite
  - Test: `test_refreshTripEtag_returnsVoid_responseBodyNotExposed`, `test_refreshTripEtag_updatesRegistryViaExistingGetSideEffect`

- **AC-6:** Given eine `SaveStatus`-Instanz wird ohne `tripId` erzeugt (z. B. im heutigen Ortsvergleich-Editor vor S6) / When ein Speichervorgang dort fehlschlaegt, auch mit Statuscode `412` / Then verhaelt sich der Speicher-Anzeiger exakt wie vor dieser Scheibe — kein Konflikt-Zustand, kein Retry-Button; die Aenderung ist auf den Trip-Editor beschraenkt
  - Test: `test_createSaveStatus_withoutTripId_412FallsBackToPlainErrorState`, `test_retryConflict_withoutTripId_isNoOp`

## Known Limitations

- **Ein zweiter, unabhaengiger Fehler waehrend des Refresh-GET (z. B.
  Netzwerkausfall) fuehrt zu `'error'`, nicht zu einem erneuten
  `'conflict'`.** Der urspruenglich fehlgeschlagene Speichervorgang
  (`_lastFailed`) geht dabei bewusst verloren — kein automatischer zweiter
  Retry-Versuch, kein Backoff, kein Retry-Loop. Der Nutzer muss die
  Aenderung erneut ausloesen (z. B. erneut ins Feld klicken, was
  `schedule()`/`doSave()` neu antriggert). Diese Scheibe ist als EIN
  Wiederholungsversuch pro Konflikt spezifiziert, nicht als resilientes
  Retry-System.
- **`retryConflict()` ist nicht fuer wiederholtes automatisches Nachfassen
  gedacht.** Scheitert der wiederholte Speichervorgang selbst erneut mit
  `412` (AC-3), muss der Nutzer den Knopf ein weiteres Mal klicken — es gibt
  keine interne Schleife, die das von selbst mehrfach versucht.
- **Kein Aufraeumen von `_lastFailed` beim Verlassen der Seite.** Verlaesst
  der Nutzer die Tour-Seite waehrend eines offenen Konflikts, verfaellt der
  gemerkte Speichervorgang mit der `SaveStatus`-Instanz — unschaedlich, weil
  keine Instanz seitenuebergreifend weiterlebt.
- **Der Ortsvergleich-Editor bekommt in dieser Scheibe keinen Konflikt-Schutz**
  — dort existiert noch kein `ETag`/`If-Match`-Vertrag (S6). `createSaveStatus()`
  bleibt dort ohne `tripId`-Argument.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0036 (kein neues ADR)
- **Rationale:** Diese Scheibe fuegt keine neue, schwer umkehrbare oder
  mehrere Systemteile betreffende Entscheidung hinzu — sie macht den in S2
  bereits definierten `412`-Vertrag am bestehenden Speicher-Anzeiger
  bedienbar. Die einzige nennenswerte Design-Entscheidung dieser Scheibe
  (Registry-only-Refresh statt globalem `trip`-Replace) ist eine lokale
  Umsetzungsentscheidung innerhalb des in ADR-0036 beschriebenen
  Fingerabdruck-Vertrags, keine Architektur-Entscheidung mit
  Systemtragweite.

## Zeilenrahmen

600 Zeilen, vom PO fuer die Scheiben S1–S6 dieses Issues pauschal
freigegeben (bei Bedarf anhebbar).

| Bereich | Schaetzung |
|---|---|
| Produktivcode (`api.ts`, `saveStatusStore.svelte.ts`, `SaveIndicator.svelte`, `+page.svelte`) | ~90 |
| Tests (3 neue Testdateien) | ~200 |
| **Summe** | **~290 von 600** |

## Changelog

- 2026-07-31: Initial spec erstellt — Issue #1395 Scheibe S4, aufbauend auf S1–S3
