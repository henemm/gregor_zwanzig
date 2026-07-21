---
entity_id: issue_1261_compare_edit_autosave
type: module
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [compare, trip, autosave, shared-components, bugfix, data-safety]
---

<!-- Issue #1261 — Ortsvergleich: Bearbeiten auffindbar machen (a) + Autospeichern
     nachrüsten (b). PO-Richtungsentscheid: "Ortvergleich soll sich so verhalten
     wie Trips!!!!!!!" — Trip-Verhalten wird 1:1 gespiegelt, keine strukturelle
     Routen-Verschmelzung (das ist Konvergenz-Epic #1230). -->

# Issue 1261 — Compare-Editor: Bearbeiten auffindbar + Autospeichern (Trip-Parität)

## Approval

- [ ] Approved

## Purpose

Behebt den kritischen Bug #1261: Auf der Compare-Detailseite (Desktop) gibt es
keinen auffindbaren „Bearbeiten"-Einstieg (Teil a), und Änderungen an
Orten/Wertebereich/Versand im Compare-Editor werden nicht automatisch
gespeichert — nur ein manueller Klick auf „Speichern" persistiert (Teil b).
Beide Lücken werden durch 1:1-Spiegelung des Trip-Verhaltens geschlossen:
sichtbarer Bearbeiten-Zugang (Header-Button + Desktop-⋮-Menü) und debouncetes
Autospeichern mit dem #1234-Gesten-Gate (verhindert Schreibzugriffe ohne
echte Nutzeraktion, GR221-Datenverlust-Klasse). Die getrennten Compare-Routen
(`/compare/[id]` vs. `/compare/[id]/edit`) und die geteilten Trip-Komponenten
bleiben strukturell unangetastet — das ist bewusst Konvergenz-Epic #1230, nicht
dieser Hotfix.

## Source

> **Schicht-Hinweis geprüft:** Alle betroffenen Dateien liegen im Frontend
> (`frontend/src/...`, SvelteKit). Das Backend
> (`internal/handler/compare_preset.go`, `PUT /api/compare/presets/{id}`)
> existiert bereits, funktioniert bei manuellem Save und bleibt in diesem
> Issue unverändert.

- **File (a, Detail-Header + Kebab):** `frontend/src/routes/compare/[id]/+page.svelte:100-102` (toter `edit`-Handler),
  `:171-180` (Desktop-Header-Aktionsreihe, kein Bearbeiten-Button),
  `:179` (Kebab injiziert `compareLifecycleActions(status)`, ohne `edit`)
- **File (a, Aktions-Baupläne):** `frontend/src/lib/components/compare/subscriptionHelpers.ts:253-272`
  (`compareActions()`, MIT `{id:'edit'}`, nutzen die Listen-Tiles) vs.
  `:279-286` (`compareLifecycleActions()`, OHNE `edit`, nutzt die Detailseite)
- **File (a, Mobile-Referenz, unverändert):** `frontend/src/lib/components/mobile/MCompareActionSheet.svelte:31`
  (nutzt ebenfalls `compareLifecycleActions()`, bewusst ohne `edit` seit #1256
  Scheibe 8 AC-23 — Mobile hat den separaten Stift-Button
  `+page.svelte:211-217`)
- **File (b, zentraler Save):** `frontend/src/lib/components/compare/CompareEditor.svelte:72`
  (`compareSaveCtl = createSaveStatus()`), `:182-218` (`dirty`-`$derived` +
  Sync-`$effect` nach `compareSaveCtl`, ruft nie `.schedule()`),
  `:297-410` (`handleSave`, PUT via `buildComparePresetSavePayload`),
  `:900-908` („Verwerfen"/„Speichern"-Buttons, edit-Modus Desktop),
  `:739-745` (mobiler „Speichern"-Button in der Top-App-Bar),
  `:1432-1434` (`SaveIndicator`), `:1437-1456` (`ConfirmDialog` „Verwerfen")
- **File (b, Save-Infrastruktur, wiederverwendet):** `frontend/src/lib/stores/saveStatusStore.svelte.ts`
  (`SaveStatus.schedule()`/`.flush()`/`.hasPending`, bereits vorhanden,
  700 ms Default — kein neuer Mechanismus nötig)
- **File (b, Edit-Route):** `frontend/src/routes/compare/[id]/edit/+page.svelte`
  (kein `beforeNavigate`-Flush; Referenzmuster: `frontend/src/routes/trips/[id]/+page.svelte:5-6,22,25-34`,
  `tripSaveCtl = createSaveStatus()` + `beforeNavigate(({cancel,to,willUnload}) => ...)`)
- **File (b, Gesten-Gate-Vorbild, wiederverwendet):** `frontend/src/lib/components/trip-detail/weatherSaveGate.ts:39-43`
  (`weatherSaveGate({catalogLoaded, userTouched}) → 'save'|'skip'`, reine
  Funktion, context-agnostisch), Einhängung als Capture-Listener-Vorbild:
  `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte:781-787`
  (`onpointerdowncapture`/`onkeydowncapture`/`onchangecapture`/`oninputcapture`)
- **File (Backend, unverändert):** `internal/handler/compare_preset.go:331-342`
  (Update-RMW), Router `PUT /api/compare/presets/{id}` — funktioniert bereits

## Estimated Scope

- **LoC:** ~150-200 (innerhalb des 250-LoC-Workflow-Limits, kein Override
  erwartet)
- **Files:** ~4-5 Frontend-Dateien MODIFY + 1 wiederverwendetes Modul (kein
  Change) + 2-4 neue Testdateien
- **Effort:** medium (Speicher-Pfad mit Datenverlust-Historie #1234/GR221,
  daher hoher Sorgfaltsanspruch trotz kleinem Diff)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | (a) sichtbarer Desktop-Header-„Bearbeiten"-Button + erweiterte Kebab-Aktionsliste für `active`/`paused` |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | MODIFY (evtl.) | (a) neue/erweiterte Actions-Liste NUR für den Desktop-Detail-Call-Site — `compareLifecycleActions()` selbst bleibt für Mobile unverändert |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | (b) debounced Auto-Save-`$effect`, Gesten-Gate-Capture-Listener am Editor-Root, ggf. Verwerfen-Dialog-Copy |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | MODIFY | (b) `beforeNavigate`-Flush analog `routes/trips/[id]/+page.svelte:25-34` |
| `frontend/src/lib/components/trip-detail/weatherSaveGate.ts` | REUSE (kein Change) | (b) Gesten-Gate-Entscheidungsfunktion wiederverwendet (context-agnostisch) |
| `frontend/src/lib/components/mobile/MCompareActionSheet.svelte` | VERIFY (kein Change erwartet) | (a) Regressionsnachweis: bleibt ohne `edit`-Eintrag |
| `frontend/e2e/compare-detail-edit-entry.spec.ts` | CREATE | (a) Staging-E2E für AC-1…AC-4 |
| `frontend/e2e/compare-editor-autosave.spec.ts` | CREATE | (b) Staging-E2E für AC-5…AC-11, AC-14 |
| `frontend/e2e/compare-editor-autosave-user-isolation.spec.ts` | CREATE | (b) Zwei-Nutzer-Isolationstest AC-12 |
| Kern-Unit-Test(s) für die erweiterte Kebab-Aktionsliste | CREATE | (a) logik-seitiger Nachweis AC-2/AC-3/AC-4 (Namensregel-konform, siehe Test Coverage) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `weatherSaveGate.ts` (`weatherSaveGate()`) | Frontend-Modul | #1234-Gesten-Gate-Logik wiederverwendet (context-agnostisch, keine Compare-eigene Neuimplementierung) |
| `saveStatusStore.svelte.ts` (`SaveStatus.schedule/flush/doSave/hasPending`) | Frontend-Modul | Bestehender Debounce-/Save-Status-Mechanismus, bereits als `compareSaveCtl` instanziiert (Issue #758) |
| `compareEditorSave.ts` (`buildComparePresetSavePayload`) | Frontend-Modul | RMW-sicherer PUT-Payload-Aufbau, bereits vorhanden und unverändert |
| `subscriptionHelpers.ts` (`compareActions`, `compareLifecycleActions`) | Frontend-Modul | Bestehende Aktions-Baupläne, Referenz für Kebab-Erweiterung Teil (a) |
| `PUT /api/compare/presets/{id}` (`internal/handler/compare_preset.go`) | Go-API | Persistenz-Endpoint, existiert & funktioniert, unverändert |
| `routes/trips/[id]/+page.svelte` (`beforeNavigate`-Flush, `createSaveStatus`) | Frontend-Referenz | Trip-Autosave-Fädelungsmuster als Vorbild (1:1-Spiegelung lt. PO) |
| `docs/specs/modules/issue_1234_autosave_hydration_gate.md` | Spec-Referenz | Ursprungs-Spec des Gesten-Gate-Musters, Entscheidungstabelle wird übernommen |
| Issue #1230 (Konvergenz-Epic) | Programm | Zielbild volle Save-Wiring-Konvergenz (Ansatz B) — hier NICHT umgesetzt |
| Issue #1258 (laufend, S5/S6) | Parallel-Workflow | Aktive Arbeit am selben `CompareEditor.svelte` — vor Implementierung erneut gegen `origin/main` prüfen |
| `docs/specs/modules/issue_1256_compare_ui_rewire.md` (AC-23) | Spec-Referenz | Begründet, warum `compareLifecycleActions()` NICHT pauschal um `edit` erweitert werden darf (Mobile-Sheet-Regression) |

## Implementation Details

### (a) Bearbeiten auffindbar machen

1. **Desktop-Header-Button:** In `routes/compare/[id]/+page.svelte:171-180` wird
   für `status !== 'draft'` neben dem bestehenden Primärbutton („Test senden")
   ein sichtbarer „Bearbeiten"-Button ergänzt, der auf `/compare/{id}/edit`
   navigiert (nutzt denselben Pfad wie der bereits existierende, aber tote
   `handleAction('edit')`-Zweig, `:100-102`).
2. **Desktop-⋮-Menü:** Der Kebab-Aufruf an dieser Stelle (`:179`) bekommt eine
   um `{id:'edit', label:'Bearbeiten'}` erweiterte Aktionsliste — für
   `status === 'active' | 'paused'`. Diese Erweiterung darf **ausschließlich**
   den Desktop-Detail-Call-Site betreffen (z. B. Inline-Zusammenführung mit
   `compareActions()`-Teilmenge oder ein neuer, eng begrenzter Helper),
   **nicht** die Funktion `compareLifecycleActions()` selbst — die wird auch
   vom Mobile-Sheet (`MCompareActionSheet.svelte:31`) genutzt, das laut
   #1256-Scheibe-8-AC-23 bewusst ohne `edit`-Eintrag bleiben soll (Mobile hat
   den separaten Stift-Button).
3. **Draft-Status:** unverändert — der bestehende „Setup abschließen"/„Setup
   fortsetzen"-Einstieg deckt Draft bereits ab, kein neuer Button nötig.
4. **Mobile:** keine Code-Änderung erwartet (Stift-Icon `:211-217` und
   `MCompareActionSheet.svelte` bleiben wie sie sind) — wird als
   Regressionstest (AC-3) abgesichert, nicht neu gebaut.

### (b) Autospeichern nachrüsten (Ansatz A — zentraler Auslöser, gelockt)

Der Compare-Editor behält seine zentrale, RMW-sichere Save-Logik
(`handleSave`/`buildComparePresetSavePayload`, Dirty-/Reset-Tracking); es
kommt **nur** ein automatischer Auslöser samt Sicherheitsnetz hinzu — kein
Umbau der geteilten Tabs (CorridorEditor/VersandTab/AlarmeTab), kein Eingriff
in deren `route`-Zweig.

1. **Debounced Auto-Save:** Ein neuer `$effect` in `CompareEditor.svelte`
   beobachtet dieselbe `dirty`-Quelle, die bereits den Statuswechsel treibt
   (`:182-218`), und ruft bei `dirty === true` `compareSaveCtl.schedule(() =>
   Promise.resolve(handleSave()))` (oder eine promise-basierte Variante von
   `handleSave`) statt nur `setDirty()`. Debounce bleibt beim vorhandenen
   `SaveStatus`-Default von 700 ms (Trip-Parität, keine neue Konstante).
2. **beforeNavigate-Flush:** `routes/compare/[id]/edit/+page.svelte` bekommt
   einen `beforeNavigate`-Handler nach dem Muster
   `routes/trips/[id]/+page.svelte:25-34`: `cancel()` + `saveCtl.flush()` +
   danach `goto(target)`, sofern `hasPending` true ist. Dafür muss die
   `compareSaveCtl`-Instanz aus `CompareEditor.svelte` an die Edit-Route
   durchgereicht werden (z. B. über Context/Prop-Rückkanal — Wahl der
   Verdrahtung ist Implementierungsdetail, solange die Instanz pro Editor
   nicht zum Singleton wird, Issue #758 AC-6).
3. **#1234-Gesten-Gate:** Ein Capture-Listener-Wrapper um den Editor-Root
   (Vorbild `WeatherMetricsTab.svelte:781-787`:
   `onpointerdowncapture`/`onkeydowncapture`/`onchangecapture`/`oninputcapture`)
   setzt ein `userTouched`-Flag. Der neue Auto-Save-`$effect` schreibt nur,
   wenn `weatherSaveGate({catalogLoaded: true, userTouched}) === 'save'`
   liefert (im Compare-Editor ist „catalogLoaded" faktisch immer `true`, da
   die Edit-Route synchron aus SSR-Daten hydriert — die Funktion bleibt aber
   unverändert wiederverwendet, kein Compare-eigener Fork). Ohne Geste bleibt
   der `$effect` bei reinem `setDirty()`-Verhalten ohne Schreibzugriff, exakt
   wie vor diesem Fix — verhindert, dass geteilte-Tab-interne
   Hydrations-`$effect`e (z. B. CorridorEditor-Dual-Write in `wiz.corridors`)
   unbeabsichtigt einen Schreibzugriff auslösen (dieselbe Fehlerklasse wie
   #1234 F001).
4. **Statuspille:** `SaveIndicator` (`:1432-1434`) bleibt unverändert
   eingebunden — zeigt jetzt automatische Zustandswechsel statt nur
   button-getriebene.
5. **„Speichern"-Button:** bleibt als manueller Sofort-Auslöser erhalten
   (kein Entfernen der UI — das wäre Restrukturierung, Out of Scope). Er wird
   durch Autosave redundant-sicher: ein Klick während ein Auto-Save
   aussteht/läuft darf zu keinem widersprüchlichen Endzustand führen (idempotenter
   PUT, letzter `wiz`-Snapshot gewinnt).
6. **„Verwerfen"-Button:** bleibt als Navigation zurück zum Hub bestehen,
   verliert aber ab Ablauf des Debounce-Fensters die Fähigkeit, eine bereits
   automatisch gespeicherte Änderung zurückzurollen — das ist beabsichtigt und
   spiegelt den Trip, der gar keine Verwerfen-Funktion besitzt (jede Änderung
   greift dort sofort). Text/Copy-Anpassung des `ConfirmDialog`
   (`:1437-1456`), falls die bestehende Formulierung „Alle Änderungen ...
   werden verworfen" nach dem Fix irreführend wäre, ist Teil der
   Implementierung.

### Invarianten (dürfen sich NICHT ändern)

- Der `route`-Zweig der geteilten Tabs (CorridorEditor/VersandTab/AlarmeTab)
  bleibt byte-identisch — dieser Fix fasst ausschließlich `CompareEditor.svelte`
  und den Compare-Edit-Routing-Pfad an.
- Keine neue Compare-Komponente mit existierendem Trip-Pendant
  (Teilungs-Invariante, `feedback_trip_compare_sharing_invariant`).
- Multi-User-Isolation: Autosave nutzt ausschließlich die bereits im Editor
  vorhandene `preset.id`/echte `user_id` aus dem Auth-Kontext — kein neuer
  ID-Auflösungspfad, kein `"default"`-Fallback.
- `compareLifecycleActions()` als Funktion bleibt für den Mobile-Call-Site
  unverändert (kein `edit`-Eintrag) — nur der Desktop-Detail-Call-Site bekommt
  eine erweiterte Liste.

## Expected Behavior

- **Input:** Nutzeraktionen im Compare-Editor (Orte wählen/abwählen,
  Wertebereich/Korridor ändern, Kanäle/Zeitplan im Versand-Tab ändern);
  Klick auf „Bearbeiten" auf der Compare-Detailseite (Desktop-Header oder
  ⋮-Menü); Navigation weg vom Editor.
- **Output:** Automatischer, debounced `PUT /api/compare/presets/{id}` mit
  konsolidiertem Payload bei echter Nutzergeste; sofortiger Flush ausstehender
  Änderungen vor Navigation; sichtbarer „Bearbeiten"-Einstieg auf der
  Desktop-Detailseite (Button + Kebab-Eintrag).
- **Side effects:** Keine Schema-Änderung (kein `data_schema_backup.py`-Trigger
  erwartet — nur Frontend-Dateien betroffen). Kein neuer Backend-Endpoint.

## Acceptance Criteria

**AC-1:** Given ich habe einen Ortsvergleich im Status „active" oder „paused" und öffne dessen Detailseite auf dem Desktop / When die Seite geladen ist / Then sehe ich im Kopfbereich einen sichtbaren „Bearbeiten"-Button, der beim Klick auf `/compare/{id}/edit` navigiert.
  - Test: Playwright klickt auf den Header-Bearbeiten-Button und prüft die Ziel-URL.

**AC-2:** Given ich bin auf der Compare-Detailseite (Desktop, Status „active" oder „paused") / When ich das ⋮-Menü öffne / Then enthält die Liste zusätzlich zu Pausieren/Aktivieren, Archivieren, Löschen einen Eintrag „Bearbeiten", der auf `/compare/{id}/edit` navigiert.
  - Test: Playwright öffnet den Kebab, klickt „Bearbeiten", prüft die Ziel-URL.

**AC-3:** Given das mobile Bottom-Sheet der Compare-Detailseite (`MCompareActionSheet`) / When es für einen Vergleich im Status „active" oder „paused" geöffnet wird / Then enthält es weiterhin KEINEN „Bearbeiten"-Eintrag — die #1256-Scheibe-8-Entscheidung (AC-23) bleibt unverändert, Mobile nutzt den separaten Stift-Button.
  - Test: Component-/Playwright-Regressionstest prüft, dass `compareLifecycleActions()`-Ergebnis für Mobile keinen `edit`-Eintrag enthält.

**AC-4:** Given ein Ortsvergleich im Status „draft" / When ich die Detailseite öffne / Then bleibt der bestehende „Setup abschließen"-Einstieg unverändert, und es erscheint KEIN zusätzlicher „Bearbeiten"-Button oder -Kebab-Eintrag für Draft.
  - Test: Playwright öffnet Draft-Detailseite, prüft Abwesenheit eines „Bearbeiten"-Buttons/-Eintrags neben dem bestehenden „Setup abschließen".

**AC-5:** Given ich bin im Compare-Editor (edit-Modus) auf einem beliebigen Tab / When ich eine echte Nutzergeste ausführe, die einen Feldwert ändert (z. B. einen Ort abwählen) / Then wird die Änderung ohne Klick auf „Speichern" automatisch gespeichert — spätestens nach dem Debounce-Fenster (~700 ms) erfolgt genau ein `PUT` auf `/api/compare/presets/{id}` mit dem geänderten Feld.
  - Test: Playwright fängt Netzwerk-Requests ab, ändert einen Ort, prüft genau einen debounced PUT mit dem erwarteten `location_ids`-Wert — kein Klick auf „Speichern".

**AC-6:** Given ich ändere im Compare-Editor mehrere Felder kurz hintereinander innerhalb des Debounce-Fensters (z. B. Ort und Kanal) / When die Auto-Save-Logik greift / Then wird genau EIN konsolidierter `PUT`-Request ausgelöst, der beide Änderungen enthält — nicht ein Request pro Feld.
  - Test: Playwright ändert zwei Felder in schneller Folge, zählt die PUT-Requests im Debounce-Fenster — genau einer.

**AC-7:** Given ich öffne den Compare-Editor im edit-Modus und führe KEINE Nutzergeste aus (kein Klick, keine Eingabe, keine Auswahl) / When ich unmittelbar wieder wegnavigiere / Then wird KEIN `PUT`-Request an `/api/compare/presets/{id}` gesendet — null Schreibzugriffe ohne echte Nutzerinteraktion.
  - Test: Playwright öffnet den Editor, wartet auf vollständiges Hydrieren, navigiert ohne Interaktion weg, prüft Netzwerk-Log auf null PUT-Requests. Dieser Test ist rot vor dem Fix (falls Hydrations-Effekte fälschlich schreiben würden) und grün danach — Gesten-Gate-Bug-Nachweis analog #1234.

**AC-8:** Given eine Änderung ist noch nicht geflusht (innerhalb des Debounce-Fensters) / When ich per Link/Navigation den Compare-Editor verlasse / Then wird die ausstehende Änderung vor dem Verlassen sofort gespeichert (`beforeNavigate`-Flush), und die Navigation erfolgt erst nach Abschluss des Speicherns.
  - Test: Playwright ändert ein Feld, navigiert sofort (< 700 ms) weg, prüft dass ein PUT vor dem Erreichen der Zielseite abgeschlossen wurde und die Änderung nach Reload persistiert ist.

**AC-9:** Given die Statuspille (`SaveIndicator`) im Compare-Editor / When eine Änderung automatisch gespeichert wird / Then durchläuft die Pille sichtbar die Zustände „wird gespeichert" → „gespeichert", ohne dass manuell auf „Speichern" geklickt wird.
  - Test: Playwright ändert ein Feld, prüft den sichtbaren Text/Testid-Zustand der Statuspille im zeitlichen Verlauf ohne Button-Klick.

**AC-10:** Given Autosave ist aktiv und ein automatischer Save steht aus oder läuft / When ich zusätzlich manuell auf „Speichern" klicke / Then führt dies zu keinem Datenverlust und keinem widersprüchlichen Endzustand — der zuletzt geschriebene Serverstand entspricht dem zuletzt bekannten Editor-Zustand (idempotenter PUT, kein Request-Fehler durch Doppelpfad).
  - Test: Playwright ändert ein Feld und klickt sofort „Speichern" während der Debounce-Timer noch läuft, prüft nach Abschluss beider Requests den finalen Serverzustand per GET.

**AC-11:** Given Autosave hat eine Änderung bereits gespeichert (Debounce-Fenster abgelaufen, Status nicht mehr „dirty") / When ich danach auf „Verwerfen" klicke / Then navigiert der Button zurück zum Hub, OHNE die bereits serverseitig gespeicherte Änderung rückgängig zu machen — analog zum Trip-Editor, der keine Verwerfen-Funktion besitzt.
  - Test: Playwright ändert ein Feld, wartet Debounce+Flush ab, klickt „Verwerfen", lädt den Hub neu und prüft, dass die Änderung erhalten geblieben ist.

**AC-12:** Given zwei verschiedene Nutzer mit je einem eigenen Ortsvergleich / When Nutzer A eine Autosave-Änderung an seinem Vergleich auslöst / Then bleibt der Vergleich von Nutzer B unverändert — der PUT trifft ausschließlich `/api/compare/presets/{eigene_id}` des angemeldeten Nutzers, kein Cross-User-Schreibzugriff.
  - Test: Staging-E2E mit zwei separaten eingeloggten Sessions (zwei Test-User), Autosave-Änderung bei User A auslösen, per GET verifizieren dass User Bs Preset unverändert ist.

**AC-13:** Given der Trip-Editor nutzt dieselben geteilten Tabs (CorridorEditor/VersandTab/AlarmeTab) im `context="route"`-Zweig / When der Compare-Autosave-Fix implementiert ist / Then verhält sich der Trip-Editor byte-identisch wie vor dem Fix — keine Codeänderung an den geteilten Tab-Komponenten selbst, bestehende Trip-Autosave-Tests bleiben unverändert grün.
  - Test: `git diff` gegen `frontend/src/lib/components/shared/**` zeigt keine Änderung; bestehende Trip-Autosave-Testsuite läuft unverändert grün durch.

**AC-14:** Given die drei vom Bug-Report genannten Bereiche — Orte (Ortsauswahl), Wertebereich (Idealwerte/Korridor) und Versand (Kanäle/Zeitplan) / When jeweils eine echte Nutzergeste in genau diesem Bereich ausgeführt wird / Then löst jeder der drei Bereiche unabhängig einen debounced Auto-Save aus — kein Bereich bleibt beim alten manuellen „Speichern"-Zwang zurück.
  - Test: Drei Playwright-Szenarien (Orte-Tab, Wertebereich-Tab, Versand-Tab), je eine Geste, je ein beobachteter debounced PUT mit dem passenden geänderten Feld.

## Known Limitations

- **Keine Routen-Verschmelzung:** Detail (`/compare/[id]`) und Editor
  (`/compare/[id]/edit`) bleiben getrennte Routen — anders als beim Trip
  (Detailseite = Editor). Diese strukturelle Verschmelzung ist
  Konvergenz-Epic **#1230**, nicht Teil von #1261.
- **Keine volle Save-Wiring-Konvergenz:** Ansatz B (verteiltes Autospeichern
  über die geteilten Tabs, `saveController` an CorridorEditor/VersandTab/
  AlarmeTab im `vergleich`-Zweig durchreichen) ist bewusst NICHT gewählt —
  gehört ebenfalls zu #1230.
- **„Verwerfen" verliert Rollback-Fähigkeit nach Debounce-Ablauf:** Sobald
  eine Änderung automatisch gespeichert wurde (~700 ms nach der Geste), kann
  „Verwerfen" sie nicht mehr zurückrollen. Akzeptierter Trade-off, der exakt
  das Trip-Verhalten spiegelt (Trip kennt gar keine Verwerfen-Funktion, jede
  Änderung greift sofort).
- **Draft-Status unverändert:** #1261 fügt für Status „draft" keinen neuen
  Bearbeiten-Einstieg hinzu — der bestehende „Setup abschließen"/„Setup
  fortsetzen"-Pfad bleibt zuständig und ist von diesem Fix nicht betroffen.
- **Parallele Arbeit am selben Editor:** Issue #1258 (Scheiben S5/S6) arbeitet
  aktiv an `CompareEditor.svelte`/`CompareTabs.svelte`. Vor Implementierung
  ist der Stand erneut gegen `origin/main` zu prüfen (Merge-Konflikt- und
  Kollisionsgefahr).

## Out of Scope

- Strukturelle Verschmelzung von Compare-Detail und Compare-Editor zu einer
  Route (Epic #1230).
- Verteiltes Autospeichern über die geteilten Tabs (Ansatz B, Epic #1230).
- Neue Backend-Endpunkte oder Änderungen an `compare_preset.go` — der
  bestehende `PUT`-Endpunkt wird unverändert weiterverwendet.
- Änderungen am Compare-Hub (`CompareTabs.svelte`) oder am Create-Wizard —
  betroffen ist ausschließlich der Edit-Pfad (`mode="edit"`) und die
  Detailseite.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bug-Fix ohne neues Architekturmuster — wiederverwendet
  ausschließlich bestehende, bereits etablierte Bausteine (`SaveStatus`
  Debounce/Flush aus Issue #758, `weatherSaveGate`-Gesten-Gate aus Issue
  #1234, `buildComparePresetSavePayload` aus Issue #679/#1258). Das
  Datenmodell und der Persistenz-Endpoint bleiben unverändert. Die
  strukturelle Entscheidung (getrennte vs. verschmolzene Compare-Routen)
  wird bewusst NICHT in diesem Issue getroffen, sondern bleibt Konvergenz-Epic
  #1230 vorbehalten.

## Test Coverage

### Kern-Tests (deterministisch, Vitest/node:test, KEINE Mocks als Verhaltensnachweis)

- `compareDetailEditActions.test.ts` — reine Funktionslogik der erweiterten
  Desktop-Kebab-Aktionsliste: `edit`-Eintrag vorhanden für „active"/„paused",
  abwesend für „draft" (AC-2, AC-4 logik-seitig)
- Regressionstest `compareLifecycleActions()` unverändert: kein `edit`-Eintrag
  im Rückgabewert, für alle Status (AC-3 logik-seitig)
- `weatherSaveGate.test.ts` (bereits vorhanden, unverändert) — Gesten-Gate
  bleibt Referenz-Beleg für die wiederverwendete Entscheidungsfunktion (AC-7
  logik-seitig)
- Falls eine neue Konsolidierungs-/Wrapper-Funktion für den Auto-Save-Payload
  entsteht: reiner Funktionstest ohne DOM (AC-6 logik-seitig)

### Staging-E2E (Marker `live`/`staging`, Playwright gegen echten Login, echter Klick-Pfad)

- `compare-detail-edit-entry.spec.ts` — Desktop-Header-Button + Kebab-Eintrag
  + Mobile-Regression + Draft-Ausnahme (AC-1, AC-2, AC-3, AC-4)
- `compare-editor-autosave.spec.ts` — debounced PUT bei Geste, konsolidierter
  Multi-Feld-PUT, Null-PUT-Gegenprobe ohne Geste, `beforeNavigate`-Flush,
  SaveIndicator-Zustandswechsel, Speichern-Klick-Kollision, Verwerfen-Semantik
  nach Debounce-Ablauf, alle drei Bereiche Orte/Wertebereich/Versand
  (AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-14)
- `compare-editor-autosave-user-isolation.spec.ts` — Zwei-Sessions-Test
  (AC-12)
- Bestehende Trip-Autosave-Testsuite (unverändert, als Regressionsnachweis
  AC-13)

**Namensregel:** Testdateien nach Verhalten benennen (wie oben), NICHT nach
Issue-Nummer (`test_naming_gate.py` blockt neue issue-nummerierte
Testdateien). AC-7 ist der primäre Bug-Reproduktionsnachweis (rot vor Fix,
grün danach) — Nutzersicht: „ich ändere nichts, aber es wird nichts kaputt
geschrieben" bzw. umgekehrt AC-5 „ich ändere etwas, und es bleibt erhalten,
ohne dass ich Speichern klicke".

## Changelog

- 2026-07-15: Initial spec created (Issue #1261, Workflow
  `fix-1261-compare-edit-save`). Analyse-Basis: `docs/context/fix-1261-compare-edit-save.md`
  (PO-Richtungsentscheid „Ortvergleich soll sich so verhalten wie Trips!!!!!!!",
  Ansatz A für Autospeichern gelockt, Scope-Grenze gegen Epic #1230 gezogen).
