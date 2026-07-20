---
entity_id: feat_1301_f3_deadcode_offscreen
type: feature
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
tags: [epic-1301, compare, deadcode, responsive, issue-1206, issue-989]
---

# Epic #1301 Scheibe F3 — Rest-Abräumung #1206 (tote Compare-Komponenten) + #989 (Offscreen-Ghost-Elemente)

## Approval

- [ ] Approved

## Purpose

Nach F2b (`db0ca26b`, Alt-Editor `CompareEditor.svelte` gelöscht) sind zwei Alt-Befunde noch nicht
vollständig geschlossen:

1. **#1206** — zwei Komponenten und ein Test unter `frontend/src/lib/components/compare/` sind
   Totcode geworden (kein Produktions-Import mehr, bzw. nie einer), werden aber weiterhin von
   `issue_462.test.ts` (Import-Migrations-Check) referenziert bzw. haben einen eigenen Test, der
   dokumentiert obsoletes Verhalten prüft.
2. **#989** — `/compare/new` hat noch ein Rest-Offscreen-Muster: Auf ≤899px wird der Desktop-Block
   per `position:fixed; top/left:-9999px; 1×1px` versteckt statt per `display:none`. Das DOM bleibt
   erhalten, Elemente bleiben tab-fokussierbar (Ghost-Elemente) — genau die #989-Beanstandung, nur
   mit verschobenen statt entfernten Koordinaten. Der Kommentar im Code benennt es offen als
   Test-Krücke: das Offscreen-Element hält `compare-editor-name` künstlich befüllbar, weil es auf
   Mobile kein eigenes Namensfeld gibt.

Diese Scheibe schließt beide Befunde ab: Totcode-Löschung ohne Ersatz (#1206) und Angleichung des
Compare-Responsive-Switches an das bereits etablierte Trip-Muster #661 (#989) — inklusive eines
echten Mobile-Namensfeldes, damit Mobile-Nutzer den Vergleichsnamen tatsächlich eingeben können
(heute nur per Playwright-`fill()` aufs unsichtbare Desktop-Element möglich, kein realer Nutzerpfad).

## Source

- **Analyse:** `docs/context/f3-1206-989.md` (Befunde, betroffene Dateien mit Zeilennummern, Risiken).
- **Vorbild-Spec (Format):** `docs/specs/modules/epic_191_state_migration.md`,
  `docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md`.
- **Referenzmuster #661 (Trip-Responsive-Switch):** `frontend/src/lib/components/trip-new/TripNewEditor.svelte`
  (Desktop-Name-Input `:512` `trip-new-name-input-desktop`, Mobile-Name-Input `:797`
  `trip-new-name-input-mobile`, beide auf dieselbe State-Variable `name`; CSS-Switch `:1039-1058`
  `.tn-desktop`/`.tn-mobile` mit `display:none !important`).
- **Deprecation-Beleg Wochenrhythmus (#1232 Scheibe 2a):** `internal/model/compare_preset.go:29-33`
  — `Weekday *int` ist DEPRECATED, „kein neuer Schreibpfad mehr — nur noch Altdaten-Träger".

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` (#622/#661) | Produktivcode, Vorbild | Referenzmuster für Mobile-Namensfeld (`:512-515` Desktop-Input, `:797-799` Mobile-Input, beide auf `name`) und CSS-Responsive-Switch (`:1039-1058`, `.tn-desktop`/`.tn-mobile` mit `display:none !important`) — wird nur gelesen, nicht verändert |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Produktivcode, Ziel der Änderung | Enthält heute den Offscreen-Switch (`:549-561`) und das alleinige Desktop-Namensfeld (`compare-editor-name`, `:334`) — beides wird in dieser Scheibe angepasst |
| `frontend/src/lib/components/compare/issue_462.test.ts` | Test, Basis | Atomic-Import-Migrations-Check; Zeile 38 referenziert die zu löschende `SavePresetDialog.svelte` und muss angepasst werden, restliche Einträge bleiben Referenz für das Kommentar-Vermerk-Format (Zeilen 25-31) |
| `internal/model/compare_preset.go` (`Weekday`-Feld, `:29-33`) | Produktivcode, Beleg | Dokumentiert die Deprecation des Wochenrhythmus (#1232 Scheibe 2a) — Beweisgrundlage dafür, dass `issue_511_weekly_scheduler.test.ts` obsoletes Verhalten prüft |
| `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte` | Produktivcode, Abgrenzung | Namensgleiche, aber funktional unabhängige Komponente (Metrik-Preset-Dialog) — nur als Negativ-Abgrenzung relevant, bleibt unangetastet |
| Betroffene Mobile-E2E-Specs (`issue-682-compare-editor-mobile.spec.ts` u. a., s. Scope Teil 2) | Test, downstream | Nutzen heute `compare-editor-name` unter Mobile-Viewport und müssen nach der Testid-Aufspaltung auf `compare-editor-name-mobile` umgestellt werden |

## Implementation Details

```
Teil 1 (#1206) — reine Löschungen, keine Logikänderung:
  rm frontend/src/lib/components/compare/SavePresetDialog.svelte
  rm frontend/src/lib/components/compare/RangeSlider.svelte
  rm frontend/src/lib/components/compare/__tests__/issue_511_weekly_scheduler.test.ts
  issue_462.test.ts: MIGRATED_FILES-Eintrag für SavePresetDialog.svelte (Zeile 38)
    entfernen + Kommentar-Vermerk im Format der Zeilen 25-31 ergänzen.

Teil 2 (#989) — CompareNewEditor.svelte:
  1. Neues <input data-testid="compare-editor-name-mobile"> im .cm-mobile-Block,
     bind:value={wiz.name} (dieselbe State-Variable wie das bestehende
     Desktop-Input <input data-testid="compare-editor-name"> in .cm-desktop).
  2. <style>-Block (aktuell :549-561) umbauen:
       VORHER (Offscreen):
         @media (max-width: 899px) {
           .cm-desktop { position:fixed; top:-9999px; left:-9999px;
                         width:1px; height:1px; overflow:hidden; }
           .cm-mobile { display:block !important; }
         }
       NACHHER (Trip-Muster #661):
         .cm-mobile { display:none !important; }
         @media (max-width: 899px) {
           .cm-desktop { display:none !important; }
           .cm-mobile { display:block !important; }
           .cm-mobile-flex { display:flex !important; }
         }
  3. E2E-Specs: Fill-Aufrufe auf [data-testid="compare-editor-name"] innerhalb
     von Mobile-Viewport-Kontexten (setViewportSize Breite ≤899px) auf
     [data-testid="compare-editor-name-mobile"] umstellen; Desktop-Kontexte
     unverändert lassen (s. Tabelle in Scope Teil 2).
```

## Expected Behavior

- **Input (Teil 1):** Aktueller Repo-Stand mit den drei toten Dateien und dem veralteten
  `issue_462.test.ts`-Eintrag.
- **Output (Teil 1):** Die drei Dateien existieren nicht mehr; `issue_462.test.ts` prüft nur noch
  lebende Komponenten und bleibt grün; kein Produktionsverhalten ändert sich (die gelöschten Dateien
  hatten keinen aktiven Aufrufer).
- **Input (Teil 2):** `/compare/new` unter Mobile-Viewport (≤899px) mit dem heutigen
  Offscreen-Desktop-Block und ohne eigenes Mobile-Namensfeld.
- **Output (Teil 2):** Unter Mobile-Viewport ist der Desktop-Block per `display:none` unsichtbar
  und nicht mehr fokussierbar; ein eigenes, sichtbares Mobile-Namensfeld
  (`compare-editor-name-mobile`) erlaubt reale Nameneingabe, gebunden auf denselben State wie das
  Desktop-Feld. Unter Desktop-Viewport (≥900px) ist das Verhalten unverändert (Mobile-Block weiterhin
  per `display:none` versteckt).
- **Side effects:** Betroffene Mobile-E2E-Specs müssen ihr Ziel-Testid wechseln (sonst schlägt
  `fill()` auf dem nun tatsächlich versteckten Desktop-Element fehl); keine Backend-/API-Änderung,
  keine Persistenzänderung.

## Scope

### Teil 1 — #1206 Totcode-Löschung (ersatzlos, kein Umschreiben)

| Datei | Aktion | Begründung |
|---|---|---|
| `frontend/src/lib/components/compare/SavePresetDialog.svelte` (223 LoC) | löschen | Kein Produktions-Import mehr (Alt-Editor-Relikt, F2b hat den letzten Aufrufer `CompareEditor.svelte` bereits entfernt) |
| `frontend/src/lib/components/compare/RangeSlider.svelte` (142 LoC) | löschen | Völlig referenzlos — kein Import, kein Test |
| `frontend/src/lib/components/compare/__tests__/issue_511_weekly_scheduler.test.ts` (99 LoC) | löschen | Prüft dokumentiert obsoletes Verhalten (Wochenrhythmus wurde mit #1232 Scheibe 2a bewusst entfernt); nach Test-Politik (`CLAUDE.md` „Zwei Schichten") löschen statt umschreiben, da kein aktuelles Verhalten mehr existiert, das dieser Test sinnvoll beweisen könnte |
| `frontend/src/lib/components/compare/issue_462.test.ts` Zeile 38 | Eintrag entfernen | `{ path: join(COMPARE_DIR, 'SavePresetDialog.svelte'), components: ['Btn'] }` referenziert die gelöschte Datei; Kommentar-Vermerk analog den bestehenden #1256-Vermerken (Zeilen 25-31) hinzufügen, der Datei, Grund und Issue-Nummer nennt |

**AC-3 von #1206 (Weekday-Picker #511) — dokumentiert zurückgebaute Funktion, kein Verlust-Befund:**
Issue #1232 Scheibe 2a hat den Wochenrhythmus bewusst entfernt (KL-1: „Wochenrhythmus entfällt,
Presets versenden täglich"). Am lebenden Frontend-Pfad (`shared/`, `compare-new/`,
`routes/compare/**`) existiert kein `weekday`/`weekly`-Code mehr. Der issue_511-Test prüft damit
ausschließlich Alt-Verhalten, das absichtlich nicht mehr existiert — seine Löschung ist keine
Funktionsregression, sondern Testbestand-Bereinigung passend zum bereits vollzogenen Produkt-Rückbau.

### Teil 2 — #989 Responsive-Switch-Angleichung ans Trip-Muster

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Mobiles Namensfeld ergänzen: zweiter `<input>` im `.cm-mobile`-Block, `data-testid="compare-editor-name-mobile"`, gebunden auf dieselbe State-Variable wie das bestehende Desktop-Feld `compare-editor-name` (Vorbild: `TripNewEditor.svelte:512-515` Desktop / `:797-799` Mobile, beide auf `name`) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` (`:549-561`) | CSS-Responsive-Switch von Offscreen (`position:fixed; top/left:-9999px; 1×1px; overflow:hidden`) auf Trip-Muster #661 umstellen: `.cm-desktop { display: none !important; }` auf `@media (max-width: 899px)`, `.cm-mobile` bleibt `display:none !important` außerhalb des Media-Query und wird darin auf `display:block/flex !important` gesetzt (Vorbild `TripNewEditor.svelte:1039-1058`) |

**Testid-Konvention:** Das bestehende `compare-editor-name` bleibt unverändert das Desktop-Testid
(im `.cm-desktop`-Block). Das neue Mobile-Feld erhält das eigene Testid
`compare-editor-name-mobile` (im `.cm-mobile`-Block) — analog zu Trips
`trip-new-name-input-desktop`/`-mobile`, kein geteiltes Testid über zwei DOM-Elemente hinweg.

**Betroffene Mobile-E2E-Specs (Umstellung auf `compare-editor-name-mobile` NUR dort, wo ein
Mobile-Viewport aktiv ist — Desktop-Nutzungen von `compare-editor-name` bleiben unverändert):**

| Datei | Mobile-Kontext | Aktion |
|---|---|---|
| `frontend/e2e/issue-682-compare-editor-mobile.spec.ts` | durchgängig Mobile (375px), 3 Fill-Stellen auf `compare-editor-name` (`:155`, `:209`, weitere) | auf `compare-editor-name-mobile` umstellen |
| `frontend/e2e/issue-951-sheet-bottomnav.spec.ts` | Mobile (390×844), `:98` | auf `compare-editor-name-mobile` umstellen |
| `frontend/e2e/compare-editor-fidelity-s8d.spec.ts` | gemischt Desktop/Mobile, 5 Fill-Stellen (`:224`, `:285`, `:395`, `:445`, `:483`) | nur die Fill-Stellen innerhalb der Mobile-`describe`/`beforeEach`-Blöcke (`setViewportSize` <900px) umstellen; Desktop-Blöcke (z. B. `:445`/`:483` „Desktop-Orte"/„Desktop-Layout") bleiben auf `compare-editor-name` |
| `frontend/e2e/versand-tab-vergleich.spec.ts` | AC-6 (`:234`) läuft explizit über `.cm-desktop`-Locator, kein Mobile-Viewport | **keine Änderung** — bleibt Desktop |
| `frontend/e2e/layout-tab-vergleich.spec.ts` | zu prüfen je Testfall (`:34`, `:120`) gegen aktiven Viewport | nur Mobile-Teile umstellen, Desktop-Teile unverändert |
| `frontend/e2e/compare-flow-navigation.spec.ts` | gemischt: `:220`/`:536` in Desktop-Kontexten, Mobile-`describe`-Block ab `:341` (390×844) | nur Fill-Aufrufe innerhalb des Mobile-`describe`-Blocks umstellen, `:visible`-Disambiguierung entfällt dort dann (nur noch ein sichtbares Element je Viewport) |

Verbindliche Prüfmethode für den Developer-Agenten: vor jeder Umstellung `setViewportSize`
oberhalb des jeweiligen Testfalls/`describe`-Blocks grep-bestätigen (Breite ≤899px = Mobile).
Bei `:visible`-Locators, die heute zwei koexistierende Elemente disambiguieren (z. B.
`compare-flow-navigation.spec.ts:220/536/727`), wird nach der Umstellung geprüft, ob `:visible`
noch nötig ist (Desktop-Feld ist nach dem Fix per `display:none` tatsächlich ausgeblendet, nicht
nur offscreen — `:visible` bleibt in Desktop-Kontexten weiterhin korrekt, da dort Mobile-Feld
`display:none` ist).

## Invarianten — Was darf sich nicht ändern

- `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte` (Metrik-Preset-Dialog,
  verwendet von `WeatherMetricsTab.svelte`) bleibt **unberührt** — reine Namenskollision mit der
  gelöschten `compare/SavePresetDialog.svelte`, kein Zwilling, keine funktionale Beziehung
  (#1206-Korrektur: nicht mit dem zu löschenden Dialog verwechseln).
- `frontend/src/lib/components/trip-new/TripNewEditor.svelte` bleibt unverändert (reines Vorbild,
  keine Anpassung an Compare).
- Kein `data-testid` eines lebenden Desktop-Pfads verschwindet oder ändert sich
  (`compare-editor-name`, `compare-editor-tab-*`, `compare-editor-continue-*`,
  `compare-editor-activate`, `compare-step2-*`, `cm-mobile-*`, `top-app-bar-*` bleiben wie sie sind).
- Verhalten auf Desktop ≥900px ist nach der Umstellung identisch zu vorher (Mobile-Block war und
  bleibt dort ausgeblendet; nur der Ausblend-Mechanismus für den *Desktop*-Block auf ≤899px ändert
  sich von Offscreen auf `display:none`).
- `POST /api/compare/presets`-Vertrag, `compareNewLogic.ts`, alle übrigen Tabs/Organismen
  (`Step2Orte`, `WeatherMetricsTab`, `CorridorEditor`, `AlarmeTab`, `VersandTab`) bleiben unverändert
  — diese Scheibe fasst ausschließlich Totcode und den Responsive-Switch an.

## Acceptance Criteria

- **AC-1:** Given `frontend/src/lib/components/compare/SavePresetDialog.svelte` existiert im
Repo, When ein `grep` nach Produktions-Importen der Datei über `frontend/src` läuft, Then liefert
er null Treffer außerhalb der Datei selbst — nach der Löschung existiert die Datei gar nicht mehr
und der `issue_462.test.ts`-Eintrag dafür (Zeile 38) ist entfernt; der verbleibende Testlauf
(`node --experimental-strip-types --test src/lib/components/compare/issue_462.test.ts`) ist grün.

- **AC-2:** Given `frontend/src/lib/components/compare/RangeSlider.svelte`, When ein `grep` nach
Import-Referenzen (`RangeSlider`) über `frontend/src` (Komponenten + Tests) läuft, Then liefert er
vor der Löschung bereits null Treffer außerhalb der Datei selbst (Beweis der Referenzlosigkeit) und
die Datei ist nach dieser Scheibe gelöscht.

- **AC-3:** Given `frontend/src/lib/components/compare/__tests__/issue_511_weekly_scheduler.test.ts`
prüft Wochenrhythmus-Verhalten, When Issue #1232 Scheibe 2a den Wochenrhythmus bereits produktiv
entfernt hat (Beleg `internal/model/compare_preset.go:29-33`, `Weekday` DEPRECATED), Then ist die
Testdatei gelöscht statt umgeschrieben — kein lebender Code-Pfad verliert dadurch Testabdeckung,
da der geprüfte Rhythmus-Mechanismus selbst nicht mehr existiert.

- **AC-4:** Given der Weekday-Picker aus Issue #511, When man den heutigen Frontend-Code
(`shared/`, `compare-new/`, `routes/compare/**`) nach `weekday`/`weekly` durchsucht, Then finden
sich keine Treffer — die Funktion wurde mit #1232 Scheibe 2a bewusst zurückgebaut; diese Spec
dokumentiert das als „kein Verlust-Befund", nicht als offene Lücke.

- **AC-5:** Given ein Mobile-Viewport (≤899px) auf `/compare/new`, When die Seite lädt, Then ist
der Desktop-Block (`.cm-desktop`) per `display: none !important` unsichtbar (nicht mehr per
`position:fixed`/Offscreen-Koordinaten) und enthält keine tab-fokussierbaren Elemente — ein
Tab-Durchlauf per Tastatur ab dem Seitenanfang trifft auf keines der Desktop-Formularfelder.

- **AC-6:** Given ein Mobile-Viewport, When der Nutzer den Vergleichsnamen eingeben will, Then
existiert ein sichtbares, eigenständiges Mobile-Namensfeld (`data-testid="compare-editor-name-mobile"`)
im `.cm-mobile`-Block, gebunden auf dieselbe State-Variable wie das Desktop-Feld — eine Eingabe im
Mobile-Feld erscheint nach Rückwechsel auf Desktop-Breite im Desktop-Feld wieder (gemeinsamer
State), und umgekehrt.

- **AC-7:** Given ein Desktop-Viewport (≥900px), When die Seite lädt, Then ist der Mobile-Block
(`.cm-mobile`) per `display: none !important` unsichtbar (unverändertes Vorher-Verhalten) — die
Umstellung betrifft ausschließlich die Ausblend-Methode des Desktop-Blocks auf ≤899px, nicht die
bereits korrekte Ausblendung des Mobile-Blocks auf Desktop.

- **AC-8:** Given die Mobile-E2E-Specs, die bisher `compare-editor-name` unter einem
Mobile-Viewport befüllt haben (`issue-682-compare-editor-mobile.spec.ts`,
`issue-951-sheet-bottomnav.spec.ts`, Mobile-Teile von `compare-editor-fidelity-s8d.spec.ts`,
`layout-tab-vergleich.spec.ts` und `compare-flow-navigation.spec.ts`), When sie nach dieser
Scheibe gegen Staging laufen, Then füllen sie `compare-editor-name-mobile` und sind grün — kein
`fill()`-Fehlschlag durch nun tatsächlich verstecktes (`display:none`) Desktop-Element.

- **AC-9:** Given Desktop-Teile derselben oder anderer E2E-Specs (`versand-tab-vergleich.spec.ts`
AC-6, Desktop-`describe`-Blöcke in `compare-editor-fidelity-s8d.spec.ts` und
`compare-flow-navigation.spec.ts`), When sie nach dieser Scheibe gegen Staging laufen, Then bleiben
sie unverändert auf `compare-editor-name` und sind ohne Codeänderung weiterhin grün.

## Known Limitations

- Die generische Editor-Rahmen-Extraktion (Trip + Compare gemeinsame Shell) ist weiterhin nicht
  Teil dieser Scheibe — unverändert Radar-Kandidat laut F2a-Spec (ADR-0029).
- `frontend/src/lib/components/compare/steps/Step2Orte.svelte` bleibt unter `steps/`, kein Umzug
  in dieser Scheibe (unverändert wie F2a dokumentiert).
- Diese Scheibe fasst ausschließlich die in Teil 1 und Teil 2 genannten Dateien an; weitere
  Aufräumkandidaten aus `docs/context/f3-1206-989.md` über den dort dokumentierten Rahmen hinaus
  sind nicht Teil des Scopes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0030 (neu — ADR-0029 ist bereits durch die F2a-Spec für „Anlege-Shell je Domäne
  eigen" reserviert; diese Scheibe braucht eine eigene Nummer für eine andersartige Entscheidung).
- **Rationale:** Compare übernimmt beim Responsive-Switch vollständig das Trip-Muster #661
  (`display:none`-Umschaltung mit zwei parallelen State-gebundenen Eingabefeldern statt einem
  Offscreen-Element). Die bisherige Abweichung war eine bewusst kommentierte Test-Krücke
  („Desktop offscreen statt display:none, damit compare-editor-name auf Mobile für Playwright
  befüllbar bleibt") — sie hat kein UX- oder A11y-Ziel, sondern umging das Fehlen eines echten
  Mobile-Eingabepfads. Mit dem neuen Mobile-Feld entfällt der Grund für die Abweichung vollständig;
  die Trip/Compare-Teilungs-Invariante (`CLAUDE.md`) verlangt in diesem Fall keine neue Ausnahme,
  weil hier kein neuer Baustein entsteht, sondern ein bestehender Compare-Sonderweg auf das bereits
  etablierte, geteilte Muster zurückgeführt wird.

## Test Plan

1. **Kern-Unit/Struktur (netzfrei, node:test):** `issue_462.test.ts` läuft ohne den
   `SavePresetDialog.svelte`-Eintrag grün (Datei existiert nicht mehr im geprüften Set, verbleibende
   Einträge unverändert bestanden).
2. **Frontend-Build:** `cd frontend && npm run build` bzw. `npm run check` grün — keine toten
   Imports auf die gelöschten Dateien, keine TypeScript-Fehler durch das neue Mobile-Input.
3. **Grep-Beweis vor Löschung (Teil der Umsetzung, nicht nur Behauptung):** `grep -rn
   "SavePresetDialog\|RangeSlider" frontend/src --include=*.svelte --include=*.ts` vor und nach der
   Löschung dokumentieren — vorher nur der Eintrag in `issue_462.test.ts` bzw. gar keine Treffer
   (RangeSlider), nachher keine Treffer mehr.
4. **Playwright lokal/Staging:** läuft regulär in Phase 7 (`/e2e-verify`) gegen Staging, nicht Teil
   dieser Spec-Freigabe — die AC-5 bis AC-9 sind dort mit echten Klickpfaden (Tab-Fokus-Test,
   Mobile-Fill, Desktop-Fill) zu verifizieren, nicht per Code-Review allein.
5. **Mandantentrennung:** entfällt — diese Scheibe berührt keinen datenbewegenden Endpoint (reine
   Totcode-Löschung + CSS/Markup-Umstellung ohne Backend-Kontakt).

## Estimated Scope

- **LoC:** überwiegend Löschungen: `-223` (SavePresetDialog.svelte), `-142` (RangeSlider.svelte),
  `-99` (issue_511-Test), `-1/+3` (issue_462.test.ts Eintrag + Kommentar) = **~-460 LoC**; dazu
  `CompareNewEditor.svelte` **+~15/-10** (neues Mobile-Input + CSS-Switch-Umstellung); E2E-Umbauten
  **~+20/-20** (Testid-Austausch in ~5 Dateien, kein struktureller Umbau). 250-LoC-Limit unkritisch
  (Löschungen zählen negativ, Nettosumme deutlich negativ).
- **Files:** 3 gelöscht (`SavePresetDialog.svelte`, `RangeSlider.svelte`,
  `issue_511_weekly_scheduler.test.ts`), 2 geändert im Kern (`issue_462.test.ts`,
  `CompareNewEditor.svelte`), bis zu 5 E2E-Dateien mit punktuellem Testid-Austausch.
- **Effort:** niedrig-mittel — mechanische Löschung plus ein klar vorgezeichnetes Muster-Kopie
  (Trip-Mobile-Input) ohne neue Fachlogik.

## Changelog

- 2026-07-19: Initial spec created
