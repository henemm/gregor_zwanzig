---
entity_id: fix_2215_unsaved_input_marker
type: bugfix
created: 2026-10-03
updated: 2026-10-03
status: draft
version: "1.0"
workflow: fix-2215-debounce-setdirty
tags: [saveStatusStore, autosave, debounce, epic-2260, trip, ortsvergleich]
---

# Speicher-Anzeige: ungespeicherter Zwischenstand darf nie „Gespeichert" melden (#2215)

## Approval

- [ ] Approved (PO: ACs auf Deutsch freigeben mit `approved` / `freigabe`)

## Purpose

Wenn der Nutzer einen gültigen Stand eingibt und innerhalb von 700 ms einen nicht speicherbaren Zwischenstand folgen lässt, schreibt der Store den alten Stand und springt auf „Gespeichert", obwohl auf dem Bildschirm ein ungespeicherter Stand steht. Die Spec trennt „Zwischenstand offen" von „vorgemerkter Save läuft weiter" und stellt die Epic-Invariante (#2260) sicher: was nicht gespeichert ist, sieht der Nutzer sofort — und die Anzeige lügt nie.

## Source

- **File:** `frontend/src/lib/stores/saveStatusStore.svelte.ts`
- **Identifier:** `SaveStatus.setDirty` (:154), `setSaved` (:145), `markPristine` (:176), `schedule` (:362), `cancel` (:427), `defer` (:391), `doSave` (:198)

Schicht: **Frontend / User-UI** (SvelteKit). Kein Go-API- oder Python-Anteil.

## Befund (gegen `origin/main` 04a76f5a6 geprüft)

- `setDirty()` setzt nur `state = 'dirty'`; `_timer` und `_pendingFn` bleiben unberührt.
- `schedule()` merkt den Save vor (Schnappschuss-Payload, z. B. `buildSaveFn()` in `CorridorEditor.svelte`). Läuft der Timer ab, ruft `doSave()` → `setSaving()` → `setSaved()` und überschreibt `dirty` mit `idle` + frischem `savedAt`.
- Auslöser in der Praxis: `CorridorEditor.svelte:325`, `CorridorEditorMobile.svelte:264`, `WeatherMetricsTab.svelte:972/1007/1034` (Gate `skip`), `BriefingScheduleTab.svelte:103` (Gate `skip`).

## Entscheidung (nicht verhandelbar, aus /20-analyse)

1. **Der letzte gültige Stand wird weitergeschrieben.** Stilles Verwerfen wäre Datenverlust (Epic #2260). Der Schnappschuss ist ein vom Nutzer bewusst erreichter gültiger Stand.
2. **Die Anzeige bleibt `dirty`** („Nicht gespeichert"), solange der ungültige Zwischenstand offen ist — auch nach erfolgreichem PUT.
3. **`setDirty()` bleibt unverändert.** `EditStagesPanelNew.svelte:445` (vorgemerkter Save soll bei `hasPending` weiterlaufen und danach „Gespeichert" melden) und `defer()` (:395) nutzen es bewusst so.

## Implementation Details

Neue öffentliche Methode (Arbeitsname `setUnsavedInput()`) und privates Merkmal `_offenerZwischenstand: boolean = false` (Testinstanzen per `Object.create(SaveStatus.prototype)` haben `undefined` — überall truthy prüfen, wie bei `_unresolvedError`).

| Stelle | Verhalten |
|---|---|
| `setUnsavedInput()` | Bei offenem Konflikt No-op (wie `setDirty`, #1433; das Merkmal wird dann NICHT gesetzt). Sonst `state = 'dirty'` und `_offenerZwischenstand = true`. `_timer`/`_pendingFn` unberührt. |
| `setSaved()` | Bei offenem Konflikt unverändert No-op. Ist das Merkmal gesetzt: `state` bleibt `dirty` (bzw. wird auf `dirty` gesetzt, falls `doSave` zuvor `saving` gesetzt hatte), `error = null`, KEIN `savedAt`-Stempel. Greift für jeden Aufrufweg: Timer-Ablauf, `flush()` und einen bereits laufenden Request (`_inflight`), dessen `setSaved()` erst nach dem `setUnsavedInput()` eintrifft. |
| `schedule()` | Löscht das Merkmal (eine neue gültige Eingabe ist ein neuer Stand, der Zwischenstand ist überholt). Reihenfolge: Merkmal löschen VOR `setSaving()`. |
| `cancel()` | Löscht das Merkmal (Verwerfen: der ungültige Stand ist weg). |
| `markPristine()` | Löscht das Merkmal (Baseline-Korrektur: „nichts zu speichern"). Löschung vor dem Konflikt-Early-Return ist nicht nötig; bei Konflikt bleibt alles stehen. |
| `setDirty()` | Unverändert. Löscht das Merkmal NICHT und setzt es NICHT. |
| `defer()` | Unverändert (ruft `setDirty()`). |

### Festlegung `_unresolvedError`

- **Echter erfolgreicher PUT löscht `_unresolvedError` auch bei offenem Zwischenstand.** Begründung: der Fehlschlag betrifft den damals versuchten Stand; der jetzt erfolgreich geschriebene letzte gültige Stand ersetzt ihn tatsächlich (Daten sind auf dem Server). Das entspricht dem bestehenden Satz in `setSaved()` („erst ein ECHTER Erfolg löscht den offenen Fehlschlag"). Es wird nur die Anzeige zurückgehalten, nicht die Fehlerbuchführung verfälscht.
- **`setError()` bleibt unverändert** und gewinnt über das Merkmal: ein gescheiterter PUT zeigt `error`. Das Merkmal bleibt dabei gesetzt, damit ein späterer erfolgreicher Retry bei weiterhin offenem Zwischenstand ebenfalls `dirty` statt „Gespeichert" zeigt.
- **`markPristine()`** behält sein Verhalten: ist `_unresolvedError` gesetzt, zeigt es `error`; sonst `idle`. Das Merkmal wird dort gelöscht.
- **Konflikt (`conflict`) ist sticky** und hat Vorrang vor allem; `setUnsavedInput()` verändert ihn nicht.

### Aufrufer-Umstellung (Zeilen gegen aktuellen Stand)

`setDirty()` → `setUnsavedInput()` an genau diesen Stellen (alle bedeuten „Eingabe ungültig bzw. Geste fehlt, Bildschirm zeigt ungespeicherten Stand"):

- `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte:325`
- `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte:264`
- `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:972`, `:1007`, `:1034`
- `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte:103` (Kommentar :88 mitziehen)
- **Nachtrag (Adversary F001, 2026-10-03):** `CorridorEditor.svelte` und `CorridorEditorMobile.svelte`, Funktion `maybeSchedule`, Zweig `context === 'vergleich'`: bei Gate ≠ `schedule` zusätzlich `saveController?.setUnsavedInput()` (neuer Aufruf, kein Umstellen). Anlege-Seite `/compare/new` hat keinen Controller (optional chaining, No-op).

NICHT umstellen: `EditStagesPanelNew.svelte:445`.

## Estimated Scope

- **LoC:** +60 / −6 (ohne Tests)
- **Files:** 6 Produktionsdateien + 1 Testdatei (plus je ein Verdrahtungstest je Aufrufer-Familie)
- **Effort:** low–medium (Risk MEDIUM: geteilter Speicher-Baustein aller Editoren, aber additiv)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `saveStatusStore.svelte.ts` | store | Zustandsmaschine, `SaveFn`, `_inflight` |
| `SaveIndicator.svelte` (feat_880) | component | zeigt `dirty` als „Nicht gespeichert", `idle` + `savedAt` als „Gespeichert HH:MM" |
| `corridorEditorState.ts` `saveGateDecision` (:816) | function | entscheidet `schedule`/`dirty` |
| `weatherSaveGate` | function | entscheidet `save`/`skip` |

## Trip/Ortsvergleich-Teilung

Reiner geteilter Baustein (Store + geteilte Tab-Organismen `shared/`, `corridor-editor/`). Trip UND Ortsvergleich sind betroffen, es entsteht keine neue Compare- oder Trip-eigene Komponente — kein Pendant-Problem.

## Test-Plan

Kerntests (deterministisch, Schicht „Kern", kein Netz): `frontend/src/lib/stores/__tests__/saveStatus.test.ts`, Fake-Timer (bestehender Stil der Datei), echter `SaveStatus` — kein Mock des Prüflings. Geprüft wird immer die **Anzeige nach Timer-Ablauf** (`state`, `savedAt`), nicht der Methodenaufruf.

1. Repro (rot vor Fix): `schedule(fn)` → `setUnsavedInput()` → Timer ablaufen lassen, `await` → `fn` wurde aufgerufen (Daten gesichert), `state === 'dirty'`, `savedAt` unverändert.
2. Request im Netz: `doSave(fn)` mit offenem Promise → `setUnsavedInput()` → Promise auflösen → `state === 'dirty'`, kein neues `savedAt`.
3. `flush()`-Weg: `schedule(fn)` → `setUnsavedInput()` → `await flush()` → `state === 'dirty'`.
4. Reset durch neue gültige Eingabe: `setUnsavedInput()` → `schedule(fn2)` → Timer ablaufen → `state === 'idle'`, `savedAt` gesetzt.
5. Reset durch `cancel()` und durch `markPristine()`: anschließend `doSave(fn)` → `idle` (Merkmal ist weg).
6. Regression Altverhalten: `schedule(fn)` → `setDirty()` → Timer ablaufen → `state === 'idle'` (EditStagesPanelNew-Bedeutung unverändert); `defer(fn)` + `flush()` → `idle`.
7. Konflikt: bei `state === 'conflict'` ändert `setUnsavedInput()` nichts, Merkmal bleibt ungesetzt; nach `retryConflict()` und erfolgreichem Save → `idle`.
8. Fehler: `setUnsavedInput()` → `doSave(werfende fn)` → `state === 'error'`; anschließender erfolgreicher `doSave` bei weiter offenem Zwischenstand → `dirty`. Erfolgreicher PUT bei offenem Zwischenstand löscht `_unresolvedError` (danach `markPristine()` → `idle`, nicht `error`).

Verdrahtungstests (je Aufrufer-Familie, beweisen, dass die Komponente im echten Render den neuen Weg ruft — im Stil der vorhandenen SSR-/Komponententests unter `shared/__tests__/` und `corridor-editor/__tests__/`, mit echtem `SaveStatus`, ungültige Eingabe bei bereits vorgemerktem Save, Timer ablaufen lassen, Anzeige-Zustand lesen):

- Familie Wertebereiche: `CorridorEditor` (Desktop) und `CorridorEditorMobile` — ungültige Zeile nach gültigem Schritt → nach Ablauf `dirty`.
- Familie Wetter-Metriken: `WeatherMetricsTab`, Gate `skip` (alle drei Stellen, mindestens je ein Pfad; die drei Pfade sind getrennte Funktionen).
- Familie Briefing-Zeitplan: `BriefingScheduleTab`, Gate `skip` nach vorgemerktem Save.
- Regression: `EditStagesPanelNew` ruft weiterhin `setDirty()` — vorgemerkter Save läuft und meldet „Gespeichert".

Jede Aufrufer-Prüfung läuft mit zwei Kontexten, wo der Baustein beide kennt (`context="route"` und `context="vergleich"`).

## Mutations-Gegenproben (Pflicht für den Adversary)

Nur per String-Ersetzung mit externer Sicherungskopie, nie `git checkout/stash/reset`. Für jede Mutation muss genau der benannte Test rot werden (nicht ein zufälliger anderer):

| Mutation | Erwartung |
|---|---|
| Merkmal-Prüfung in `setSaved()` entfernen | Tests 1, 2, 3 rot (Anzeige nach Timer-Ablauf `idle`) |
| Löschen in `schedule()` entfernen | Test 4 rot (Anzeige bliebe ewig `dirty`) |
| Löschen in `cancel()` bzw. `markPristine()` entfernen | Test 5 rot |
| `setUnsavedInput()` setzt zusätzlich `clearTimeout`/`_pendingFn = null` (stilles Verwerfen) | Test 1 rot (`fn` lief nicht = Datenverlust) |
| `setDirty()` setzt das Merkmal mit | Test 6 rot (Altverhalten) |
| `setUnsavedInput()` ignoriert den Konflikt | Test 7 rot |
| Aufrufer wieder auf `setDirty()` zurück (je Familie einzeln) | der Verdrahtungstest dieser Familie rot |
| `_unresolvedError` bei offenem Zwischenstand nicht löschen | Test 8 rot |

Die Prüfung misst die Anzeige NACH Timer-Ablauf, also an der Stelle, an der die Zusicherung wirkt — nicht nur im Methodenaufruf.

## Expected Behavior

- **Input:** gültiger Stand (→ `schedule`), danach innerhalb 700 ms ein nicht speicherbarer Zwischenstand (→ `setUnsavedInput`).
- **Output:** der gültige Stand wird nach Ablauf des Timers gespeichert; die Anzeige steht durchgehend auf „Nicht gespeichert" und sagt nie „Gespeichert HH:MM" für den offenen Zwischenstand.
- **Side effects:** keine neuen Requests; `savedAt` bleibt unverändert, solange das Merkmal gesetzt ist.

## Acceptance Criteria

**AC-1:** Given ein Nutzer hat in einem Editor einen gültigen Stand eingegeben und der Autospeicher ist vorgemerkt / When er innerhalb des Wartefensters von 700 ms einen nicht speicherbaren Zwischenstand eingibt und das Fenster abläuft / Then bleibt die Anzeige auf „Nicht gespeichert" und zeigt zu keinem Zeitpunkt „Gespeichert".
  - Test: Kerntest 1 (Fake-Timer, Anzeige-Zustand und `savedAt` nach Timer-Ablauf).

**AC-2:** Given derselbe Ablauf wie in AC-1 / When das Wartefenster abgelaufen ist / Then wurde der zuletzt gültige Stand trotzdem gespeichert, es geht keine bewusst erreichte Eingabe verloren.
  - Test: Kerntest 1 (`fn` wurde genau einmal aufgerufen, Payload = gültiger Schnappschuss).

**AC-3:** Given ein Speichervorgang läuft bereits im Netz / When währenddessen ein nicht speicherbarer Zwischenstand eingegeben wird und der Vorgang erfolgreich endet / Then bleibt die Anzeige auf „Nicht gespeichert" und trägt keinen neuen „Gespeichert HH:MM"-Zeitstempel.
  - Test: Kerntest 2 (offener `doSave`, danach Auflösung).

**AC-4:** Given ein nicht speicherbarer Zwischenstand ist offen und ein Save ist vorgemerkt / When der Save über Seitenwechsel oder Flush sofort ausgelöst wird / Then bleibt die Anzeige ebenfalls auf „Nicht gespeichert".
  - Test: Kerntest 3.

**AC-5:** Given ein nicht speicherbarer Zwischenstand ist offen / When der Nutzer danach wieder einen gültigen, speicherbaren Stand eingibt (oder die Änderung verwirft bzw. der Stand wieder dem gespeicherten entspricht) / Then wird beim nächsten erfolgreichen Speichern wieder „Gespeichert HH:MM" angezeigt — die Anzeige bleibt nicht dauerhaft auf „Nicht gespeichert" hängen.
  - Test: Kerntests 4 und 5.

**AC-6:** Given der Seitenwechsel-/Rückfrage-Pfad im Trip-Etappen-Editor (`EditStagesPanelNew`) hat einen Save vorgemerkt / When er den Zustand „Nicht gespeichert" setzt und der vorgemerkte Save danach läuft / Then meldet die Anzeige nach dem Speichern weiterhin „Gespeichert" — das Verhalten von `setDirty()` und `defer()` ist unverändert.
  - Test: Kerntest 6 und Verdrahtungs-Regression EditStagesPanelNew.

**AC-7:** Given ein Konflikt (anderer Reiter hat den Trip geändert) ist offen / When der Nutzer weiter eine ungültige Eingabe macht / Then bleibt der Konflikt-Zustand mit seiner „Nochmal speichern"-Aktion unverändert bestehen und wird nicht von „Nicht gespeichert" überschrieben.
  - Test: Kerntest 7.

**AC-8:** Given ein Speichervorgang scheitert, während ein ungültiger Zwischenstand offen ist / When der Fehler eintrifft / Then zeigt die Anzeige den Fehler, und ein späterer erfolgreicher Versuch bei weiter offenem Zwischenstand zeigt „Nicht gespeichert", nicht „Gespeichert".
  - Test: Kerntest 8.

**AC-9:** Given ein Nutzer arbeitet in einem Trip ODER in einem Ortsvergleich in Wertebereiche (Desktop und Mobil), Wetter-Metriken oder Briefing-Zeitplan / When er nach einer gültigen Änderung eine ungültige bzw. noch nicht freigeschaltete Eingabe macht / Then bleibt der Speicher-Chip in allen diesen Editoren auf „Nicht gespeichert", bis wieder ein speicherbarer Stand gesichert ist.
  - Test: Verdrahtungstests je Aufrufer-Familie (inkl. beider Kontexte `route` und `vergleich`, wo vorhanden).

## Known Limitations

- Ein bereits im Netz laufender Request kann nicht zurückgenommen werden (kein Rollback, bestehende Spec-Grenze aus `cancel()`); die Lösung deckt ihn über die Anzeige ab, nicht über Abbruch.
- Es wird kein neuer Fehlertext für „ungültige Eingabe" eingeführt; die Anzeige nutzt den bestehenden Zustand `dirty`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** additive Zustandsergänzung im bestehenden Speicher-Baustein, keine Änderung an Kanälen, Persistenz oder Editor-Paradigma; Datenverlust-Regel (Epic #2260) wird eingehalten, indem nichts verworfen wird.

## Changelog

- 2026-10-03: Nachtrag Ortsvergleich-Zweig in `maybeSchedule` (Desktop + Mobil) nach Adversary-Finding F001
- 2026-10-03: Initial spec created (Issue #2215)
