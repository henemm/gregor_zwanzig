---
entity_id: rework_2880_paritaet_reiterflaeche_anlegefelder
type: feature
created: 2026-11-09
updated: 2026-11-09
status: approved
version: "1.0"
workflow: rework-2880-paritaet
tags: [epic-2345, trip-compare-teilung, frontend-only, shared, paritaet, design-audit-2026-11-09]
---

# Parität Trip/Vergleich: Reiterfläche im Hub und Feld-Bausteine beim Anlegen (Issue #2880)

## Approval

- [x] Approved (PO Henning, 2026-11-09, Freigabe per AskUserQuestion)

## Purpose

Trip und Ortsvergleich sollen gleich aussehen, weil sie denselben Code teilen (ADR-0097, Pendant-Sperre #1170). Das Audit vom 9.11.2026 hat zwei Abweichungen gemessen:

- **P1 Reiterfläche im Hub:** Beim Vergleich ist der Inhalt der Reiter doppelt eingerückt. Ursache (gemessen): `CompareTabs.svelte` legt um alle Reiter einen Behälter `.compare-tabs-content` mit eigenem Rand (Computer 28/40/80 px, Handy 16/16/60 px) und um jeden Reiter außer der Übersicht noch `.tab-panel` (24 px oben und unten). Die geteilten Reiter-Bausteine (Wetter-Metriken, Wertebereiche, Alarme, Zustellung) bringen ihren Rand selbst mit (28/40/60 px, Handy 20/16/48 px). Ergebnis: Computer +40 px links und 80 statt 28 px oben, Handy +16 px links und 60 statt 20 px oben. Der Trip hat keinen solchen Behälter; dort bringen Übersicht (32/40/60) und Etappen (20/40/60) je einen eigenen, untereinander verschiedenen Rand mit.
- **P3 Feld-Bausteine beim Anlegen:** Der Trip schreibt seine Feldbeschriftungen von Hand (Sans, 12 px, fett, Versalien, roter Stern; Hinweis „optional · max 50“ rechts neben der Beschriftung). Der Vergleich nutzt den Design-System-Baustein `molecules/Field` (Mono-Eyebrow 10 px, Hinweis über `side` rechtsbündig in der Beschriftungszeile, kein Stern). Am Handy schreiben beide Seiten ihre Beschriftungen von Hand in jeweils anderer Optik. Die Reiter des Anlegens (Name · Etappen/Orte · …) sind auf beiden Seiten von Hand gebaut, mit verschiedenen Elementen (`div role=tab` gegen `button`) und Markierungen (Trip „OPTIONAL“-Pille, Vergleich keine).

**Entscheidung (Tech Lead):**
1. **Eine Reiterfläche:** Neuer geteilter Baustein `shared/hub-reiterflaeche/HubReiterflaeche.svelte` mit dem einheitlichen Rand 28/40/60 px (Handy unter 900 px: 20/16/48 px) und `max-width: 1480px`. Übersicht und Etappen (Trip) sowie Übersicht und Orte (Vergleich) stehen darin. Die Reiter, die ihren Rand schon selbst tragen (Wetter-Metriken samt Zustellung, Wertebereiche, Alarme), bleiben ohne äußeren Behälter. `.compare-tabs-content`-Rand und `.tab-panel` entfallen; der eigene Rand von `EditStagesPanelNew` und `.trip-uebersicht` entfällt zugunsten der Reiterfläche. Alle Werte liegen im 4-px-Raster.
2. **Ein Feld-Baustein:** Beim Anlegen nutzen beide Seiten für jedes Eingabefeld denselben Baustein: am Computer `molecules/Field`, am Handy `mobile/MField`. Beide bekommen eine Eigenschaft `pflicht` (zeigt nach der Beschriftung ein Sternchen in `--g-bad` mit `aria-hidden`, und das Eingabefeld bekommt `aria-required`) und zeigen Hinweise wie „optional · max 50“ einheitlich rechtsbündig in der Beschriftungszeile (`side`). Die Design-System-Optik (Mono-Eyebrow, Versalien, `--g-ink-3`) gilt für beide Seiten. Pflichtfelder (Name) tragen auf beiden Seiten das Sternchen.
3. **Eine Reiterleiste beim Anlegen:** Neuer geteilter Baustein `shared/anlege-rahmen/AnlegeReiter.svelte` für die Schritt-Reiter beider Seiten (Computer und Handy), mit Zuständen `aktiv`, `erledigt`, `gesperrt`, `optional`. Er ersetzt die vier handgebauten Leisten (Trip/Vergleich × Computer/Handy). Jeder Reiter ist ein `button` (`role="tab"`, gesperrt: `aria-disabled="true"`). Die Zustandsmarker sind auf beiden Seiten gleich; welche Zeichen sie zeigen (heute ✓ und ⊘), legt #2881 (R3) fest: dieser Baustein ist die eine Stelle, an der #2881 sie ersetzt. Die „Optional“-Pille erscheint auf beiden Seiten, wenn ein Schritt optional ist.

**Nicht hier:** Der Reiter Wetter-Metriken hat beim Vergleich eine ganz andere Oberfläche (`WeatherMetricsTab.svelte`, Zweig `context==='vergleich'`); das baut #2794 neu. Die Reiter Wertebereiche und Alarme entfallen mit #2794; sie profitieren aber automatisch vom Wegfall der doppelten Einrückung.

## Source

- **Neu:**
  - `frontend/src/lib/components/shared/hub-reiterflaeche/HubReiterflaeche.svelte`
  - `frontend/src/lib/components/shared/anlege-rahmen/AnlegeReiter.svelte`
  - `frontend/e2e/hub-anlegen-paritaet-flaechen.spec.ts` (Playwright; Positivliste und Ratschen in CI nachziehen)
- **Geändert:**
  - `frontend/src/lib/components/compare/CompareTabs.svelte`: `.compare-tabs-content`-Rand, `.tab-panel` entfernen; Übersicht und Orte in `HubReiterflaeche`.
  - `frontend/src/lib/components/trip-detail/TripTabs.svelte`: `.trip-uebersicht` entfernen; Übersicht und Etappen in `HubReiterflaeche`.
  - `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`: eigenen Außenrand entfernen.
  - `frontend/src/lib/components/molecules/Field.svelte`, `frontend/src/lib/components/mobile/MField.svelte`: Eigenschaft `pflicht`; `MField` zusätzlich `side`.
  - `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`, `frontend/src/lib/components/compare/steps/Step2Orte.svelte`: Felder über `Field`/`MField`, Schritt-Reiter über `AnlegeReiter`.
  - Bestehende Unit-/E2E-Tests, die an den alten Selektoren hängen (`tn-mobile-tabbar`, `cm-mobile-tabbar` usw.), werden angepasst, nicht gelöscht; vorhandene `data-testid` bleiben erhalten (der neue Baustein reicht sie durch).

> **Schicht:** nur Frontend.
> **Trip/Ortsvergleich-Teilung:** Kern dieser Spec; beide neuen Bausteine liegen unter `shared/`, die Pendant-Sperre greift nicht.
> **Mandantentrennung / Kanäle:** nicht betroffen.

## Estimated Scope

- **LoC:** ca. +250 / -300 Code, ca. +300 Test
- **Files:** 2 neue Bausteine, 7 geänderte Komponenten, 1 neue E2E-Datei, angepasste Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/anlege-rahmen/AnlegeRahmen.svelte` | geteilter Rahmen (#2837 S2) | bleibt; `AnlegeReiter` sitzt in seinem Inhalt |
| `molecules/Field.svelte`, `mobile/MField.svelte` | Design-System-Bausteine | Feldbeschriftung |
| `frontend/e2e/anlege-rahmen-paritaet.spec.ts` | bestehender Paritätstest | bleibt grün |
| #2881 | Folge-Issue | ersetzt ✓/⊘ im neuen `AnlegeReiter` |

## Implementation Details

1. `HubReiterflaeche.svelte`: `<div class="hub-reiterflaeche" data-testid={testid}>{@render children()}</div>`; CSS `padding: 28px 40px 60px; max-width: 1480px;` und unter 900 px `padding: 20px 16px 48px`.
2. `CompareTabs.svelte`: Behälter `.compare-tabs-content` behält nur `position: relative` (ohne Rand, ohne `max-width`); `.tab-panel`-Hüllen fallen weg (die `data-testid` der Panels bleiben am Panel-Element).
3. `TripTabs.svelte` / `EditStagesPanelNew.svelte`: entsprechend; `EditStagesPanelNew` behält seinen inneren Aufbau.
4. `Field`/`MField`: `pflicht?: boolean`. Rendert `<span class="field-pflicht" aria-hidden="true">*</span>` nach der Beschriftung; das Eingabefeld setzt `aria-required` selbst (der Aufrufer), damit Screenreader es ohne Sternchen erfahren.
5. `AnlegeReiter.svelte`: Eigenschaften `schritte: {id, label, zustand: 'offen'|'erledigt'|'gesperrt', optional?: boolean}[]`, `aktiv`, `onWahl(id)`, `variante: 'desktop'|'mobil'`, `testidPrefix`. Optik: Unterstrich-Reiter (2 px `--g-accent` am aktiven Reiter), Computer 13 px, Handy Mindesthöhe 44 px mit waagerechtem Scrollen wie bisher.
6. Pflicht-Mutationen: (a) `.tab-panel { padding: 1.5rem 0 }` zurück, (b) `HubReiterflaeche`-Rand im Trip-Zweig auf 32 px oben, (c) Trip-Editor nutzt für ein Feld wieder eine handgeschriebene Beschriftung, (d) Vergleich verliert die Optional-Pille. Jede muss einen AC rot machen.

## Expected Behavior

- **Input:** Hub-Reiter und Anlege-Schritte von Trip und Vergleich, Computer 1440 × 900 und Handy 390 × 844.
- **Output:** gleiche Lage und gleicher Rand des Reiterinhalts; gleiche Feldbeschriftungen, Hinweise, Pflicht-Sternchen und Schritt-Reiter.
- **Side effects:** Der Vergleich rückt im Hub um 40 px (Handy 16 px) nach links und um bis zu 52 px nach oben. Die Trip-Übersicht rückt 4 px nach oben, der Etappen-Reiter 8 px nach unten. Die Feldbeschriftungen beim Trip-Anlegen werden zur Mono-Eyebrow des Design-Systems.

## Acceptance Criteria

- **AC-1:** Given ein Trip und ein Ortsvergleich, beide gespeichert / When bei 1440 × 900 Pixel nacheinander die Reiter Übersicht, Etappen bzw. Orte, Wetter-Metriken, Wertebereiche und Alarme geöffnet werden / Then hat das erste sichtbare Inhaltselement jedes Reiters bei Trip und Vergleich denselben linken Rand (x, Toleranz 1 Pixel) und denselben Abstand zur Unterkante der Reiterleiste (Toleranz 1 Pixel).
  - Test: Playwright `hub-anlegen-paritaet-flaechen.spec.ts` PF-1, `boundingBox()` des ersten sichtbaren Kindes von `[data-testid="trip-detail-panel-{reiter}"]` bzw. `[data-testid="compare-detail-panel-{reiter}"]` relativ zur Leiste; Reiterpaare Etappen ↔ Orte.

- **AC-2:** Given dieselben Seiten bei 390 × 844 Pixel / When dieselben Reiter geöffnet werden / Then gilt dieselbe Gleichheit (x und Abstand zur Leiste, Toleranz 1 Pixel), und keine Seite läuft waagerecht über.
  - Test: Playwright PF-2.

- **AC-3:** Given die Reiter Übersicht und Etappen bzw. Orte / When sie bei 1440 × 900 vermessen werden / Then beträgt der Innenrand der Reiterfläche oben 28, seitlich 40 und unten 60 Pixel, bei 390 Pixel Breite 20, 16 und 48 Pixel.
  - Test: Playwright PF-3, `getComputedStyle` von `[data-testid$="-reiterflaeche"]`.

- **AC-4:** Given das Anlegen eines Trips und das Anlegen eines Vergleichs, erster Schritt / When bei 1440 × 900 die Feldbeschriftungen „Name“ und „Region“ verglichen werden / Then haben sie auf beiden Seiten dieselbe Schriftart, -größe, -stärke, Versalien-Schreibweise, Laufweite und Farbe; das Pflichtfeld Name zeigt auf beiden Seiten ein Sternchen, das Region-Feld auf beiden Seiten den Hinweis „optional · max …“ an derselben Stelle (rechts in der Beschriftungszeile, gleicher Abstand zur Feldkante, Toleranz 1 Pixel); auf Deutsch und Englisch.
  - Test: Playwright PF-4, `getComputedStyle` der Beschriftungen, `boundingBox()` der Hinweise relativ zum Eingabefeld; Name-Eingabe trägt `aria-required="true"` auf beiden Seiten.

- **AC-5:** Given dieselben Anlege-Seiten bei 390 × 844 / When die Feldbeschriftungen verglichen werden / Then gilt dieselbe Gleichheit wie in AC-4 mit dem Handy-Baustein.
  - Test: Playwright PF-5.

- **AC-6:** Given das Anlegen von Trip und Vergleich, ohne eingegebenen Namen / When die Schritt-Reiter bei 1440 × 900 und 390 × 844 betrachtet werden / Then haben die Reiter beider Seiten dieselbe Höhe, Schrift und Farbe je Zustand (aktiv, gesperrt), gesperrte Reiter tragen `aria-disabled="true"` und denselben Zustandsmarker, optionale Schritte tragen auf beiden Seiten die Optional-Pille, und am Handy ist jeder Reiter mindestens 44 Pixel hoch.
  - Test: Playwright PF-6, `getComputedStyle`/`boundingBox()` je Zustand Trip gegen Vergleich.

- **AC-7:** Given das Anlegen von Trip und Vergleich / When ein Nutzer einen Namen eingibt, auf „Weiter“ klickt, einen erledigten Schritt-Reiter erneut anklickt und das Anlegen abschließt / Then verhält sich der Ablauf wie bisher (Schrittwechsel, Sperren, Abschluss legt das Abo an), und die bestehenden Abläufe `hub-anlegen-ablauf.spec.ts` und `anlege-rahmen-paritaet.spec.ts` laufen unverändert grün.
  - Test: bestehende Playwright-Dateien, unverändert in ihren Zusicherungen (nur Selektoren dürfen nachgezogen werden, wenn sich `data-testid` ändern müsste; Ziel: keine Änderung).

## Test Plan

- Playwright PF-1 bis PF-6 neu, am isolierten Stack, Trip gegen Vergleich, Computer und Handy, DE und EN (AC-4/5).
- Bestehende Paritäts- und Ablauftests als Regressionsschutz (AC-7).
- RED-Nachweis: PF-1/PF-2 (Vergleich 40 bzw. 16 px eingerückt), PF-4 (Trip Sans/Vergleich Mono) und PF-6 (Optional-Pille nur Trip) schlagen auf `origin/main` fehl.

## Definition of Done

- AC-1 bis AC-7 grün, Adversary VERIFIED mit den vier Pflicht-Mutationen gefangen.
- PR mit allen 6 CI-Checks grün gemergt; Staging-Prüfung und Prod-Deploy über die Server-Sitzung.

## Known Limitations

- Die maximale Zeichenzahl der Region unterscheidet sich (Trip 50, Vergleich 60) und kommt aus dem jeweiligen Datenmodell; die Spec ändert sie nicht, sie gleicht nur die Darstellung des Hinweises an.
- Wetter-Metriken beim Vergleich bleibt inhaltlich anders, bis #2794 den Reiter „Wetter“ baut.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; wendet ADR-0097 und ADR-0110 an. Dass die Anlege-Schritte eine eigene Reiterleiste (Unterstrich, auch am Handy) statt der Hub-Pillen haben, hält ADR-0111 aus #2881 fest.

## Changelog

- 2026-11-09: Initial spec (Issue #2880).
- 2026-11-09: Vom PO freigegeben.
