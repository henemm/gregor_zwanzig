---
entity_id: issue_963_mobile_editor_controls
type: module
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [bugfix, frontend, mobile, editor]
workflow: fix-963-mobile-editor-controls
---

# Mobile Etappen-Editor: Steuerelemente außerhalb Viewport (Issue #963)

## Approval

- [ ] Approved

## Purpose

Im mobilen Etappen-Editor (`/trips/:id?tab=stages`, Viewport <900px) landen `stage-switcher-pill` (Etappenwechsel) und der `add-waypoint`-Button außerhalb des sichtbaren Bereichs. **Korrigierter Befund (2026-07-11, empirisch per RED-Test verifiziert):** Beide Steuerelemente sind `position:absolute; top:12px` relativ zur Oberkante von `.mobile-map-wrap`. Diese Oberkante liegt real bei y≈1453px (Viewport 390×844) — eine reine Höhenkorrektur der Karte (ursprünglich angenommener Fix) verschiebt die Oberkante NICHT und kann die Steuerelemente daher nicht in den sichtbaren Bereich holen. Ursache der 1453px: ~526px fixer Chrome (Breadcrumb + TripHeader + Tab-Leiste + Aktivitäts-Select) + ~176px EtappenStrip + **~715px Etappen-Header-Zeile**, die auf schmalen Viewports durch eine Flex-Squeeze (`.stage-header-fields` mit `min-width:168px`, quetscht die Textspalte auf ~120px) extrem umbricht — ein zusätzlicher, bislang unbekannter Layoutfehler, der jeden mobilen Trip betrifft, nicht nur Randfälle. Diese Spec beschreibt die vom PO freigegebene Lösung: die Vollbild-Karte wird auf Mobilgeräten direkt unter die Tab-Leiste vorgezogen (Map-First-Reorder), Etappen-Details erscheinen darunter scrollbar — dadurch ist die Karte samt Steuerelementen sofort sichtbar, unabhängig von der Chrome-Höhe darüber.

## Source

- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
- **Identifier:** `.mobile-editor` / `.mobile-map-wrap` (Zeilen 385, 631 im aktuellen Stand)

> **Schicht-Bestätigung:** Frontend / User-UI (`frontend/src/...`, SvelteKit). Kein Go- oder Python-Backend-Code betroffen. Verifiziert per Grep auf `.mobile-map-wrap`/`.mobile-editor` — beide Selektoren existieren ausschließlich in `EditStagesPanelNew.svelte` und `ProfileSheetEmbedded.svelte`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte` | component | `.profile-sheet-host` ist `position:absolute; inset:0` relativ zu `.mobile-editor` — Snap-Höhen-Berechnung hängt indirekt von der korrigierten Höhe ab |
| `frontend/src/lib/components/edit/MapControl.svelte` | component | Enthält `add-waypoint`-Button, `position:absolute` relativ zu `.mobile-map-wrap` |
| `frontend/src/routes/trips/[id]/+page.svelte` | route | Rendert Breadcrumb-Bar vor dem Tab-Content, Teil des variablen Chrome-Offsets |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | component | Trip-Kopf, Teil des variablen Chrome-Offsets |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | component | Tab-Leiste + Aktivitäts-Select im `stages`-Tab, Teil des variablen Chrome-Offsets |
| `frontend/src/app.css` | stylesheet | `.mobile-scroll-pad` definiert TopAppBar-Padding (56px) und BottomNav-Padding (64px) als konstante Anker |
| `docs/specs/modules/wegpunkt_editor_handoff.md` | spec | Ursprüngliches #542-Handoff, definiert die fehlerhafte `100dvh-56px`-Vorgabe — muss parallel korrigiert werden |
| `frontend/e2e/issue-1158-mobile-sheet-collapse.spec.ts` | test | Snap-Höhen-Assertions hängen von `.mobile-editor`-Höhe ab, müssen nach Fix gegen echten Viewport (390×844) neu verifiziert werden |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY | Kernfix: Map-First-Reorder — `.mobile-map-wrap` wird auf Mobil (`@media max-width:899px`) per DOM-Reihenfolge/CSS `order` direkt unter die Tab-Leiste gerendert (vor EtappenStrip/Etappen-Header/Cascade-Strip), Höhe dynamisch als `calc(100dvh - {Tab-Unterkante}px)` bis zur BottomNav; Etappen-Header/EtappenStrip/Cascade-Strip folgen darunter scrollbar |
| `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte` | REVIEW/MODIFY | Snap-Höhen-Berechnung gegen neue (kleinere, korrekte) Container-Höhe neu verifizieren; nur minimal anpassen falls nötig |
| `docs/specs/modules/wegpunkt_editor_handoff.md` | MODIFY | AC-3 und Höhen-Formel auf Map-First-Reorder + dynamische Messung ab Tab-Unterkante präzisieren |
| `frontend/e2e/mobile-editor-controls-viewport.spec.ts` | CREATE | Regressionstest (Verhaltens-Name statt Issue-Nummer, Pflicht laut `test_naming_gate.py`): Bounding-Box von `stage-switcher-pill` und `add-waypoint` gegen Viewport-Grenzen prüfen VOR jedem `.click()` (Playwright scrollt sonst automatisch und verschleiert den Bug) |
| `frontend/e2e/issue-1158-mobile-sheet-collapse.spec.ts` | REVIEW | Snap-Höhen-Assertions (`h > vh*0.7` etc.) nach Fix gegen echten Viewport (390×844) neu verifizieren |

### Estimated Changes
- Files: 5 (2 MODIFY sicher, 1 REVIEW mit ggf. minimal MODIFY, 1 CREATE, 1 REVIEW)
- LoC: +110/-15 (Map-First-Reorder ist etwas invasiver als reine Höhenmessung, inkl. neuer e2e-Test ~60 LoC)

## Implementation Details

**Root Cause (final, empirisch per RED-Test verifiziert am 2026-07-11):** `stage-switcher-pill` und `add-waypoint` sind `position:absolute; top:12px` relativ zur Oberkante von `.mobile-map-wrap`. Diese Oberkante entsteht rein aus der DOM-Reihenfolge — sie liegt NACH Breadcrumb, TripHeader, Tab-Leiste, Aktivitäts-Select, EtappenStrip UND Etappen-Header im Dokumentfluss, gemessen bei y≈1453px (Viewport 390×844). Eine Höhenänderung von `.mobile-map-wrap` verschiebt seine Oberkante nicht — der ursprünglich angenommene Fix (Kandidat b, dynamische Höhenmessung bei gleichbleibender Position) kann die Steuerelemente daher grundsätzlich NICHT in den sichtbaren Bereich holen. Zusätzlich wurde ein bislang unbekannter Layoutfehler gefunden: Die Etappen-Header-Zeile (`flex items-start justify-between`) quetscht auf schmalen Viewports die Textspalte (`.stage-header-fields`, `min-width:168px`) auf ~120px, wodurch Titel + Wetterscheiden-Hinweistext auf ~715px Höhe umbrechen — trägt allein mehr als die Hälfte zum Gesamt-Offset bei.

**Fix-Ansatz (Map-First-Reorder, PO-entschieden 2026-07-11):** Auf Mobil (`@media max-width:899px`) wird `.mobile-map-wrap` per DOM-Reihenfolge/CSS `order` DIREKT unter die Tab-Leiste gerendert (vor EtappenStrip, Etappen-Header, optionalem Cascade-Strip) — die Karte ist damit sofort sichtbar, ihre Oberkante hängt nur noch vom fixen Chrome (Breadcrumb + TripHeader + Tab-Leiste + Aktivitäts-Select, ~526px) ab, nicht mehr vom variablen Etappen-Content. Höhe wird dynamisch als `calc(100dvh - {gemessene Tab-Unterkante}px)` gesetzt, damit die Karte bis zur BottomNav reicht. Etappen-Header, EtappenStrip und Cascade-Strip folgen darunter im normalen (scrollbaren) Fluss — Datum/Zeit-Bearbeitung bleibt vollständig erreichbar, nur eine Bildschirmlänge weiter unten. Tab-Leiste bleibt an ihrer Position, erfüllt weiterhin das AC aus #1158 ("Tab-Leiste bleibt klickbar").

**Verworfene Alternativen:**
- Reine dynamische Höhenmessung ohne Reorder (ursprünglicher Plan): funktioniert nicht — siehe Root Cause oben, Höhe ≠ Position.
- Textquetschung beheben + EtappenStrip mobil ausblenden (ohne Reorder): reicht laut Messung nur knapp (Editor-Top sinkt auf ~526-570px, Steuerelemente lägen direkt am BottomNav-Rand), fragiler bei künftigen Textlängen — nicht gewählt.
- `.mobile-editor` als `position:fixed`-Vollbild-Overlay: verdeckt dauerhaft Breadcrumb/TripHeader/Tabs, verletzt bestehendes AC aus #1158 ("Tab-Leiste bleibt klickbar").
- Steuerelemente `position:fixed` relativ zum Viewport statt zum Container: semantisch falsch (löst Kontrollelemente vom Karten-Kontext), Kollisionsgefahr mit TopAppBar-z-index.

Für Details zur Chrome-Struktur und den RED-Test-Messwerten siehe `docs/context/fix-963-mobile-editor-controls.md`.

## Expected Behavior

- **Input:** Nutzer öffnet den Etappen-Tab eines Trips auf einem Mobilgerät (Viewport <900px), unabhängig von Etappenanzahl, Etappennamen-Länge oder ob ein Cascade-Strip (Datumsverschiebungs-Hinweis) sichtbar ist.
- **Output:** Die Vollbild-Karte erscheint direkt unter der Tab-Leiste (Map-First-Reorder) und füllt die verbleibende Höhe bis zur BottomNav. `stage-switcher-pill` und `add-waypoint` sind dadurch immer innerhalb des sichtbaren Bildschirmbereichs positioniert und ohne Scrollen klickbar — unabhängig von der Länge des Etappennamens/Wetterscheiden-Textes oder Cascade-Strip-Sichtbarkeit, da diese Elemente jetzt UNTER der Karte liegen und die Karten-Position nicht mehr beeinflussen. Etappen-Header, EtappenStrip und Cascade-Strip bleiben durch Herunterscrollen erreichbar.
- **Side effects:** Bei Bildschirmdrehung/`resize` wird die Höhe der Karte neu gemessen (Tab-Unterkante als Bezugspunkt) und passt sich unmittelbar an. `ProfileSheetEmbedded` (Wegpunkt-Sheet), dessen Snap-Positionen relativ zu `.mobile-editor` berechnet werden, skaliert mit der korrigierten (nun kleineren, aber stabilen) Höhe mit; sein bisheriges Snap-Verhalten (verifiziert in #1158) muss nach dem Reorder erneut bestätigt werden. Auf Desktop (≥900px) hat die Änderung keinen Effekt, da dort das Editor-Grid statt `.mobile-editor` aktiv ist und keine Reorder-Logik greift.

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1: GIVEN ein Trip mit kurzem Etappennamen und deaktiviertem Cascade-Strip im mobilen Viewport (390×844) WHEN der Etappen-Tab geöffnet wird THEN liegt die Bounding-Box von `stage-switcher-pill` vollständig innerhalb des sichtbaren Viewports (y zwischen TopAppBar-Höhe 56px und `viewportHeight - 64px` BottomNav)
- [ ] Test 2: GIVEN dieselbe Ausgangslage WHEN der Etappen-Tab geöffnet wird THEN liegt die Bounding-Box des `add-waypoint`-Buttons ebenso vollständig innerhalb des sichtbaren Viewports und ist klickbar (kein Auto-Scroll vor der Prüfung)
- [ ] Test 3: GIVEN ein Trip mit langem Etappennamen/Wetterscheiden-Text (erhöhte Chrome-Höhe) WHEN der Etappen-Tab geöffnet wird THEN bleiben beide Steuerelemente weiterhin innerhalb des sichtbaren Viewports
- [ ] Test 4: GIVEN ein Trip mit sichtbarem Cascade-Strip (Datumsverschiebung Tag 1 ausgelöst) WHEN der Etappen-Tab geöffnet wird THEN bleiben beide Steuerelemente weiterhin innerhalb des sichtbaren Viewports
- [ ] Test 5: GIVEN das Wegpunkt-Sheet (`ProfileSheetEmbedded`) im echten Mobil-Viewport (390×844) nach dem Fix WHEN das Sheet geöffnet/gezogen wird THEN entspricht das Snap-Verhalten weiterhin den bestehenden Assertions aus `issue-1158-mobile-sheet-collapse.spec.ts`

## Acceptance Criteria

- **AC-1:** Given ein Trip mit typischer (kurzer) Etappenbezeichnung ohne aktiven Cascade-Strip im mobilen Viewport / When der Nutzer den Etappen-Tab öffnet / Then ist die Etappenwechsel-Pille vollständig innerhalb des sichtbaren Bildschirmbereichs sichtbar und klickbar.
  - Test: Playwright `boundingBox()` von `stage-switcher-pill` vor jedem Klick gegen Viewport-Grenzen prüfen, dann Klick ausführen und Funktionswechsel (nächste Etappe) verifizieren.

- **AC-2:** Given dieselbe Ausgangslage / When der Nutzer den Etappen-Tab öffnet / Then ist der Button zum Hinzufügen eines Wegpunkts vollständig innerhalb des sichtbaren Bildschirmbereichs sichtbar und klickbar.
  - Test: Playwright `boundingBox()` von `add-waypoint` vor jedem Klick gegen Viewport-Grenzen prüfen, dann Klick ausführen und Wegpunkt-Erstellung verifizieren.

- **AC-3:** Given ein Trip mit langem Etappennamen oder ausführlichem Wetterscheiden-Hinweistext (mehr Chrome-Höhe als der typische Fall) / When der Nutzer den Etappen-Tab öffnet / Then bleiben beide Steuerelemente weiterhin vollständig innerhalb des sichtbaren Bildschirmbereichs.
  - Test: Fixture-Trip mit künstlich langem Etappennamen laden, Bounding-Box-Prüfung analog AC-1/AC-2 erneut durchführen.

- **AC-4:** Given ein Trip, bei dem der Cascade-Strip (Datumsverschiebungs-Hinweis für Tag 1) sichtbar ist / When der Nutzer den Etappen-Tab öffnet / Then bleiben beide Steuerelemente weiterhin vollständig innerhalb des sichtbaren Bildschirmbereichs.
  - Test: Trip-Fixture mit ausgelöster Datumsverschiebung an Etappe 1 verwenden, Cascade-Strip-Sichtbarkeit erzwingen, Bounding-Box-Prüfung erneut durchführen.

- **AC-5:** Given das Wegpunkt-Sheet (`ProfileSheetEmbedded`) im echten mobilen Viewport (390×844) nach dem Fix / When der Nutzer das Sheet öffnet und zwischen Snap-Positionen zieht / Then verhält sich das Sheet unverändert zum bisherigen, in #1158 verifizierten Snap-Verhalten (keine Regression).
  - Test: `issue-1158-mobile-sheet-collapse.spec.ts` gegen den korrigierten Code erneut ausführen und alle bestehenden Snap-Höhen-Assertions grün bekommen.

- **AC-6:** Given die Desktop-Ansicht (Viewport ≥900px) / When der Nutzer den Etappen-Tab öffnet / Then bleibt das Editor-Grid-Layout unverändert, da keine mobile-editor-spezifische Höhenlogik dort aktiv ist.
  - Test: Bestehende Desktop-Tests bzw. manuelle Sichtprüfung bei ≥900px zeigen keine visuelle oder strukturelle Veränderung gegenüber dem Stand vor diesem Fix.

## Known Limitations

- Die dynamische Höhenmessung reagiert auf Mount und `resize`/`orientationchange` — nicht auf beliebige andere DOM-Mutationen, die die fixe Chrome-Höhe (Breadcrumb/TripHeader/Tabs) verändern könnten. Sollte dort künftig ein neuer Block eingefügt werden, muss die Messung erneut geprüft werden.
- Der Cascade-Strip-Testfall (AC-4) wird zuverlässig über `page.locator.press('Tab')` (echter Blur/Change statt `dispatchEvent`) ausgelöst — läuft 3/3 grün, keine offene Testlücke mehr.
- Map-First-Reorder ändert die visuelle Reihenfolge auf Mobil sichtbar (Karte zuerst statt Etappen-Header zuerst) — das ist eine bewusste, PO-freigegebene UX-Änderung, keine reine Bugfix-Kosmetik.
- **Mindesthöhen-Schutz (Fix-Loop 3, final):** Die Höhe von `.mobile-editor` wird per JS bedingt berechnet (nicht mehr als blindes CSS `max()`): `available = window.innerHeight - Oberkante - 64px(BottomNav) - Safe-Area`; ist `available > 0`, wird exakt dieser Wert genutzt (endet per Definition an der BottomNav-Oberkante, kein Überlapp möglich); ist `available ≤ 0` (Querformat auf schmalen Handys, ~390px Viewporthöhe, oder sehr kurzer Portrait-Viewport wie 320×568), greift der Fallback `MOBILE_EDITOR_MIN_HEIGHT_PX = 200`. Ein früherer Ansatz (Fix-Loop 2, blindes `max(400px, calc(...))`) überschoss die BottomNav-Zone bereits im STANDARD-Fall (390×844) bei langen Trip-Namen (F004, CRITICAL) — behoben durch die bedingte JS-Berechnung. Bei den Seitenverhältnis-Extremen (F001/F002) übersteigt der fixe Chrome-Block oberhalb weiterhin die Viewport-Höhe — Karte/Steuerelemente sind dort nur nach Scrollen erreichbar (nicht "ohne jedes Scrollen sichtbar" wie im Standardfall), aber real dimensioniert, sichtbar und klickbar (kein Nullgröße-/Überlapp-Defekt).
- **SaveIndicator z-index (Fix-Loop 3, Nebenbefund):** Die BottomNav-bewusste Höhenkorrektur verschiebt das eingeklappte Wegpunkte-Sheet exakt in die Zone direkt über der BottomNav — denselben Bereich, in dem `SaveIndicator.svelte` (Speicher-Status) mobil positioniert ist. Dessen `z-index` wurde von 40 auf 62 angehoben (über Sheet z-index:61, unter Dialog-Modalen z-index:100), damit der Speicher-Status nie vom Sheet verdeckt wird.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Lokaler Bugfix innerhalb einer bestehenden Komponente, keine neue Architektur-Entscheidung oder Cross-Cutting-Concern. Die verworfenen Alternativen (Fixed-Overlay, viewport-fixed Controls) sind in Implementation Details dokumentiert, wurden aber aus funktionalen Gründen (Regression gegen #1158) verworfen, nicht aus Architektur-Prinzipien.

## Changelog

- 2026-07-11: Initial spec created
- 2026-07-11: Fix-Ansatz nach RED-Test-Erkenntnis korrigiert — dynamische Höhenmessung allein kann Bug nicht beheben (Position ≠ Höhe), zusätzlicher Layoutfehler in Etappen-Header-Zeile entdeckt (~715px Textquetschung). PO hat Map-First-Reorder als Fix-Ansatz freigegeben. Acceptance Criteria unverändert (mechanismus-agnostisch formuliert), nur Implementation Details/Scope/Expected Behavior/Known Limitations aktualisiert. Testdatei-Name auf `mobile-editor-controls-viewport.spec.ts` korrigiert (Verhaltens-Name statt Issue-Nummer, `test_naming_gate.py`-Pflicht).
- 2026-07-11 (Fix-Loop 2): Adversary-Findings F001 (Querformat 844×390 kollabiert `.mobile-editor` auf 0px) und F002 (kurzer Portrait 320×568 überlappt Pille/MapControl mit Sheet-Griffleiste) durch Mindesthöhen-Clamp (`max(400px, ...)`) behoben; Known Limitations um den Clamp-Hinweis ergänzt, veraltete AC-4-Testlücken-Notiz entfernt (F003, Test läuft zuverlässig seit `press('Tab')`-Fix).
- 2026-07-11 (Fix-Loop 3): Adversary-Fund F004 (CRITICAL) — der 400px-Floor aus Fix-Loop 2 überschoss im STANDARD-Fall (390×844, mehrstufiger Trip, Offset≈526px) die reservierte BottomNav-Zone, wodurch echte Klicks auf die untere Navigationsleiste fehlschlugen (Sheet z-index:61 > BottomNav z-index:50). Erster Fix-Versuch (`max(200px, calc(...))`) reichte NICHT: bei langen Trip-Namen (Offset≈601px) überschoss auch der reduzierte Floor die BottomNav-Zone erneut — Root-Cause war der blinde `max()`-Combinator selbst (schießt immer über, sobald `calc(...)` positiv aber kleiner als der Floor ist). Finaler Fix: Höhe wird in JS bedingt berechnet (`available > 0 ? available : FLOOR`) statt blind geclampt — siehe Known Limitations. Nebenbefund dabei entdeckt+behoben: `SaveIndicator.svelte` (Speicher-Status) wurde vom nun korrekt positionierten Sheet verdeckt (z-index 40→62). F005 (Kommentar-Rechenfehler 168px→156px) und F006 (Container-Höhen-Angabe in `wegpunkt_editor_handoff.md` auf reale Messwerte korrigiert) nebenbei behoben. Regressionstest `mobile-editor-controls-viewport.spec.ts` um F004-Testfall (echter BottomNav-Klick, Standard-Viewport, scrollY=0) erweitert; `#1158`-AC-1-Testfall musste an die jetzt korrekt kleinere Kartenhöhe angepasst werden (Klick-Position 5%→25%, da 5% neu auf Leaflets Zoom-Control statt Kartenhintergrund traf).
