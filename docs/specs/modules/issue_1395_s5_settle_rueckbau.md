---
entity_id: issue_1395_s5_settle_rueckbau
type: module
created: 2026-07-31
updated: 2026-07-31
status: draft
version: "1.0"
tags: [frontend, svelte, trip, save-status, cleanup, cascade]
---

<!-- Issue #1395 Scheibe S5 — Rückbau settle()/SETTLE_TIMEOUT_MS/Wartblock in applyCascade() -->

# Issue #1395 Scheibe S5 — Rückbau settle()/SETTLE_TIMEOUT_MS/Wartblock in applyCascade()

## Approval

- [ ] Approved

## Purpose

S3 hat `api.ts` eine zentrale Schreib-Warteschlange je Tour gegeben
(`enqueueTripWrite`): jeder `PUT /api/trips/{id}` — egal ob Auto-Save
(`buildStagesSave()`) oder Kaskaden-Schreibvorgang (`applyCascade()`) —
läuft durch denselben Trichter, ein späterer Aufruf wartet dort automatisch
auf einen früheren. Der clientseitige Wartemechanismus `settle()` in
`saveStatusStore.svelte.ts`, den `applyCascade()` vor S3 selbst benutzte, um
genau dasselbe Problem lokal im Panel zu lösen (verhindern, dass ein
Kaskaden-Schreibvorgang einen noch laufenden Auto-Save überholt), ist damit
redundant. Diese Scheibe entfernt `settle()`, `SETTLE_TIMEOUT_MS`, den
Wartaufruf in `applyCascade()` sowie die drei dedizierten Tests — ohne
Verhaltensverlust, weil die Ordnungsgarantie jetzt an der einen Stelle sitzt,
durch die alle Schreibvorgänge laufen.

## Source

- **File:** `frontend/src/lib/stores/saveStatusStore.svelte.ts` —
  `SETTLE_TIMEOUT_MS`-Konstante samt Begründungskommentar und `settle()`-Methode
  entfallen
- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` —
  `await saveController.settle();` in `applyCascade()` entfällt, mehrere
  Begründungskommentare werden entfernt oder umformuliert
- **File:** `frontend/src/lib/stores/__tests__/saveStatus.test.ts` — drei
  `settle()`-spezifische Tests entfallen, Import wird bereinigt

> **Schicht-Hinweis:** ausschliesslich Frontend (`frontend/src/...`,
> SvelteKit). Kein Go-, kein Python-Code betroffen.

## Estimated Scope

- **LoC:** ~90-110 von 600 freigegebenen Zeilen (reine Löschung + einige
  Kommentar-Anpassungen, keine neue Zeile Produktivlogik)
- **Files:** 3 (alle geändert, keine neue, keine gelöschte Datei)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/etagRegistry.ts` — `enqueueTripWrite` (S3) | TS-Modul | Trägt die Ordnungsgarantie, die `settle()` ersetzt — bleibt in dieser Scheibe UNVERÄNDERT |
| `frontend/src/lib/api.ts` — `request()` (S3) | TS-Modul | Ruft `enqueueTripWrite(tripId, run)` für jeden `PUT` auf `/api/trips/{id}` auf, unabhängig vom Aufrufer — bleibt UNVERÄNDERT |
| `docs/specs/modules/issue_1395_s3_etag_registry.md` | Spec | Definiert die Warteschlange, die diese Scheibe als hinreichenden Ersatz voraussetzt |
| `docs/specs/modules/issue_1395_s4_conflict_retry.md` | Spec | Nachbar-Scheibe, live; nicht betroffen (S4 fügte `retryConflict()`/`'conflict'`-Zustand hinzu, beide bleiben unverändert bestehen) |
| `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md` | ADR | Grundsatzentscheidung, auf der S2–S5 aufbauen — kein neues ADR nötig |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | MODIFY | `SETTLE_TIMEOUT_MS`-Konstante + Begründungskommentar (aktuell Z. 19-28) und `settle()`-Methode samt JSDoc (aktuell Z. 142-166) vollständig entfernen; Kommentar am `_inflight`-Feld (Z. 49-51) umformulieren (Feld selbst bleibt — wird weiterhin von `cancel()`s F003-Guard gelesen, s. „Implementation Details") |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY | `await saveController.settle();` (aktuell Z. 423) entfernen; Kommentar bei `CASCADE_WRITE_TIMEOUT_MS` (Z. 269) von der Referenz auf `SETTLE_TIMEOUT_MS` befreien; Begründungskommentare in/um `applyCascade()`, die sich auf `settle()`s Wartefenster beziehen (Z. 377-381, 405-410, 418-421, 425), entfernen bzw. umformulieren — Detailaufschlüsselung s. „Implementation Details" |
| `frontend/src/lib/stores/__tests__/saveStatus.test.ts` | MODIFY | Import bereinigen (`SETTLE_TIMEOUT_MS` raus, `SaveStatus` bleibt); drei Tests löschen: „settle() wartet auf einen bereits laufenden Speichervorgang …" (aktuell Z. 272-304), „settle() ist ein No-Op …" (Z. 306-311), „F002: settle() wartet nicht ewig …" (Z. 315-339) |

### Estimated Changes

- Files: 3 (alle MODIFY)
- LoC: -90/-110 (Schätzung, fast ausschliesslich Löschung; s. „Zeilenrahmen")

## Implementation Details

### `saveStatusStore.svelte.ts`

1. **`SETTLE_TIMEOUT_MS` + Begründungskommentar (Z. 19-28) — vollständig
   löschen.** Kein Ersatz nötig, keine andere Stelle im Repo importiert die
   Konstante ausser dem hier ebenfalls entfallenden `settle()` und dem
   entfallenden Test-Import.

2. **`settle()`-Methode samt JSDoc (Z. 142-166) — vollständig löschen.**
   Einziger Aufrufer war `applyCascade()` (s. u.).

3. **Kommentar am `_inflight`-Feld (Z. 49-51) — umformulieren, Feld selbst
   BLEIBT.** Der bestehende Kommentar lautet:

   ```ts
   // Bug #1389: der gerade im Netz laufende Speichervorgang. `cancel()` kann ihn
   // nicht mehr stoppen — wer ihn überschreiben will, muss auf ihn WARTEN
   // (`settle()`), sonst entscheidet die Netz-Laufzeit, welcher Stand gewinnt.
   private _inflight: Promise<void> | null = null;
   ```

   `_inflight` selbst ist **kein** `settle()`-exklusives Feld — es wird in
   `doSave()` gesetzt/geleert (Z. 116-118) und in `cancel()`s
   Adversary-F003-Guard gelesen (`hadDeferred && this._inflight === null`,
   Z. 250), unabhängig von `settle()`. Nur der dritte Satz des Kommentars
   ("wer ihn überschreiben will, muss auf ihn WARTEN (`settle()`)") referenziert
   die gelöschte Methode und muss raus bzw. auf den verbleibenden Zweck
   (Grundlage für `cancel()`s Guard) umformuliert werden. Das Feld selbst,
   sein Setzen in `doSave()` und seine Prüfung in `cancel()` bleiben
   unverändert bestehen.

### `EditStagesPanelNew.svelte`

`grep -n "settleMootCascade"` im selben File findet eine **gleichnamige, aber
unabhängige** Funktion (`settleMootCascade()`, Z. 516 — räumt eine
gegenstandslos gewordene Rückfrage ab). Sie hat mit `saveController.settle()`
nichts zu tun und bleibt **unangetastet**. Wortverwechslung wäre hier der
naheliegendste Fehler beim Rückbau.

Zeilenweise Behandlung der Fundstellen (aktueller Stand, verifiziert):

| Zeile(n) | Inhalt | Behandlung |
|---|---|---|
| 269 | `// 15 s liegt weit über jeder normalen Antwortzeit und über SETTLE_TIMEOUT_MS (8 s).` | Umformulieren — Referenz auf `SETTLE_TIMEOUT_MS` raus, Begründung für `CASCADE_WRITE_TIMEOUT_MS` bleibt eigenständig gültig, z. B. „15 s liegt weit über jeder normalen Antwortzeit." |
| 377-381 | Reentrancy-Riegel-Begründung (`cascadeBusy`); letzter Satz: „Seit `settle()` klafft das Fenster bis SETTLE_TIMEOUT_MS, nicht nur einen PUT." | `cascadeBusy`-Riegel selbst bleibt (Z. 382 `if (cascadeBusy) return;` unverändert) — nur der letzte Satz (Z. 381) ist `settle()`-spezifisch und muss raus bzw. umformuliert werden, OHNE die Kernaussage (Doppeltipp im selben Tick vor dem ersten `await` muss abgefangen werden) zu verlieren |
| 405-410 | „Bug #1393 R5-F001: die Zieldaten werden auf die LEBENDE Liste angewandt … Der frühere `nextStages` entstand VOR `settle()` (bis 8 s Wartezeit) …" | Entfällt inhaltlich mit `settle()`: nach dem Rückbau liegt zwischen `cancel()`/`setSaving()` und dem Aufbau von `withTargets(stages)` kein `await` mehr — der frühere Erklärungsgrund (Liste könnte sich während der Wartezeit ändern) besteht nicht mehr in dieser Form. Kommentar entfernen oder auf einen Satz kürzen, der nur noch beschreibt, dass live gelesen wird (ohne `settle()`-Bezug) |
| 418-421 | „Bug #1389: `cancel()` stoppt nur Noch-nicht-Abgeschicktes; auf einen bereits laufenden Request muss GEWARTET werden … Adversary F002: `setSaving()` bewusst VOR dem Warten …" | Vollständig löschen — beschreibt ausschliesslich die Notwendigkeit von `settle()`. `saveController.cancel();` (Z. 417) und `saveController.setSaving();` (Z. 422) BLEIBEN unverändert (Doppeltipp-/UI-Zweck unabhängig von `settle()`) |
| 423 | `await saveController.settle();` | Löschen — der eigentliche Rückbau |
| 424 | `// Flush immediately (cascade = user intent, no debounce needed).` | Bleibt — kein `settle()`-Bezug |
| 425 | `// R5-F001: Rumpf ERST JETZT bauen — nach dem Warten, aus dem aktuellen Stand.` | Umformulieren — „nach dem Warten" ist nach dem Rückbau falsch (es gibt keinen Wartschritt mehr an dieser Stelle); falls der Kommentar noch etwas Eigenständiges beiträgt, ohne Bezug auf eine Wartezeit neu fassen, sonst löschen |

Kommentare, die 2+ Anliegen mischen (z. B. Z. 377-381, 405-410), werden
**bearbeitet, nicht pauschal blockweise gelöscht** — sonst geht entweder eine
noch gültige Begründung (Reentrancy-Riegel) verloren, oder ein
`settle()`-Verweis bleibt stehen und zeigt auf eine gelöschte Konstante/Methode
(Regel aus dem Auftrag: „Kommentar bei `CASCADE_WRITE_TIMEOUT_MS`, der
`SETTLE_TIMEOUT_MS` referenziert, darf nach dem Rückbau nicht mehr auf eine
gelöschte Konstante zeigen" — gilt sinngemäss für alle übrigen Fundstellen).

**Was in `applyCascade()` unverändert bleibt:** `cascadeBusy`-Riegel
(Z. 382/388, `finally`-Rücksetzung weiter unten), `saveController.cancel()`
(Z. 417), `saveController.setSaving()` (Z. 422), `AbortController` +
`CASCADE_WRITE_TIMEOUT_MS` (Z. 426-427), der eigentliche `api.put`-Aufruf und
die Fehlerbehandlung danach (ab Z. 428).

### `saveStatus.test.ts`

- **Import (Z. 53):** `import { SaveStatus, SETTLE_TIMEOUT_MS } from
  '../saveStatusStore.svelte.ts';` → `SETTLE_TIMEOUT_MS` aus dem Import
  entfernen, `SaveStatus` bleibt (wird von praktisch jedem verbleibenden Test
  gebraucht).
- **Drei Tests löschen** (Beschreibungen wie im Repo aktuell benannt):
  - `'settle() wartet auf einen bereits laufenden Speichervorgang — die
    Reihenfolge hängt nicht mehr am Netz'` (Z. 272-304)
  - `'settle() ist ein No-Op, wenn nichts unterwegs ist (kein künstliches
    Warten)'` (Z. 306-311)
  - `'F002: settle() wartet nicht ewig — ein hängender Request friert die
    Oberfläche nicht ein'` (Z. 315-339)
- **Umgebende `describe()`-Blöcke bleiben.** Die ersten beiden Tests liegen im
  Block `'Bug #1389: Kaskaden-Rückfrage darf keinen zweiten Speichervorgang
  erzeugen'` (Z. 220), der auch die weiterhin gültigen Tests zu `defer()`
  (Z. 228) und `cancel()` (Z. 260) enthält — nur die beiden `settle()`-Tests
  darin entfallen, der Block selbst bleibt. Der dritte Test liegt im Block
  `'Bug #1389 Fix-Loop 1 (Adversary F002/F003)'` (Z. 314), der auch die
  weiterhin gültigen `F003`-Tests (Z. 341, Z. 357) enthält — ebenfalls nur der
  eine `settle()`-Test entfällt.
- Kein Ersatztest nötig: Die Serialisierungsgarantie hat bereits eigene Tests
  in `frontend/src/lib/__tests__/etagRegistryQueue.test.ts`
  (`test_enqueueTripWrite_serializesSameTripId` u. a., S3), die von dieser
  Scheibe nicht berührt werden.

## Expected Behavior

- **Input:** Nutzer löst „Alle mitverschieben" im Etappen-Editor aus, während
  im Hintergrund noch ein Auto-Save derselben Tour läuft
- **Output:** genau ein Kaskaden-`PUT` auf `/api/trips/{id}`, das den
  vorherigen Auto-Save-`PUT` nicht überholt — Garantie kommt jetzt
  ausschliesslich aus `enqueueTripWrite` (`api.ts`/`etagRegistry.ts`), nicht
  mehr aus einem clientseitigen Wartschritt im Panel
- **Side effects:** keine — reiner Rückbau, kein neues Verhalten, keine neue
  Persistenz, keine geänderte UI

## Testplan

Alle betroffenen Tests laufen unter `node --test`
(`--import ./test-lib-loader.mjs --experimental-strip-types`), wie die
bestehende Suite.

| Test | Deckt |
|---|---|
| `frontend/src/lib/stores/__tests__/saveStatus.test.ts` (verbleibende Tests, insbesondere `defer()`/`cancel()`/F003-Tests) | AC-1, AC-4 — nichts ausserhalb von `settle()` ist als Kollateralschaden zerbrochen |
| `frontend/src/lib/__tests__/etagRegistryQueue.test.ts` → `test_enqueueTripWrite_serializesSameTripId` (unverändert, S3) | AC-2 — die Serialisierungsgarantie besteht unabhängig von `settle()` bereits vor dieser Scheibe und bleibt danach unverändert grün |
| `frontend/e2e/issue-498-stage-date-autosave.spec.ts` (Playwright, u. a. `cascade-strip`/`cascade-done`-Assertions) | AC-3 — der Kaskaden-Schreibvorgang selbst funktioniert nach dem Rückbau weiterhin korrekt end-to-end (kein Unit-Test möglich, s. Known Limitations) |
| Grep-Nachweis `grep -rn "settle\|SETTLE_TIMEOUT_MS" frontend/src` (Ausnahme: `settleMootCascade`) | AC-5 — keine toten Referenzen bleiben |

## Acceptance Criteria

- **AC-1:** Given `settle()`, `SETTLE_TIMEOUT_MS` und der Wartaufruf in
  `applyCascade()` sind entfernt / When ein Nutzer im Etappen-Editor eine
  Etappe umdatiert und „Alle mitverschieben" bestätigt / Then läuft der
  Kaskaden-Schreibvorgang unverändert korrekt durch — die Folge-Etappen
  bekommen die berechneten Zieldaten, der Anzeiger zeigt „Gespeichert"
  Test: `frontend/e2e/issue-498-stage-date-autosave.spec.ts` bleibt grün
  (insbesondere die `cascade-done`-Assertions); ergänzend: `saveStatus.test.ts`
  bleibt vollständig grün nach Entfernen der drei `settle()`-Tests

- **AC-2:** Given ein Auto-Save derselben Tour läuft noch im Netz / When
  parallel ein Kaskaden-Schreibvorgang für dieselbe Tour ausgelöst wird /
  Then bleiben Auto-Save und Kaskaden-Schreibvorgang serialisiert (der
  spätere wartet auf den früheren) — ausschliesslich getragen von
  `enqueueTripWrite` in `api.ts`/`etagRegistry.ts`, ohne lokalen Wartschritt
  im Panel
  Test: `test_enqueueTripWrite_serializesSameTripId` in
  `frontend/src/lib/__tests__/etagRegistryQueue.test.ts` (bestehend, S3,
  unverändert grün)

- **AC-3:** Given ein vorheriger Schreibvorgang derselben Tour hängt
  ungewöhnlich lange in der Warteschlange / When der Kaskaden-Schreibvorgang
  darauf wartet / Then bricht er spätestens nach `CASCADE_WRITE_TIMEOUT_MS`
  (15 s) mit einer verständlichen Fehlermeldung ab, statt unbegrenzt zu
  hängen — diese Deckelung besteht bereits vor dem Rückbau (AbortController
  deckt die gesamte Wartezeit inkl. Queue, nicht nur den `fetch`) und bleibt
  unverändert bestehen
  Test: bestehendes Verhalten des `AbortController`/`ctrl.signal`-Zweigs in
  `applyCascade()` (Z. 426-433, 449-456) — unverändert durch diese Scheibe,
  kein neuer Test nötig; e2e-Regressionsnachweis wie AC-1

- **AC-4:** Given die drei `settle()`-spezifischen Tests sind aus
  `saveStatus.test.ts` gelöscht / When die restliche Testdatei ausgeführt
  wird / Then bleiben alle verbleibenden Tests (u. a. `defer()`, `cancel()`,
  die beiden F003-Tests, `markPristine()`) unverändert grün — kein toter
  Import, kein Verweis auf `SETTLE_TIMEOUT_MS` mehr in der Datei
  Test: `node --test` auf `saveStatus.test.ts` nach dem Rückbau, 0 Failures,
  0 Referenzen auf `settle`/`SETTLE_TIMEOUT_MS` im Testoutput/Quelltext

- **AC-5:** Given der Rückbau ist abgeschlossen / When der gesamte
  `frontend/src`-Baum nach `settle`/`SETTLE_TIMEOUT_MS` durchsucht wird /
  Then gibt es ausser der namentlich unabhängigen `settleMootCascade()`
  (unverändert, anderer Zweck) keinen Treffer mehr — insbesondere zeigt der
  Kommentar bei `CASCADE_WRITE_TIMEOUT_MS` nicht mehr auf die gelöschte
  Konstante
  Test: `grep -rn "settle\|SETTLE_TIMEOUT_MS" frontend/src` liefert nach dem
  Rückbau ausschliesslich Treffer für `settleMootCascade`

## Known Limitations

- **`applyCascade()` selbst ist nicht direkt unit-testbar.**
  `EditStagesPanelNew.svelte` ist eine Svelte-Komponente und im
  `node:test`-Setup dieses Repos (`--import ./test-lib-loader.mjs`) nicht
  instanziierbar (bestehende Einschränkung, dokumentiert im Kommentarblock
  von `saveStatus.test.ts` Z. 382-386 sowie in
  `docs/specs/modules/issue_1395_s4_conflict_retry.md`). Der Regressionsnachweis
  für AC-1/AC-3 läuft deshalb über den bestehenden Playwright-E2E-Test
  (`issue-498-stage-date-autosave.spec.ts`), nicht über einen neuen Unit-Test.
- **Folgende Mechanismen bleiben von dieser Scheibe ausdrücklich
  unverändert** (laut Issue-Kommentar, kein Teil von S5):
  - `defer()` — stellt einen Save zurück, wenn eine Rückfrage offen ist
    (Absicht, kein Wettlauf-Schutz)
  - Doppeltipp-Riegel `cascadeBusy`
  - `saveController.cancel()` — verwirft einen noch NICHT abgeschickten
    Debounce, anderer Zweck als `settle()` (das auf einen BEREITS laufenden
    Request wartete)
  - `beforeNavigate`-Flush (#1376)
  - `settleMootCascade()` — namensähnlich, aber unabhängige Funktion (räumt
    eine gegenstandslos gewordene Rückfrage ab)
- **Keine Timeout-Deckelung mehr auf 8 s speziell für das Warten auf einen
  Vorgänger.** Die Warteschlange in `api.ts` hat selbst keinen Timeout — sie
  wartet, bis der vorherige Request antwortet oder scheitert. Das ist kein
  Rückschritt: `CASCADE_WRITE_TIMEOUT_MS` (15 s) deckelt bereits die GESAMTE
  Wartezeit inkl. Zeit in der Queue, nicht nur den `fetch` selbst — ein
  hängender Vorgänger kann den Kaskaden-Schreibvorgang also nicht unbegrenzt
  blockieren (verifiziert am Code: `ctrl.signal` wird vor dem
  `enqueueTripWrite`-Eintritt gebaut und läuft unabhängig davon weiter, ob der
  Request gerade in der Queue wartet oder schon fetcht; ist `signal` beim
  Dequeuing bereits `aborted`, lehnt `fetch()` sofort mit `AbortError` ab).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Rückbau von totem/redundantem Code ohne neue
  Entscheidungsfläche — die zugrundeliegende Architekturentscheidung
  (Nebenläufigkeitsschutz über ETag/`If-Match` + zentrale Warteschlange) ist
  bereits in ADR-0036 getroffen und mit S3 umgesetzt. Diese Scheibe entfernt
  lediglich einen jetzt überflüssigen, lokalen Vorläufer-Mechanismus.

## Zeilenrahmen

600 Zeilen, vom PO für die Scheiben S1-S6 dieses Issues pauschal freigegeben.

| Bereich | Schätzung |
|---|---|
| Produktivcode (`saveStatusStore.svelte.ts`, `EditStagesPanelNew.svelte`) | ~-25 bis -35 (Löschung) |
| Tests (`saveStatus.test.ts`) | ~-64 (Löschung) |
| **Summe** | **~-90 bis -110 von 600** (negativ — reiner Abbau) |

## Changelog

- 2026-07-31: Initial spec erstellt — Issue #1395 Scheibe S5, Rückbau nach
  S3 (Warteschlange live) und S4 (live)
