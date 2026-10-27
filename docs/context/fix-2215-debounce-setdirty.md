# Context: fix-2215-debounce-setdirty

## Request Summary
Issue #2215 (Epic #2260): Ein im Debounce-Fenster (700 ms) vorgemerkter Save wird nicht abgebrochen, wenn danach ein NICHT speicherbarer Zwischenstand folgt. Der alte Payload wird trotzdem geschrieben, die Anzeige springt auf „Gespeichert", obwohl auf dem Bildschirm ein ungespeicherter Stand steht. Verstößt gegen die Epic-Invariante „was nicht gespeichert ist, sieht der Nutzer sofort".

## Befund (am 2026-10-03 gegen `origin/main` 04a76f5a6 geprüft): Fehler besteht noch
- `saveStatusStore.svelte.ts:154` `setDirty()` setzt nur `state = 'dirty'` (Ausnahme: offener Konflikt). Weder `_timer` noch `_pendingFn` werden angefasst.
- `schedule()` (:363) setzt `_pendingFn` + Timer; `doSave()` (:198) setzt danach `setSaving()` → `setSaved()`. Der Zustand `dirty` wird vom Timer-Ablauf überschrieben.
- Ablauf CorridorEditor (`CorridorEditor.svelte:324-325`): gültige Eingabe → `schedule(buildSaveFn())`. `buildSaveFn()` baut den Payload SOFORT (Schnappschuss, :266). Innerhalb 700 ms ungültige Eingabe → `setDirty()` → Timer läuft weiter → alter Schnappschuss wird gespeichert → „Gespeichert ✓", Bildschirm zeigt ungültigen Stand.
- Gleiches Muster in `WeatherMetricsTab.svelte:972, 1007, 1034` (Gate `skip` → `setDirty()`) und `BriefingScheduleTab.svelte:103`.

## Related Files
| File | Relevanz |
|------|-----------|
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | `setDirty` (:154), `schedule` (:363), `cancel` (:424), `defer` (:392), `doSave` (:198), `hasPending` |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte:324-325` | `schedule` vs. `setDirty` je nach `saveGateDecision` |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts:816` | `saveGateDecision` (`schedule`/`dirty`) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Gate `skip` → `setDirty()` an 3 Stellen |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte:101-103` | `schedule` oder `setDirty` |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte:445` | `setDirty()` BEWUSST bei `hasPending` — der vorgemerkte Save soll weiterlaufen |
| `frontend/src/lib/stores/__tests__/saveStatus.test.ts` | bestehende Store-Tests, `setDirty` an :93, :120, :267 |

## Existing Patterns
- `cancel()` (:424) verwirft Timer + `_pendingFn` und setzt `idle` nur, wenn ein Timer abgebrochen wurde und kein Request im Netz läuft; läuft ein Request, bleibt der Zustand unberührt.
- `defer()` (:392) stellt einen Save OHNE Timer zurück (Zustand `dirty`, `flush()` schreibt ihn später).
- #1433: `setSaving()` ist bei offenem Konflikt ein No-op, `setDirty()` ebenso.

## Dependencies / Dependents
- Upstream: `saveFn` der Aufrufer (`baueTripSpeicherung`, `baueWetterMetrikenSpeicherung`).
- Downstream: alle Editoren in Trip UND Ortsvergleich, die `saveController` nutzen (geteilter Baustein, Trip/Compare-Teilung beachten). Speicher-Chip/Overlay (#880).

## Wichtige Designfalle
`setDirty()` pauschal um „Timer abbrechen" zu erweitern bricht `EditStagesPanelNew.svelte:445`: dort soll der vorgemerkte Save bei `dirty` ABSICHTLICH weiterlaufen. Lösung muss die beiden Bedeutungen trennen (z. B. eigene Store-Methode „ungültiger Zwischenstand" oder Aufrufer-seitiges `cancel()` + `setDirty()`). Entscheidung gehört in die Analyse.

## Offene Fragen für /20-analyse
1. Soll bei ungültigem Zwischenstand der letzte gültige Stand noch gespeichert werden (Timer läuft weiter, Anzeige bleibt `dirty`) oder verworfen? Datenverlust-Regel (Epic #2260) spricht gegen stilles Verwerfen; Anzeige darf aber nie „Gespeichert" sagen.
2. Läuft bereits ein Request im Netz (`_inflight`), wenn der ungültige Stand kommt? Dort kein Rollback möglich, `setSaved()` danach darf `dirty` nicht überschreiben.
3. Reproduktion im Kerntest (ohne Netz): Store + Fake-Timer, `schedule(fn)`, `setDirty()`, Timer ablaufen lassen, Zustand muss `dirty` bleiben.

## Existing Specs
- `docs/specs/modules/feat_880_autosave_overlay.md`, `docs/specs/_archive/modules/issue_758_save_indicator.md`

## Risks
- Blast Radius: geteilter Speicher-Baustein aller Editoren.
- Mutations-Gegenprobe Pflicht: Test muss an der Stelle prüfen, an der die Zusicherung wirkt (Anzeige nach Timer-Ablauf), nicht nur im Store-Aufruf.

## Analysis

### Type
Bug (nutzersichtbar: Anzeige „Gespeichert" obwohl ein ungespeicherter Stand auf dem Bildschirm steht)

### Entscheidung zu den offenen Fragen
1. **Letzten gültigen Stand weiterschreiben, Anzeige bleibt `dirty`.** Verwerfen wäre Datenverlust (Epic #2260); der Schnappschuss ist ein vom Nutzer bewusst erreichter gültiger Stand. Die Anzeige darf aber nie „Gespeichert" sagen, solange der ungültige Zwischenstand offen ist.
2. **Request im Netz (`_inflight`):** wird von derselben Lösung abgedeckt — `setSaved()` prüft das Merkmal, egal ob der Save aus dem Timer oder aus `flush()` kommt.
3. **Reproduktion im Kerntest:** `saveStatus.test.ts`, Fake-Timer: `schedule(fn)` → `markiereUngespeicherteEingabe()` → Timer ablaufen lassen → `fn` lief (Daten gesichert), `state === 'dirty'`, `savedAt` unverändert.

### Technischer Ansatz
- Neue Store-Methode (Arbeitsname `setUnsavedInput()`) neben dem unveränderten `setDirty()`: setzt `state='dirty'` UND ein Merkmal `_offenerZwischenstand`; Timer/`_pendingFn` bleiben unberührt.
- `setSaved()`: ist das Merkmal gesetzt, bleibt `dirty` (kein `savedAt`-Stempel, `_unresolvedError` bleibt wie bei Teilerfolg unangetastet nur bei echtem Erfolg löschen — in der Spec festlegen).
- Merkmal löschen in: `schedule()` (neue gültige Eingabe = neuer Stand), `cancel()`, `markPristine()`.
- `setDirty()` bleibt unverändert, weil `EditStagesPanelNew.svelte:445` und `defer()` es bewusst so nutzen (vorgemerkter Save soll die Wahrheit schreiben und danach „Gespeichert" melden).
- Aufrufer umstellen (alle „ungültig/Geste fehlt"-Fälle): `CorridorEditor.svelte:325`, `CorridorEditorMobile.svelte:264`, `WeatherMetricsTab.svelte:972, 1007, 1034`, `BriefingScheduleTab.svelte:103`.
- Trip/Compare-Teilung: reiner geteilter Baustein, kein Pendant-Problem.

### Affected Files
| File | Change | Description |
|---|---|---|
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | MODIFY | neue Methode + Merkmal, `setSaved`/`schedule`/`cancel`/`markPristine` |
| `corridor-editor/CorridorEditor.svelte`, `CorridorEditorMobile.svelte` | MODIFY | `setDirty()` → neue Methode |
| `shared/WeatherMetricsTab.svelte` (3 Stellen) | MODIFY | dito |
| `trip-detail/BriefingScheduleTab.svelte` | MODIFY | dito |
| `stores/__tests__/saveStatus.test.ts` | MODIFY | Kerntests (Timer-Ablauf, inflight, schedule-Reset, setDirty-Altverhalten) |

### Scope Assessment
- Files: 6–7, Estimated LoC: +60/−6 (ohne Tests), Risk Level: MEDIUM (geteilter Speicher-Baustein aller Editoren, aber additiv)

### Risiken / Adversary-Punkte
- Mutation: Merkmal in `setSaved()` entfernen → Test muss rot werden (Anzeige nach Timer-Ablauf, nicht nur Methodenaufruf).
- Mutation: Reset in `schedule()` entfernen → Anzeige bliebe nach gültiger Folgeeingabe ewig `dirty`.
- `EditStagesPanelNew`-Verhalten muss unverändert bleiben (Regressionstest).
- Komponenten-Aufrufer: ein Test pro Familie, der die Verdrahtung beweist (nicht nur Store).

### Open Questions
- [ ] Keine für den PO. Technisch in Spec festzulegen: Verhalten von `_unresolvedError` bei offenem Zwischenstand.
