# Context: fix-963-mobile-editor-controls

## Request Summary
Im mobilen Etappen-Editor (`/trips/:id?tab=stages`, Viewport <900px) landen die Karten-Steuerelemente `stage-switcher-pill` und `add-waypoint` außerhalb des sichtbaren Bereichs und sind nicht klickbar. Der im Issue #963 dokumentierte Root Cause ("mehrere Tab-Panels gleichzeitig gerendert") ist durch Code-Lektüre **widerlegt** — echte Ursache ist ein Höhen-Berechnungsfehler.

## Tatsächlicher Render-Pfad (wichtig — weicht vom Issue-Text ab)

`trips/[id]/+page.svelte` → `TripTabs.svelte` (Tab `stages`) → `EditStagesSection.svelte` → `EditStagesPanelNew.svelte`

Die im Issue erwähnte `TripEditView.svelte` wird **nirgends produktiv verwendet** (nur in einem Test referenziert) — dort werden Tab-Panels zwar korrekt exklusiv per `{#if}/{:else if}` gerendert (nur aktives Panel im DOM), das ist aber für den Bug irrelevant, weil dieser Code-Pfad gar nicht läuft.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte:384-425,630-662` | `.mobile-editor`/`.mobile-map-wrap` mit fehlerhafter `height: calc(100dvh - 56px)`; enthält `stage-switcher-pill` (396-403, 636-652) und `MapControl`/`add-waypoint` (404-406) |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte:302-381` | Chrome-Elemente VOR `.mobile-editor` im selben Fluss: Root-Wrapper (302, gap 16px), EtappenStrip (304-312, ~118px), Content-Wrapper-Padding (324, 20+60px), Etappen-Header (326-353, ~90-140px), optionaler Cascade-Strip (355-381, ~40px) |
| `frontend/src/routes/trips/[id]/+page.svelte:225-329` | Breadcrumb-Bar (227-283, Style 321-329, ~45-50px) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte:195-208` | Trip-Kopf, `padding:26px 40px 18px` + `margin-bottom:1.25rem` + Titel/Stats (~100-150px) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:136-231` | Segmented Tab-Leiste (136-137, Style 208-231, ~40-50px) + Aktivitäts-Select-Zeile nur im `stages`-Tab (145-163, ~45-55px) |
| `frontend/src/routes/+layout.svelte:80` | Äußerer Scroll-Container `<main class="mobile-scroll-pad ...">` |
| `frontend/src/app.css:190-205` | `.mobile-scroll-pad`: mobil `padding-top:56px`, `padding-bottom:calc(64px + safe-area)`; ab 900px beides 0 |
| `frontend/src/lib/components/edit/MapControl.svelte:46-58` | `add-waypoint`-Button, `position:absolute` relativ zu `.mobile-map-wrap` |
| `frontend/src/lib/components/edit/issue_542_mobile_editor.test.ts` | Bestehender Test zu #542 — reiner Source-String-Match (kein DOM/Geometrie), deckt #963 NICHT ab |
| `frontend/e2e/issue-1158-mobile-sheet-collapse.spec.ts:185` | Einziger Playwright-Test, der `stage-switcher-pill` anklickt — Playwrights automatisches Vor-Scrollen beim `.click()` verdeckt den Bug |
| `docs/specs/modules/wegpunkt_editor_handoff.md` | Ursprüngliches #542-Handoff, definiert `100dvh-56px`-Vorgabe für `.mobile-map-wrap` OHNE die Chrome-Elemente davor zu berücksichtigen — Ursprung des Fehlers |

## Root Cause

`.mobile-map-wrap` (EditStagesPanelNew.svelte:385) setzt `height: calc(100dvh - 56px)` in der Annahme, direkt unter der TopAppBar (56px) zu sitzen. Tatsächlich läuft er im normalen Dokumentfluss NACH Breadcrumb + TripHeader + Tab-Leiste + Aktivitäts-Select + EtappenStrip + Etappen-Header (+ optional Cascade-Strip) — zusammen ca. 400-700px zusätzliche Höhe, je nach Trip-Daten (Textlänge Etappenname/Wetterscheiden-Hinweis, Anzahl Etappen-Chips, Cascade-Strip sichtbar oder nicht).

Die absolute Dokumenthöhe überschreitet dadurch den Viewport um genau diesen Betrag. `stage-switcher-pill` und `add-waypoint` sind `position:absolute; top:12px` **relativ zu `.mobile-map-wrap`** — sie erben dessen fehlerhaften Offset und landen entsprechend weit unterhalb des sichtbaren Bereichs (Meldung: y≈1539px bei 844px Viewport-Höhe = kumulierter offsetTop der Chrome-Elemente + 12px).

## Existing Patterns

- Mobile/Desktop-Umschaltung durchgängig über `@media (max-width: 899px)` (Pattern aus #542), kein JS-basiertes Viewport-Tracking.
- Vollbild-Karten-Layouts (`100dvh`-Berechnungen) kommen im Projekt nur an dieser Stelle vor — kein etabliertes "sticky/fixed volle Resthöhe"-Pattern zum Wiederverwenden.

## Dependencies
- Upstream: TopAppBar-Höhe (56px, hartcodiert in mehreren Dateien), `.mobile-scroll-pad`-Padding aus `app.css`.
- Downstream: `MapControl.svelte` (add-waypoint), Etappenwechsel-Logik hinter `stage-switcher-pill`, `issue_542_mobile_editor.test.ts` (String-Assertions, müssen bei Refactor konsistent bleiben).

## Existing Specs
- `docs/specs/modules/wegpunkt_editor_handoff.md` — muss bei Fix aktualisiert werden (dvh-Annahme war falsch).
- `docs/specs/modules/issue_1158_mobile_sheet_close.md` — verwandtes Sheet-Verhalten, nicht direkt betroffen.

## Risks & Considerations

- **Fix-Ansatz-Kandidaten:** (a) `.mobile-map-wrap` als `position:fixed`/volle Bildschirmüberlagerung statt im Dokumentfluss (größerer Eingriff, ändert Scroll-Verhalten des gesamten Tabs); (b) dynamische Höhenberechnung (`calc(100dvh - 56px - <Summe-Chrome-Höhe>)`) — fragil bei variabler Chrome-Höhe (Textumbruch, Cascade-Strip an/aus); (c) Steuerelemente NICHT relativ zu `.mobile-map-wrap`, sondern `position:fixed` relativ zum Viewport positionieren — am robustesten gegen variable Chrome-Höhe, aber ändert Stacking-Kontext/Scroll-Verhalten.
- **Regressionstest fehlt strukturell:** Playwright-`.click()` verschleiert das Problem durch Auto-Scroll. Ein echter Regressionstest muss die Bounding-Box der Elemente gegen die Viewport-Höhe prüfen (`boundingBox().y < viewportHeight`), nicht nur `.click()` erfolgreich ausführen.
- **Variable Content-Höhe:** Etappen mit langen Namen/Wetterscheiden-Texten oder aktivem Cascade-Strip erzeugen unterschiedliche Chrome-Höhen — der Fix darf sich nicht auf einen fixen Pixel-Wert verlassen, sonst regressiert er bei anderen Trip-Daten.
- Betrifft nur Mobil-Viewport (`@media max-width:899px`); Desktop-Grid ist ein komplett separater Codepfad und nicht betroffen.

## Analysis

### Type
Bug (Nebenbefund aus Adversary-Review von #951, aber unabhängig verifiziert)

### Root Cause (final, durch 2 unabhängige Agenten verifiziert)
`.mobile-editor` (`EditStagesPanelNew.svelte:631`, `position:relative`) ist der gemeinsame Anker-Container sowohl für `.mobile-map-wrap` als auch für `ProfileSheetEmbedded` (dessen `.profile-sheet-host` ist `position:absolute; inset:0` relativ zu `.mobile-editor`, siehe `ProfileSheetEmbedded.svelte:120-124`). Die Höhe von `.mobile-editor` wird faktisch durch `.mobile-map-wrap`s Inline-Style `height: calc(100dvh - 56px)` bestimmt. Diese Formel war nur unter der (falschen) Annahme korrekt, dass nichts außer der 56px-TopAppBar oberhalb liegt. TopAppBar (`fixed`, 56px) und BottomNav (`fixed`, 64px) sind konstant — das eigentliche Problem ist der variable Chrome-Block dazwischen (Breadcrumb, TripHeader, Tab-Leiste, EtappenStrip, Etappen-Header, optionaler Cascade-Strip: ~400-700px, abhängig von Trip-Daten).

Severity: **HIGH** — Kernfunktion (Etappenwechsel, Wegpunkt hinzufügen) auf Mobilgeräten vollständig unbenutzbar, 100% reproduzierbar bei jedem Öffnen des Etappen-Tabs auf Viewport <900px.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY | Reaktive Höhenmessung (`bind:this` + `$effect`/ResizeObserver) statt fixem `calc(100dvh - 56px)`; Höhe an `.mobile-editor` (nicht nur `.mobile-map-wrap`) binden, damit auch `ProfileSheetEmbedded` korrekt mitskaliert |
| `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte` | REVIEW | Prüfen ob Snap-Höhen-Berechnung (`inset:0` relativ zu `.mobile-editor`) mit der neuen dynamischen Höhe weiterhin korrekt ist |
| `docs/specs/modules/wegpunkt_editor_handoff.md` | MODIFY | AC-3 (Zeile ~42) und Formel Zeile ~61 auf dynamische Messung präzisieren (Ursprung des Bugs: Spec/Code-Drift) |
| `frontend/e2e/issue-963-mobile-editor-controls.spec.ts` | CREATE | Regressionstest: Bounding-Box der Steuerelemente gegen Viewport-Grenzen prüfen, VOR jedem `.click()` — Playwrights Auto-Scroll darf den Bug nicht verschleiern |
| `frontend/e2e/issue-1158-mobile-sheet-collapse.spec.ts` | REVIEW | Snap-Höhen-Assertions (`h > vh*0.7` etc.) nach Fix gegen echten Viewport (390×844) neu verifizieren — Container ist nach Fix kleiner als bisher angenommen |

### Scope Assessment
- Files: 2 Kern-Dateien (MODIFY) + 1 neue Testdatei + 2 Review-only
- Estimated LoC: ~+90/-5 (inkl. neuer e2e-Test ~60 LoC)
- Risk Level: MEDIUM (Kernfix ist klein und lokal, aber Interaktion mit `ProfileSheetEmbedded`-Snap-Höhen erfordert sorgfältige Verifikation)

### Technical Approach
**Empfehlung: dynamische Höhenmessung (Kandidat b).** `.mobile-editor` (bzw. äquivalent `.mobile-map-wrap`) misst per `getBoundingClientRect().top` seinen tatsächlichen Offset zur Laufzeit (bei Mount + bei Änderung von `activeStageId`/Cascade-Sichtbarkeit/`resize`) und setzt `height: calc(100dvh - {topOffset}px)` reaktiv statt hartcodiert `56px`.

Verworfene Alternativen:
- **(a) `.mobile-editor` als `position:fixed`-Vollbild:** Nicht empfohlen — Chrome-Elemente liegen im selben Scroll-Container (`main.overflow-auto`); ein Fixed-Overlay würde Breadcrumb/TripHeader/Tabs/Etappen-Header dauerhaft verdecken und dauerhaft unerreichbar machen. Verletzt AC „Tab-Leiste bleibt klickbar" aus #1158.
- **(c) Steuerelemente `position:fixed` relativ zum Viewport:** Nur Fallback — semantisch falsch (Kontrollelemente lösen sich vom Karten-Kontext, blieben sichtbar auch wenn Nutzer zur Etappenliste hochscrollt), Kollisionsgefahr mit TopAppBar z-index.

### Dependencies
- `issue-1158-mobile-sheet-collapse.spec.ts` — Sheet-Snap-Höhen hängen indirekt von `.mobile-editor`-Höhe ab; nach Fix erneut gegen echten Viewport verifizieren.
- `issue_542_mobile_editor.test.ts` — reine Source-String-Tests, kein Risiko.
- Desktop-Grid (`@media max-width:899px`) komplett unberührt.

### Regressionstest-Design
Playwrights `.click()` scrollt automatisch — das maskiert den Bug. Test muss: (1) `boundingBox()` der Pill/`add-waypoint` holen, (2) gegen Viewport-Grenzen prüfen (`box.y >= 56 && box.y + box.height <= viewportHeight - 64`, also unterhalb TopAppBar und oberhalb BottomNav) **bevor** geklickt wird, (3) danach erst klicken. Kein `scrollIntoViewIfNeeded` vor der Prüfung.

### Open Questions
- [x] Reihenfolge geklärt: Spec/Doku-Update (`wegpunkt_editor_handoff.md`) parallel zur Implementierung, um erneuten Spec/Code-Drift zu vermeiden.
- [ ] Muss im Adversary-Review explizit gegen `issue-1158`-Snap-Höhen getestet werden (echter Viewport 390×844).

## Nachtrag (2026-07-11, nach RED-Test-Erkenntnis durch Developer Agent)

Der Developer Agent hat den RED-Regressionstest geschrieben und dabei per echter DOM-Messung (Viewport 390×844) festgestellt, dass die ursprünglich empfohlene Lösung ("dynamische Höhenmessung") **strukturell nicht funktionieren kann**: `stage-switcher-pill`/`add-waypoint` sind `position:absolute; top:12px` relativ zur OBERKANTE von `.mobile-map-wrap` (nicht zu dessen Höhe). Diese Oberkante liegt real bei y≈1453px. Eine Höhenänderung verschiebt die Oberkante nicht — der Bug bleibt bestehen, unabhängig von der Höhenformel.

Aufschlüsselung des 1453px-Offsets (empirisch gemessen):
- Fixer Chrome (Breadcrumb + TripHeader + Tab-Leiste + Aktivitäts-Select): 526px
- EtappenStrip: 176px
- Etappen-Header-Zeile (NEU entdeckt, bislang unbekannt): 715px — Ursache: `.stage-header-fields` mit `min-width:168px` quetscht auf 390px-Breite die Textspalte auf ~120px, wodurch Titel + Wetterscheiden-Hinweistext extrem umbricht. Betrifft JEDEN mobilen Trip, nicht nur Randfälle.

PO-Entscheidung (2026-07-11): Map-First-Reorder — Karte wird auf Mobil direkt unter die Tab-Leiste vorgezogen (DOM-Reihenfolge/CSS `order`), Etappen-Details folgen darunter scrollbar. Spec (`docs/specs/modules/issue_963_mobile_editor_controls.md`) wurde entsprechend aktualisiert; Acceptance Criteria blieben unverändert (mechanismus-agnostisch), nur Implementation Details/Scope/Expected Behavior/Known Limitations.

Testdatei-Name musste von `issue-963-mobile-editor-controls.spec.ts` auf `mobile-editor-controls-viewport.spec.ts` korrigiert werden — `test_naming_gate.py` blockt neue issue-nummerierte Testdateien (CLAUDE.md Test-Politik, Bestandssanierung #1196).

RED-Artefakt: `docs/artifacts/fix-963-mobile-editor-controls/test-red-output.txt` (4 failed, 1 passed=setup), erstellt vom Developer Agent.
