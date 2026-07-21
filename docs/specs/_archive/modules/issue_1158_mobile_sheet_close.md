---
entity_id: issue_1158_mobile_sheet_close
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [mobile, editor, bugfix, sheet]
---

# Issue #1158 — Wegpunkte-Schublade im Mobile-Trip-Editor einklappbar machen

## Approval

- [ ] Approved

## Purpose

Auf Mobile-Viewports (<900px) versperrt die Wegpunkte-Schublade
(„Bottom-Sheet", `ProfileSheetEmbedded`) im Trip-Editor die Karte und lässt
sich nicht schließen — der Editor ist praktisch unbenutzbar (Issue #1158,
priority:critical). Diese Spec macht die Schublade **einklappbar** (nicht
entfernbar): eine schmale Griffleiste bleibt sichtbar, Karte und restliche
Seite (Tabs, Speichern) sind jederzeit erreichbar, und die Schublade lässt
sich aus dem eingeklappten Zustand wieder aufklappen. Gilt sowohl im
bestehenden Trip-Editor als auch im Trip-Anlage-Wizard.

## Source

- **File:** `frontend/src/lib/components/mobile/Sheet.svelte`
- **File:** `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte`
- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
- **Identifier:** `Sheet` (Svelte-Komponente, `variant="embedded"`), `ProfileSheetEmbedded`, mobiler Zweig in `EditStagesPanelNew` (`.mobile-editor`, Zeilen 380–422/627–658)

> Schicht: Frontend / User-UI (`frontend/src/...`, SvelteKit, produktive
> Oberfläche auf gregor20.henemm.com). Kein Go-API- und kein Python-Core-Anteil.

## Estimated Scope

- **LoC:** ~180 (Summe aller Dateien, Details unten; Budget 250)
- **Files:** 5 (3 Produktivcode, 1 bestehende Test-Datei erweitert, 1 neue E2E-Spec)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Sheet.svelte` (`variant="modal"`) | shared component | Wird von CompareEditor, MCompareActionSheet, WeatherMetricsTab, StageSelectSheet, TripNewEditor genutzt — **darf sich in keiner Weise ändern** |
| `Sheet.svelte` (`variant="embedded"`) | shared component | Einziger Nutzer: `ProfileSheetEmbedded`; hier greift der Fix |
| `ProfileSheetEmbedded.svelte` | component | Host der Wegpunktliste + Profil-SVG in der Schublade |
| `EditStagesPanelNew.svelte` | component | Mobiler Editor-Zweig (Karte + Schublade + Etappen-Pill); von `TripEditView`, `TripNewEditor` und `EditStagesSection` eingebunden |
| `TripEditView.svelte` | consumer | Trip-bearbeiten-Flow, Default-Tab `etappen` — keine Code-Änderung erwartet, nur Verhaltens-Nachweis |
| `frontend/e2e/helpers.ts` (`login`) | test helper | Bestehender Login-Helfer für Playwright-E2E |

## Implementation Details

```
1. Sheet.svelte (variant="embedded"):
   - Neuer Snap-Wert 'collapsed' zusätzlich zu 'full' | 'half' | 'peek'.
     heights-Map bekommt collapsed: eine feste Pixel-Höhe (≤64px, orientiert
     an Griffleiste + optionaler Eyebrow-Zeile), NICHT eine Prozent-Höhe wie
     die drei bestehenden Stufen — sonst wäre "eingeklappt" auf großen
     Displays immer noch zu hoch.
   - variant="embedded": style:position wechselt von "fixed" auf "absolute"
     (Anker: der Host-Container .profile-sheet-host, der bereits
     position:relative + height:calc(100dvh - 56px) trägt). style:bottom
     wechselt vom Magic-Offset "64px" auf "0" — der Host definiert die Höhe
     korrekt, der Offset war der eigentliche Fehlerherd (Kommentar in
     ProfileSheetEmbedded versprach "Host skaliert %-Werte", was bei
     position:fixed nie stimmte).
   - variant="modal" bleibt bei position:fixed, unveränderten Werten für
     bottom/inset/z-index — Verzweigung ausschließlich über variant.
   - Griffleiste (die 36×4px-Handle-Leiste, Zeilen 88–93) bekommt bei
     variant="embedded" einen onclick-Handler, der (sofern vom Aufrufer via
     Prop bereitgestellt) zwischen 'collapsed' und der zuletzt aktiven Stufe
     umschaltet — Toggle, kein neuer Button.

2. ProfileSheetEmbedded.svelte:
   - Snap-Type erweitert auf 'collapsed' | 'peek' | 'half' | 'full'.
   - cycleSnap()-Reihenfolge wird collapsed → peek → half → full → collapsed
     (bestehende drei Stufen bleiben inhaltlich unverändert, Collapsed ist
     eine zusätzliche vierte Stufe, keine Ersetzung von peek).
   - Im collapsed-Zustand wird der Sheet-Body (Profil-SVG + Wegpunktliste)
     nicht gerendert (nur Griffleiste + ggf. Eyebrow/Titel sichtbar) —
     vermeidet Overflow-Artefakte bei einer 56px-Box.
   - Kommentar-Korrektur: "peek ≈ 92px" wird durch die tatsächlichen
     Prozentwerte ersetzt (Doku-Fix, kein Verhalten).

3. EditStagesPanelNew.svelte:
   - mobileSnap-Type-Union erweitert um 'collapsed' (Zeile 51).
   - Keine CSS-Änderung am mobile-editor-Layout nötig — der Host-Container
     ist bereits korrekt dimensioniert; der Fix ist die Anker-Korrektur in
     Sheet.svelte.

4. Kein Code in TripEditView.svelte oder TripNewEditor.svelte nötig — beide
   binden EditStagesPanelNew unverändert ein, der Fix wirkt transitiv.
```

## Expected Behavior

- **Input:** Nutzer tippt auf einem Mobilgerät (<900px) im Etappen-Tab des
  Trip-Editors bzw. im Etappen-Schritt des Trip-Anlage-Wizards auf die
  Griffleiste der Wegpunkte-Schublade.
- **Output:** Die Schublade klappt zwischen einer schmalen Griffleiste
  (≤64px) und einer der bisherigen Höhenstufen (peek/half/full) um; in jedem
  Zustand bleiben Karte, Tabs und Speichern-Leiste erreichbar.
- **Side effects:** Keine Persistenz-Änderung (reiner UI-Zustand, nicht
  gespeichert); modale Sheet-Nutzer (`variant="modal"`) sind unberührt.

## Acceptance Criteria

- **AC-1:** Given Nutzer öffnet auf einem Mobilgerät (<900px) den Trip-Editor
  im Etappen-Tab mit sichtbarer Wegpunkte-Schublade / When er auf die
  Griffleiste tippt, um sie einzuklappen / Then klappt die Schublade auf eine
  schmale Kopfzeile (≤64px sichtbare Höhe) zusammen und die Karte darunter ist
  über die gesamte restliche Bildschirmhöhe frei antippbar.
  - Test: Playwright @375×812, echter Login + Navigation zum Trip-Editor,
    echter Tap auf die Griffleiste; danach `getBoundingClientRect()` der
    Schublade < 64px UND ein Kartentipp erzeugt nachweisbar einen neuen
    Wegpunkt (kein Dateiinhalt-Check).

- **AC-2:** Given die Wegpunkte-Schublade ist eingeklappt / When der Nutzer
  erneut auf die Griffleiste tippt / Then klappt die Schublade wieder auf und
  die Wegpunktliste ist sichtbar und scrollbar.
  - Test: Playwright: nach Collapse ein zweiter echter Tap auf die
    Griffleiste; Assert Sheet-Höhe > 200px und mindestens eine
    WaypointCard im DOM sichtbar.

- **AC-3:** Given Nutzer hat die Wegpunkte-Schublade auf die größte Stufe
  (full) aufgeklappt / When er danach einen oberen Tab oder die untere
  Speichern-Leiste antippt / Then reagiert die App (Tab wechselt bzw. Save
  wird ausgelöst) — die Schublade blockiert diese Bedienelemente nicht
  dauerhaft.
  - Test: Playwright: Sheet auf full setzen, dann echten Klick auf einen
    Tab-Button und auf den Speichern-Button ausführen, jeweils
    Erfolg (Tab-Inhalt wechselt bzw. Save-Request/Erfolgsmeldung) prüfen.

- **AC-4:** Given Nutzer öffnet den Trip-Anlage-Wizard auf einem Mobilgerät
  und erreicht den Etappen-Schritt / When er dort die Wegpunkte-Schublade
  ein- und wieder auszuklappen versucht / Then verhält sie sich identisch
  zum Trip-Editor (Griffleiste, Karte frei bedienbar, wieder aufklappbar).
  - Test: Playwright, echter Klick-Pfad über „Neuer Trip" bis zum
    Etappen-Schritt, gleiche Collapse/Expand-Assertions wie AC-1/AC-2.

- **AC-5:** Given Nutzer öffnet den Trip-Editor auf einem Desktop-Viewport
  (>=900px) / When er den Etappen-Tab nutzt / Then erscheint unverändert das
  Desktop-Grid (Karte+Profil links, Wegpunkt-Sidebar rechts) ohne
  Bottom-Sheet, Griffleiste oder Collapse-Verhalten.
  - Test: Playwright @1280×800: `[data-testid="editor-grid"]` sichtbar,
    `.mobile-editor`-Container hat `display:none`, keine Sheet-Elemente
    nehmen Klicks entgegen.

- **AC-6:** Given Nutzer öffnet im mobilen Trip-Editor ein modales Sheet
  (z. B. die Etappen-Auswahl über die Etappen-Pill, `StageSelectSheet`) /
  When er es öffnet und wieder schließt / Then funktionieren Overlay,
  Schließen-Button und Body-Scroll-Sperre exakt wie vor dieser Änderung.
  - Test: Playwright: Etappen-Pill antippen, Overlay + Schließen-Button
    vorhanden, Tap auf Overlay schließt das Sheet, `document.body` hat
    `overflow:hidden` solange offen und nicht mehr danach.

- **AC-7:** Given Nutzer nutzt im mobilen Trip-Editor den bestehenden
  Höhe-wechseln-Button der Schublade / When er ihn mehrfach antippt / Then
  durchläuft die Schublade alle vier Stufen (collapsed → peek → half → full
  → collapsed) und jede der drei bisherigen Stufen (peek/half/full) bleibt
  in ihrer bisherigen ungefähren Höhe erreichbar.
  - Test: Playwright: Cycle-Button viermal antippen, nach jedem Tap die
    Sheet-Höhe gegen die erwarteten Bereiche (collapsed ≤64px, peek≈32%,
    half≈55%, full≈84% der Viewport-Höhe) plausibilisieren.

## Known Limitations

- Der neue `collapsed`-Snap existiert nur für `variant="embedded"` — modale
  Sheets bekommen keinen Collapse-Zustand (nicht Teil des Bugs, hätten
  eigenen Schließen-Button bereits über `onClose`).
- Die Griffleiste ist der einzige Collapse/Expand-Trigger; ein zusätzlicher
  expliziter „Schließen"-Button in der Schublade ist nicht Teil dieser Spec
  (würde die Sheet-Kopfzeile visuell verändern und ein Design-Fidelity-Review
  gegen `wegpunkt_editor_handoff.md` erfordern — bewusst außerhalb des
  Scopes, da PO-Vorgabe „schließbar machen" mit dem Collapse-Muster erfüllt
  ist, das `StageSelectSheet` bereits als Griff-Interaktion etabliert).
- Touch-Target-Größe der Griffleiste (Charter §7, ≥44px) wird durch die
  bestehende Griffleisten-Trefferfläche (Padding um die 36×4px-Handle)
  abgedeckt, nicht separat pixelgenau vermessen — kein Design-Fidelity-Delta,
  da die Griffleiste selbst nicht neu gestaltet wird.
- `issue_542_mobile_editor.test.ts` (Source-Inspection-Stil, vor der
  „keine Dateiinhalt-Checks"-Regel entstanden) wird nur strukturell auf den
  neuen `collapsed`-Wert erweitert; der eigentliche Verhaltensnachweis für
  #1158 läuft ausschließlich über die neue Playwright-E2E-Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner UI-Bugfix innerhalb des bestehenden Sheet-Musters
  (Anker-Korrektur `fixed`→`absolute` nur für die bereits isolierte
  `embedded`-Variante, plus eine zusätzliche Snap-Stufe). Keine neue
  Abhängigkeit, kein neues architektonisches Muster, keine Auswirkung auf
  Persistenz/Provider/Risk-Engine-Schichten.

## Affected Files (mit LoC-Schätzung)

| Datei | Änderung | LoC-Delta (geschätzt) |
|---|---|---|
| `frontend/src/lib/components/mobile/Sheet.svelte` | `collapsed`-Snap, Anker fixed→absolute nur für `variant="embedded"`, Griffleisten-Toggle | ~18 |
| `frontend/src/lib/components/edit/ProfileSheetEmbedded.svelte` | Snap-Type erweitert, Cycle-Reihenfolge, collapsed-Rendering, Kommentar-Fix | ~28 |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | `mobileSnap`-Type-Union erweitert | ~6 |
| `frontend/src/lib/components/edit/issue_542_mobile_editor.test.ts` | AC-5-Assertion um `collapsed` ergänzt | ~12 |
| `frontend/e2e/issue-1158-mobile-sheet-collapse.spec.ts` (neu) | Playwright-E2E: AC-1 bis AC-7, echter Klick-Pfad, Mobile + Desktop-Viewport | ~115 |
| **Summe** | | **~179 / 250** |

## Testplan

- **Primärer Nachweis (Bug-Reproduktion + Fix):** neue Playwright-E2E-Spec
  `frontend/e2e/issue-1158-mobile-sheet-collapse.spec.ts` gegen Staging
  (`https://staging.gregor20.henemm.com`), echter Login (`login()`-Helper),
  echter Klick-/Tap-Pfad (kein `page.goto()` auf Unterseiten, kein DB-Zugriff,
  keine Mocks). Viewport 375×812 für die Mobile-ACs (AC-1–AC-4, AC-6, AC-7),
  1280×800 für AC-5. Vor dem Fix müssen AC-1/AC-2 rot sein (Schublade lässt
  sich nicht einklappen bzw. Karte bleibt verdeckt) — Reproduktion aus
  Nutzersicht.
- **Struktureller Regressionsschutz:** `issue_542_mobile_editor.test.ts`
  (bestehend) bleibt grün; AC-5-Block dort um den `collapsed`-Wert ergänzt,
  damit die Snap-Type-Erweiterung nicht unbemerkt aus dem Code fällt.
- **Mail-/Renderer-Gate:** nicht betroffen (keine Mail-Inhalts-Datei
  geändert).
- **Manuell vor „Staging-validiert":** Trip-Editor UND Trip-Anlage-Wizard je
  einmal auf echtem Mobile-Viewport durchklicken (Collapse, Expand, Tab
  wechseln, Speichern), zusätzlich Desktop-Ansicht (>=900px) und ein
  modales Sheet (Etappen-Pill) gegenprüfen.

## Changelog

- 2026-07-09: Initial spec created (Issue #1158)
