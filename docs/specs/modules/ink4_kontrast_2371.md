---
entity_id: ink4_kontrast_2371
type: module
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
tags: [frontend, kontrast, design-system, anlege-editor, archiv, ratsche, adr-0008]
---

# Kontrast-Untergrenze: `--g-ink-4` in Anlege-Editoren und Archiv (#2371)

## Approval

- [ ] Approved

## Purpose

`--g-ink-4` (`#9a958a`, 2,71:1 auf Papier, 2,85:1 auf Weiß) darf laut ADR-0008 nur Placeholder und deaktivierte Eingabefelder färben. Heute trägt es in den Anlege-Editoren (`/trips/new`, `/compare/new`) und im Archiv Feld-Labels, Fortschritt, Hilfetexte, deaktivierte Aktionen und gesperrte Tabs. Die Spec hebt diese Texte auf `--g-ink-3` (5,0:1) und führt einen Wächter ein, der neue Verstöße rot meldet (Ratsche mit Ausnahmeliste für den Bestand außerhalb des Scopes).

Epic #2508 (Strang B). Leitprinzip: „Hoher Kontrast = Lesbarkeit" (PO-bestätigt 2026-05-25, `docs/reference/design_system.md`).

## Source

- **File:** `frontend/src/lib/components/` (Anlege-Pfad) und `frontend/src/routes/archiv/+page.svelte`
- **Identifier:** Inline-Styles `color: var(--g-ink-4)` in den unten gelisteten Svelte-Dateien

> **Schicht:** ausschließlich Frontend (SvelteKit, `frontend/src/...`). Keine Go-API-, keine Python-Änderung, keine Datenänderung.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** `TripNewEditor` und `CompareNewEditor` werden in identischer Form angepasst (Pendant-Sperre). Der geteilte Rahmen (`AnlegeRahmen`, `AnlegeFortschritt`) wird zuerst geändert, beide Editoren erben das Ergebnis. Es entsteht keine neue Komponente, daher keine einseitige Neuanlage.
> - **Mandantentrennung:** nicht betroffen (keine Nutzerdaten bewegt).
> - **Kanäle:** nicht betroffen (reine UI-Farbänderung; kein Briefing- oder Alarm-Inhalt).

## Scope

**Im Scope**

- Alle Textfarben `color: var(--g-ink-4)` (außerhalb Placeholder/Disabled-Inputs) in:
  - `components/shared/anlege-rahmen/AnlegeRahmen.svelte`, `AnlegeFortschritt.svelte`
  - `components/trip-new/TripNewEditor.svelte` (22 Fundstellen)
  - `components/compare-new/CompareNewEditor.svelte` (10 Fundstellen)
  - `routes/archiv/+page.svelte` (3 Fundstellen)
  - Organismen, die im Anlege-Pfad (`/trips/new`, `/compare/new`) sichtbar sind: `components/compare/steps/Step2Orte.svelte` (11), `components/shared/corridor-editor/CorridorEditor.svelte` (10) und `CorridorEditor.Mobile.svelte` (12), weitere per Grep im Anlege-Pfad nachgewiesene Dateien (Liste wird in der Implementierung gegen die gerenderten Seiten abgeglichen).
- Gesperrte Tabs ohne Zusatz-Opacity (bisher 0.34/0.35).
- Deaktivierte Aktion „Speichern" in `/trips/new`: Text ≥ 4,5:1 und `aria-disabled="true"`.
- Neuer Wächter-Test mit Ausnahmeliste (Ratsche).
- Neuer Playwright-Kontrastmesstest gegen Staging (390x844).

**Nicht im Scope**

- Dark-Mode-Wert von `--g-ink-3` (Issue #2400).
- Danger-Rot-Kontrast (Issue #1831).
- Token-Definitionen in `frontend/src/app.css` (`--g-ink-3`, `--g-ink-4`) bleiben unverändert.
- Die Design-Seite `routes/_design/+page.svelte` (zeigt Ratio 2,98 statt 2,85; Anschlussthema #1831/#2508).
- Bestand an `--g-ink-4`-Textfarben in Dateien außerhalb des Anlege-Pfads und des Archivs (Ausnahmeliste; Abbau im Epic #368/#2508).
- Placeholder (`::placeholder`) und `:disabled`-Inputs (dürfen `--g-ink-4` behalten).
- Layout, Abstände, Logik, Klickverhalten der betroffenen Elemente.

## Estimated Scope

- **LoC:** ca. +150 / -60 (überwiegend Einzeilen-Ersetzungen; Wächter ca. 80, Messtest ca. 70)
- **Files:** ca. 8-12 produktive Dateien plus 2 neue Tests, ggf. Fixture-Anpassungen
- **Effort:** medium (viele Inline-Styles, Parität, Golden-Fixtures)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css:205-206` | Design-Tokens | `--g-ink-3` `#6b675c` (Ziel), `--g-ink-4` `#9a958a` (nur Placeholder/Disabled); unverändert |
| `docs/adr/0008-kontrast-vor-optik.md` | ADR | Regel: `--g-ink-4` nur Placeholder/Disabled, Text ≥ 4,5:1 |
| `docs/reference/design_system.md` | Referenz | Leitprinzip und Token-Bedeutung |
| `scripts/contrast_audit.py` (`contrast_ratio`) | Skript (Issue #377) | Referenzformel für die Messlogik (WCAG-Luminanz, Alpha-Blending im Test nachgebaut) |
| `components/organisms/PresetRail.svelte:102` | Bestehender Marker | Vorbild für `audit:exempt: --g-ink-4` |
| `docs/reference/gates_und_ratschen.md` | Referenz | Ratschen-Muster mit Ausnahmeliste (z. B. i18n-Ratsche) |

## Implementation Details

```
Reihenfolge (Wächter zuerst, dann geteilt vor einzeln):

1. Wächter-Test (node --test) schreiben, zunächst rot gegen den Ist-Stand:
   - scannt frontend/src/**/*.svelte (und eingebettete <style>-Blöcke / style="…"-Attribute)
   - meldet jede Zeile mit `color: var(--g-ink-4)` (bzw. color:var(--g-ink-4) ohne Leerzeichen)
   - NICHT gemeldet: ::placeholder-Regeln, :disabled-Selektoren/Input-Disabled,
     Zeilen mit Marker `audit:exempt` (gleiche Zeile oder direkt davor)
   - Ausnahmeliste: Datei -> erlaubte Anzahl (Datei-Ebene, Zähler je Datei)
       * Ist die Anzahl in einer Datei GRÖSSER als der Zähler -> rot
       * Ist die Anzahl KLEINER als der Zähler -> rot mit Hinweis "Zähler senken" (Ratsche, darf nur sinken)
       * Datei nicht in der Liste -> Zähler 0
   - Scope-Dateien (AnlegeRahmen, AnlegeFortschritt, TripNewEditor, CompareNewEditor,
     Archiv-Seite, im Anlege-Pfad sichtbare Organismen) stehen NICHT in der Liste (Zähler 0)
   - Bestandsdateien außerhalb des Scopes stehen mit ihrem heutigen Zähler in der Liste

2. Geteilte Teile: AnlegeFortschritt ("0/6"), AnlegeRahmen (Hilfetext) -> --g-ink-3

3. TripNewEditor und CompareNewEditor in identischer Form:
   - Eyebrow, Feld-Labels, Gruppen-Überschriften, Hilfetexte, Stage-Köpfe, Hinweise -> --g-ink-3
   - Gesperrte Tabs: Text --g-ink-3, opacity 0.34/0.35 entfernt;
     "gesperrt" bleibt über Symbol ⊘, cursor:not-allowed und fehlendes Gewicht erkennbar
   - Speichern (deaktiviert): Text ≥ 4,5:1, aria-disabled="true" zusätzlich zum bisherigen
     Verhalten; Klickverhalten unverändert (heute Hintergrund --g-ink-4 + Opacity 0.45)

4. Archiv-Fußzeile ("0 von 0 Einträgen …") und Organismen im Anlege-Pfad -> --g-ink-3

5. Rein dekorative Symbole (SVG-Strokes) bekommen den Marker `audit:exempt: --g-ink-4`
   statt Änderung; Bedienelemente mit Aktion (z. B. ×-Buttons) -> --g-ink-3

6. Golden-Fixtures (tests/golden/f3_home_listen/*, f10_vergleich_flaechen/*,
   frontend/src/routes/__tests__/fixtures/auth/*.html) und Tests, die die alte Farbe festschreiben
   (issue_582_compare_design_fidelity, issue_578_molecules_organisms), prüfen und nur dort
   nachziehen, wo sie eine geänderte Stelle festschreiben.
```

## Expected Behavior

- **Input:** Nutzer öffnet `/trips/new`, `/compare/new` oder `/archiv` (Mobil 390x844).
- **Output:** Alle Texte dort sind mit mindestens 4,5:1 lesbar. Kein Textknoten hat die berechnete Farbe `#9a958a`, außer in Placeholder/deaktivierten Eingabefeldern. Gesperrte Tabs sind lesbar und bleiben als gesperrt erkennbar (Symbol, Mauszeiger, kein Gewicht).
- **Side effects:** Keine. Keine Logik-, Layout- oder Datenänderung. Der Wächter blockiert künftig neue `color: var(--g-ink-4)`-Verstöße in der Kern-Testschicht.

## Acceptance Criteria

- **AC-1:** Given die Seiten `/compare/new`, `/trips/new` und `/archiv` auf 390x844 / When jeder sichtbare Textknoten gegen seinen effektiven Hintergrund gemessen wird / Then hat kein Textknoten die berechnete Farbe `#9a958a` (`rgb(154, 149, 138)`), außer in `::placeholder` oder `:disabled`-Inputs.
  - Test: Playwright-Messlauf gegen Staging (390x844) durchläuft alle sichtbaren Textknoten der drei Seiten, liest `getComputedStyle(...).color` und meldet Treffer auf `#9a958a`.

- **AC-2:** Given ein gesperrter Tab in einem der beiden Anlege-Editoren / When seine effektive Textfarbe inklusive `opacity` (Alpha-Blending gegen den Hintergrund) berechnet wird / Then liegt der Kontrast zum Hintergrund bei mindestens 4,5:1.
  - Test: Playwright-Messlauf mit Alpha-Blending über alle Vorfahren-Opacities, Kontrast nach WCAG-Formel (Logik wie `contrast_audit.contrast_ratio`), für gesperrte Tabs in `/trips/new` und `/compare/new`.

- **AC-3:** Given `/trips/new` ohne eingegebenen Namen / When die deaktivierte Aktion „Speichern" gemessen wird / Then hat ihr Text mindestens 4,5:1 Kontrast und sie trägt `aria-disabled="true"`, und ein Klick darauf löst weiterhin nichts aus (Verhalten unverändert).
  - Test: Playwright-Messlauf gegen Staging liest Farbe, Hintergrund, Opacity und Attribut `aria-disabled`; zusätzlich Klick-Probe ohne Navigation und ohne Speicheraufruf.

- **AC-4:** Given ein neuer Svelte-Baustein setzt `color: var(--g-ink-4)` auf Fließtext / When die Kern-Testschicht läuft / Then wird die Stelle vom Wächter rot gemeldet, während `::placeholder`, `:disabled`-Inputs und mit `audit:exempt` markierte Stellen nicht gemeldet werden.
  - Test: `node --test` Wächter über `frontend/src`; Gegenprobe mit einer temporär eingeschleusten Verfälschung (neue Datei bzw. zusätzliche Zeile) muss rot werden, die Ausnahmefälle müssen grün bleiben.
  - Einordnung: bewusstes Ratschen-Gate nach Muster der i18n-Ratschen (`docs/reference/gates_und_ratschen.md`). Der Quellcode ist hier der Gegenstand der Regel, kein Ersatz für einen Verhaltensnachweis; das Verhalten im Browser belegen AC-1 bis AC-3 und AC-5. Der Wächter trägt den Marker `# doc-compliance-test` (Ausnahme der Test-Politik).

- **AC-5:** Given die beiden Anlege-Editoren `/trips/new` und `/compare/new` / When gleichartige Elemente (Eyebrow, Feld-Labels, Fortschritt, Hilfetext, gesperrte Tabs) verglichen werden / Then haben sie dieselbe Textfarbe (`--g-ink-3`, `#6b675c`) und dieselbe Behandlung gesperrter Tabs (ohne Zusatz-Opacity, Sperre über Symbol und Mauszeiger), damit beide Editoren gleich aussehen.
  - Test: Playwright-Messlauf liest für je ein Element dieser Klassen in beiden Editoren die berechnete Farbe und Opacity und vergleicht sie; ein einseitiger Unterschied ist rot.

- **AC-6:** Given die Ratsche (Ausnahmeliste auf Datei-Ebene mit Zähler je Datei) / When die Anzahl der `color: var(--g-ink-4)`-Treffer je Datei mit dem Zähler verglichen wird / Then ist jede Scope-Datei (Anlege-Editoren, `AnlegeRahmen`, `AnlegeFortschritt`, Archiv-Seite, im Anlege-Pfad sichtbare Organismen) bei Zähler 0, kein Zähler in der Liste steigt, und ein Treffer über dem Zähler oder in einer nicht gelisteten Datei lässt den Wächter rot werden, wobei dekorative SVG-Symbole nur per `audit:exempt` ausgenommen sind.
  - Test: `node --test` Wächter prüft (a) Zähler je Datei als Obergrenze, (b) Scope-Dateien sind sauber, (c) Zähler größer als tatsächliche Anzahl wird ebenfalls rot („Zähler senken"), (d) `audit:exempt` wirkt nur mit Marker an der Stelle.
  - Einordnung wie AC-4: Ratschen-Gate mit Marker `# doc-compliance-test`; Browser-Verhalten belegen AC-1 bis AC-3.

## Geplante Tests

| Schicht | Test | Nachweis |
|---------|------|----------|
| Kern (deterministisch, ohne Netz) | `ink4_waechter` (neu, `node --test`, unter `frontend/src/lib/**/__tests__/`) | AC-4, AC-6 |
| Live-E2E (nur in `/e2e-verify`) | Playwright-Kontrastmessung gegen Staging `https://staging.gregor20.henemm.com`, Viewport 390x844, Alpha-Blending, Kontrastformel wie `contrast_audit.contrast_ratio` | AC-1, AC-2, AC-3, AC-5 |
| Bestandstests | Golden-Fixtures (`tests/golden/f3_home_listen/*`, `f10_vergleich_flaechen/*`, `frontend/src/routes/__tests__/fixtures/auth/*.html`), `routes/compare/__tests__/issue_582_compare_design_fidelity.test.ts`, `molecules/issue_578_molecules_organisms.test.ts`, E2E `kuerzel-legende-lesbar.staging.spec.ts` | prüfen, ob sie die alte Farbe an geänderten Stellen festschreiben; nur dann nachziehen. Verhaltensnachweis bleibt unverändert |
| Fresh-Eyes | Screenshot gesperrter Tabs und deaktivierter Aktion (390x844) | Sperre bleibt visuell erkennbar, Layout unverändert |

Die Frontend-Tests laufen über `node --test` (kein Vitest). Kein Mock-Theater: der Wächter liest echte Quelldateien als Fixture-Eingabe des Scanners; die Verhaltensnachweise kommen aus dem gerenderten DOM.

## Dateiliste (geplant)

| Datei | Änderung |
|-------|----------|
| `frontend/src/lib/components/shared/anlege-rahmen/AnlegeFortschritt.svelte` | MODIFY |
| `frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte` | MODIFY |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY |
| `frontend/src/routes/archiv/+page.svelte` | MODIFY |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | MODIFY |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`, `CorridorEditor.Mobile.svelte` | MODIFY |
| weitere im Anlege-Pfad sichtbare Organismen (per Grep belegt) | MODIFY |
| Wächter `ink4_waechter` (`node --test`) inkl. Ausnahmeliste | CREATE |
| Playwright-Kontrastmesstest (Staging, 390x844) | CREATE |
| Golden-Fixtures / `issue_582`, `issue_578` | MODIFY nur falls betroffen |
| `frontend/src/app.css`, `routes/_design/+page.svelte` | unverändert |

## Test Plan

Siehe `## Geplante Tests`: Kern-Schicht `ink4_waechter` (`node --test`, AC-4/AC-6); Live-E2E Playwright-Kontrastmessung gegen Staging bei 390x844 (AC-1/2/3/5); Bestandstests und Golden-Fixtures auf festgeschriebene Altfarbe prüfen; Fresh-Eyes-Blick auf gesperrte Tabs und deaktivierte Aktion.

## Definition of Done

- AC-1 bis AC-6 erfüllt und nachgewiesen (Kern-Schicht grün, Staging-Messlauf grün).
- Kein Text auf `/trips/new`, `/compare/new`, `/archiv` mit `--g-ink-4` außer Placeholder/Disabled; gesperrte Tabs und deaktiviertes „Speichern" bei mindestens 4,5:1.
- Trip- und Compare-Editor sind in Farbe und Tab-Behandlung gleich (Pendant-Sperre).
- Ratschen-Ausnahmeliste vorhanden, Scope-Dateien bei Zähler 0, Zähler nur fallend.
- Alle 6 CI-Checks grün, Deploy und Selftest ohne Befund.

## Known Limitations

- Der Bestand außerhalb von Anlege-Pfad und Archiv (insgesamt ca. 84-90 Fundstellen in rund 27 Svelte-Dateien) bleibt zunächst in der Ausnahmeliste; Abbau in Epic #368/#2508. Die Liste darf nur sinken.
- Dark-Mode-Kontrast von `--g-ink-3` (#2400) und Danger-Rot (#1831) sind nicht Teil.
- Die Design-Seite zeigt die Ratio 2,98 statt 2,85; Korrektur gehört zu #1831/#2508.
- Der Staging-Messlauf braucht eingeloggte Staging-Sitzung (Staging-`.env`); lokaler Nachweis ersetzt ihn nicht.

## Risiken

- **Umfang:** viele Inline-Styles in rund 8-12 Dateien; Gegenmaßnahme: Wächter zuerst, jede Ersetzung ist eine Einzeilenänderung.
- **Trip/Vergleich-Parität (Gate):** einseitige Änderung wäre ein Verstoß; AC-5 und geteilter Rahmen zuerst fangen das ab.
- **Gesperrte Tabs:** Ohne Opacity verlieren sie Abstand zu aktiven Tabs; Gegenmaßnahme: Symbol ⊘, `cursor:not-allowed`, fehlendes Gewicht; Fresh-Eyes-Prüfung.
- **Deaktivierte Speichern-Aktion:** `aria-disabled` darf das Klickverhalten nicht ändern; AC-3 enthält eine Klickprobe.
- **Golden-Fixtures und Tests mit alter Farbe:** können rot werden; gezielt nachziehen, nicht blind aktualisieren.
- **Wächter-Fehlalarme:** `::placeholder`, `:disabled` und `audit:exempt` sauber erkennen; Gegenprobe in AC-4/AC-6.
- **Alpha-Blending im Messtest:** Opacity von Vorfahren muss einbezogen werden, sonst wird AC-2 zu optimistisch gemessen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0008 „Kontrast vor Optik" wird umgesetzt, nicht geändert)
- **Rationale:** Die Spec setzt die bestehende Entscheidung durch. Die Ratsche mit Ausnahmeliste auf Datei-Ebene und Zähler je Datei (darf nur sinken) folgt dem etablierten Muster der i18n-Ratschen in `docs/reference/gates_und_ratschen.md`. Dekorative SVG-Symbole werden per `audit:exempt` ausgenommen statt geändert (Tech-Entscheidung).

## Changelog

- 2026-11-09: Initial spec created (Issue #2371, Epic #2508 Strang B)
