---
entity_id: trip_stage_date_editing
type: bug
created: 2026-07-25
updated: 2026-07-25
status: approved
version: "1.0"
tags: [frontend, mobile, trip-editor, cascade, autosave, data-loss]
---

# Trip-Etappen-Datum: Kaskaden-Dialog mobil unsichtbar + stiller Datenverlust

## Approval

- [x] Approved
- PO-Freigabe 2026-07-25 (go), inkl. Entscheidung: still speichern statt warnen

## Purpose

Zwei zusammenhängende Bugs auf derselben Oberfläche (Etappen-Datum-Bearbeitung,
`/trips/{id}?tab=stages`) werden gemeinsam behoben: (1) der Kaskaden-Rückfrage-Dialog
beim Verschieben des Tourstarts ist auf Mobilgeräten unsichtbar unterhalb des
Viewports (#1375), (2) eine Datumsänderung an einer mittleren Etappe oder einem
Pausentag geht kommentarlos verloren, wenn die Seite innerhalb des 700ms-Auto-Save-
Fensters verlassen oder neu geladen wird (#1376, Datenverlust-Risiko).

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
- **Identifier:** `@media (max-width: 899px) { .mobile-editor { order: -1; } }` (Bug #1375),
  `handleDateChange()` (unverändert korrekt, nur Kontext)
- **File:** `frontend/src/routes/trips/[id]/+page.svelte`
- **Identifier:** `beforeNavigate(({ cancel, to, willUnload }) => { ... })` (Bug #1376)
- **File:** `frontend/src/lib/components/molecules/StageCascadeNotice.svelte`
- **Identifier:** gesamte Komponente (toter Code, wird im Zuge von #1375 entfernt)

**Schicht:** Frontend (`frontend/src/...`, SvelteKit) — kein Go-API-/Python-Core-Anteil.

## Estimated Scope

- **LoC:** ~+55/-135 (netto negativ durch Löschung toten Codes; Doku zählt nicht mit)
- **Files:** 6 (4 Code, 2 Test)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `computeCascadeDelta`, `addDays` (`frontend/src/lib/components/edit/cascade.ts`) | ts-Modul | Berechnet Tagesdifferenz für den Kaskaden-Vorschlag — bleibt unverändert |
| `SaveStatus.hasPending`, `SaveStatus.flush()` (`frontend/src/lib/stores/saveStatusStore.svelte.ts`) | Klasse | Bereits vorhandene Bausteine für Bug #1376 — liefern Pending-Zustand und erzwungenes Sofort-Speichern |
| `beforeNavigate` (`$app/navigation`) | SvelteKit-API | Fängt SPA-interne Navigationen ab; `willUnload=true` markiert echte Browser-Navigation/Reload, die bisher ungeflusht bleiben |
| `expectWithinViewport()` (`frontend/e2e/mobile-editor-controls-viewport.spec.ts:75`) | Test-Helfer | Bereits vorhandene, echte Viewport-Sichtbarkeitsprüfung — wird auf den Cascade-Strip erweitert statt eines neuen Helfers |
| `data-testid="cascade-strip"` / `"stage-switcher-pill"` / `"add-waypoint"` | UI-Contract | Von E2E-Tests referenzierte Elemente, deren Sichtbarkeit AC-1 bis AC-3 beweisen |

## Implementation Details

### Bug #1375 — Kaskaden-Dialog mobil unsichtbar

Root Cause (verifiziert): `.mobile-editor { order: -1 }` zieht den Kartenblock per
Flex-`order` vor den Etappen-Header, OHNE die DOM-Reihenfolge zu ändern. Der
Cascade-Strip (`<div class="cascade-prompt" data-testid="cascade-strip">`) liegt im
Markup verschachtelt innerhalb des padding-Wrappers (`position:relative;
padding:20px 40px 60px`), der selbst ein regulärer Flex-Kind-Block ohne eigenen
`order`-Wert ist — er rutscht daher komplett unter die per `order:-1` vorgezogene
Karte und landet bei y≈1102px, weit unter dem 844px hohen Standard-Viewport.

Empfohlener Ansatz: Den Cascade-Strip (nur den Fall `cascade && activeStageIndex
=== 0`, also ausschließlich die Kaskaden-Rückfrage bei Verschiebung der ersten
Etappe) als eigenständigen, direkten Flex-Kind-Block rendern — nicht mehr
verschachtelt im padding-Wrapper — und mit `order` so positionieren, dass er auf
Mobil direkt nach `.mobile-editor` erscheint (z.B. gleicher `order:-1`-Wert; die
DOM-Reihenfolge zwischen zwei Elementen mit identischem `order` entscheidet dann,
sodass der Strip nach der Karte, aber vor `EtappenStrip`/Header sichtbar wird).
Auf Desktop (`editor-grid` sichtbar, `mobile-editor` `display:none`) darf sich am
bisherigen visuellen Ort/Verhalten nichts ändern. Alternative: den Strip als
Overlay/Banner *innerhalb* von `.mobile-editor` rendern (analog zur bereits
vorhandenen `stage-switcher-pill`-Positionierung) — beide Ansätze sind zulässig,
solange AC-1/AC-2/AC-3 erfüllt sind.

**Nebenaufräumen (Teil dieses Fixes):** `frontend/src/lib/components/molecules/
StageCascadeNotice.svelte` (#578) ist eine zweite, inhaltlich identische
Implementierung derselben Rückfrage. Verifiziert per grep: außerhalb ihres
eigenen Tests (`issue_578_molecules_organisms.test.ts`) und des Exports in
`molecules/index.ts` gibt es KEINE Verwendung — die produktiv sichtbare Kaskade
läuft ausschließlich über den inline `cascade-prompt`-Block in
`EditStagesPanelNew.svelte`. Komponente, Export-Zeile und der zugehörige Test
(nur Datei­inhalt-Assertions wie `/g-accent-tint/.test(src)` — genau das Muster,
das die Projekt-Testpolitik als Verhaltensnachweis ausschließt) werden entfernt.

### Bug #1376 — Stiller Datenverlust bei mittlerer Etappe / Pausentag

Root Cause (verifiziert): `frontend/src/routes/trips/[id]/+page.svelte:25-34` —
`beforeNavigate` steigt bei `willUnload` bewusst aus („Browser-Navigation, kein
Flush möglich"), der 700ms-Auto-Save-Debounce (`SaveStatus.schedule()`) läuft
dann ins Leere. Der Kaskaden-Pfad (erste Etappe, „Alle mitverschieben") ist davon
NICHT betroffen, da `applyCascade()` bereits synchron/`await`-basiert ohne
Debounce speichert, bevor der Nutzer weiterklicken kann.

**PO-Entscheidung 2026-07-25:** Die Änderung muss still zuverlässig gespeichert
werden — KEINE Warn-Rückfrage/Bestätigungsdialog beim Verlassen der Seite (würde
im Alltag stören). Eine `beforeunload`-Warnung des Browsers oder ein eigener
`ConfirmDialog` vor dem Verlassen ist damit **verworfen** und nicht Teil dieses
Fixes. Umzusetzen ist ein zuverlässiger Best-Effort-Flush im `willUnload`-Fall,
z.B. über `navigator.sendBeacon` oder einen synchron ausgelösten
`fetch(..., {keepalive: true})`-Aufruf im `beforeNavigate`-Handler, gestützt auf
die bereits vorhandene `SaveStatus`-API (`hasPending`, `flush()`).

## Expected Behavior

- **Input:** Nutzer ändert im Etappen-Tab (`?tab=stages`) das Datum einer Etappe
  — Tourstart, mittlere Etappe oder Pausentag — auf Mobil oder Desktop.
- **Output:** Bei Tourstart-Verschiebung erscheint die Kaskaden-Rückfrage
  sichtbar im Bildschirmausschnitt, unabhängig von Viewport-Größe. Bei jeder
  Datumsänderung bleibt die Änderung auch dann erhalten, wenn die Seite kurz
  danach verlassen/neu geladen wird — ohne Warn-Rückfrage, die Speicherung
  läuft still im Hintergrund ab.
- **Side effects:** `StageCascadeNotice.svelte` und ihr toter Test entfallen
  ersatzlos; keine Verhaltensänderung an der produktiv genutzten Kaskaden-Logik.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit mindestens zwei Etappen ist im Etappen-Tab auf
  einem mobilen Viewport (≤899px, z.B. 390×844) geöffnet und die erste Etappe
  ist aktiv / When der Nutzer das Datum der ersten Etappe im Etappen-Header
  ändert / Then wird der Kaskaden-Dialog „Tourstart um ±N Tage verschoben. Sollen
  die N Folge-Etappen um denselben Betrag mitverschoben werden?" mit den
  Schaltflächen „Alle mitverschieben" und „Nur diese Etappe" vollständig
  sichtbar im Bildschirmausschnitt angezeigt, ohne dass manuell gescrollt werden muss.
  - Test: `frontend/e2e/mobile-editor-controls-viewport.spec.ts`, Viewport
    390×844, Datumsfeld ändern, danach `expectWithinViewport(page,
    'cascade-strip')` (bestehender Helfer) — beweist echte Sichtbarkeit ohne
    vorheriges Scrollen.

- **AC-2:** Given der Kaskaden-Dialog ist nach AC-1 sichtbar / When der Nutzer
  den Bildschirm ohne zu scrollen betrachtet / Then bleiben die mit #963
  gesicherten Kartensteuerelemente (Etappenwechsel-Pille, Wegpunkt-hinzufügen-
  Button) zusätzlich zum Kaskaden-Dialog vollständig sichtbar und anklickbar —
  kein Regress der #963-Lösung durch diesen Fix.
  - Test: gleicher Testlauf wie AC-1, ergänzte Prüfung `expectWithinViewport` +
    `expectTopmostAt` für `stage-switcher-pill` und `add-waypoint`, ohne den
    bisherigen manuellen `scrollTo(0,0)`-Workaround.

- **AC-3:** Given der bisherige Testfall „AC-4: sichtbarer Cascade-Strip" in
  `mobile-editor-controls-viewport.spec.ts` prüfte Sichtbarkeit nur direkt nach
  einem automatisch scrollenden `.fill()`-Aufruf / When dieser Testfall nach dem
  Fix läuft / Then misst er die tatsächliche Bounding-Box des Cascade-Strips im
  Viewport (wie `expectWithinViewport` es für die anderen Steuerelemente bereits
  tut) statt nur `toBeVisible()` — ein erneutes Verstecken des Dialogs unter der
  Karte lässt diesen Test wieder rot werden.
  - Test: `frontend/e2e/mobile-editor-controls-viewport.spec.ts`, umgebauter
    „AC-4"-Testfall; verifiziert durch testweises Wiederherstellen der alten
    `order:-1`-Regel ohne Cascade-Umbau und Beobachten, dass der Test dann
    tatsächlich rot wird.

- **AC-4:** Given `StageCascadeNotice.svelte` (#578) ist eine seit ihrer
  Einführung nirgends im produktiven UI eingebundene Zweitvariante desselben
  Kaskaden-Dialogs / When dieser Fix umgesetzt wird / Then sind die Komponente,
  ihr Export aus `molecules/index.ts` und der zugehörige, ausschließlich
  dateiinhaltsprüfende Test entfernt, und die produktiv sichtbare Kaskaden-
  Dialog-Logik bleibt vollständig in `EditStagesPanelNew.svelte` unverändert
  funktionsfähig (Desktop + Mobil).
  - Test: Build/Typecheck bleibt grün (kein verbliebener Import der entfernten
    Komponente); AC-1/AC-2/AC-3 beweisen weiterhin funktionierendes Kaskaden-
    Verhalten nach der Löschung.

- **AC-5:** Given eine mittlere Etappe (nicht die erste) hat eine gerade
  geänderte Datumsänderung, deren automatische Speicherung noch nicht sichtbar
  abgeschlossen ist / When der Nutzer die Seite kurz danach neu lädt oder
  verlässt / Then ist die Datumsänderung nach dem Neuladen weiterhin vorhanden;
  ein stilles Verwerfen findet nicht statt, und es erscheint dabei auch keine
  Rückfrage/Warnung beim Verlassen der Seite.
  - Test: `frontend/e2e/issue-498-stage-date-autosave.spec.ts::AC-1` gegen
    echtes Backend (kein Mock) — vor diesem Fix rot, danach grün.

- **AC-6:** Given ein Pausentag hat eine gerade geänderte Datumsänderung, deren
  automatische Speicherung noch nicht sichtbar abgeschlossen ist / When der
  Nutzer die Seite kurz danach neu lädt oder verlässt / Then ist die
  Datumsänderung nach dem Neuladen weiterhin vorhanden; ein stilles Verwerfen
  findet nicht statt, und es erscheint dabei auch keine Rückfrage/Warnung beim
  Verlassen der Seite.
  - Test: `frontend/e2e/issue-498-stage-date-autosave.spec.ts::AC-5` gegen
    echtes Backend — vor diesem Fix rot, danach grün.

- **AC-7:** Given der Nutzer verschiebt die erste Etappe und bestätigt „Alle
  mitverschieben" (Kaskade) / When die Seite direkt danach neu geladen oder
  verlassen wird / Then bleiben alle Etappendaten wie schon vor diesem Fix
  zuverlässig gespeichert — die #1376-Absicherung darf den bereits
  funktionierenden Sofort-Speicherpfad der Kaskade weder verlangsamen noch
  brechen.
  - Test: `frontend/e2e/issue-498-stage-date-autosave.spec.ts::AC-2` und
    `::AC-4`, bleiben nach dem Fix weiterhin grün.

## Known Limitations

- Der gewählte Speicher-beim-Verlassen-Weg (`keepalive`-Request) ist beim
  Neuladen und bei echter Navigation über `beforeNavigate` zuverlässig. Beim
  tatsächlichen Schließen des Browser-Tabs/Fensters ist er dagegen NICHT für
  jeden Browser garantiert — **mobiles Safari (iOS) ist der bekannte
  Ausreißer**, der `keepalive`-Requests beim Tab-Schließen nachweislich
  abbricht statt sie zu Ende zu senden. Eine Warn-Rückfrage als zusätzliches
  Sicherheitsnetz wurde dafür bewusst nicht gewählt (PO-Entscheidung
  2026-07-25: still speichern, keine Verlassen-Warnung).
- `keepalive`-Requests sind vom Browser auf **maximal 64 KB Nutzlast**
  begrenzt (Fetch-Spezifikation). Bei sehr großen Touren (grob ab ~40 Etappen
  mit vielen Wegpunkten) überschreitet der PUT-Payload dieses Limit, der
  Browser lehnt den Request ab, und die Zusicherung aus AC-5/AC-6 greift dann
  nicht mehr. Kein bekannter Fall im aktuellen Bestand, aber bewusst in Kauf
  genommen statt einer aufwändigeren Teil-Payload-Lösung für einen bislang
  unbeobachteten Rand-Fall.
- Die extremen Mobil-Randfälle aus #963 (Querformat 844×390, iPhone SE 320×568,
  F001/F002) bleiben wie bisher: Karte kollabiert nicht, Steuerelemente sind
  dort weiterhin nur nach Scrollen erreichbar (dokumentierte Out-of-Scope-Grenze
  aus #963) — dieser Fix ändert daran nichts, solange AC-1/AC-2 im
  390×844-Standardfall halten.
- Der Cascade-Banner-Fix betrifft ausschließlich `activeStageIndex === 0`
  (erste Etappe) — für mittlere Etappen/Pausentage existiert konzeptionell kein
  Kaskaden-Dialog (Spec-Definition #498), das bleibt unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix innerhalb bereits etablierter Muster
  (SaveStatus-Controller aus #758, Kaskaden-Mechanik aus #498,
  Mobile-Editor-Map-First-Reorder aus #963) — keine neue Grundsatzentscheidung
  nötig.

## Changelog

- 2026-07-25: Initial spec erstellt — Issues #1375, #1376
- 2026-07-25: PO-Freigabe; AC-5/AC-6 auf „still speichern, keine
  Verlassen-Warnung" geschärft (Warn-Alternative verworfen); Status auf
  `approved` gesetzt
- 2026-07-25: keepalive-64-KB-Grenze und Tab-Schließen-Vorbehalt in Known
  Limitations aufgenommen. Kurzzeitig erwogenes AC-8 (Versand-Reiter) wieder
  gestrichen: dort liegt kein Datenverlust vor, sondern die gewollte
  Stundenkappung aus #1280.
