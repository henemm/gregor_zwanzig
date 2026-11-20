---
entity_id: fix_3212_was_steht_wo_tippflaeche
type: bugfix
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: fix-3212-was-steht-wo-tippflaeche
tags: [frontend, tippflaeche, was-steht-wo, 3212]
---

# Fix #3212: Tippfläche in der Karte „Was steht wo“ (Roh/Einfach, E-Mail-Format)

## Approval

- [ ] Approved

## Purpose

In der Karte „Was steht wo“ (Reiter Wetter) sind „Roh“, „Einfach“ und die Segmente des E-Mail-Formats kleiner als 44 px antippbar; der Wächter AC-40 (`s3a2794-teil3-design`) ist rot. Der Fix gibt allen diesen Knöpfen eine unsichtbare 44-px-Tippfläche, ohne die sichtbare Optik laut Mockup Fassung 4 zu ändern.

## Source

- **File:** `frontend/src/lib/components/atoms/RohEinfachKnopf.svelte`, `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte`
- **Identifier:** `RohEinfachKnopf` (Knopf `.rek`), Segmented `was-steht-wo-email-format`

> Schicht: Frontend (SvelteKit), kein Go-/Python-Anteil, frontend-only Deploy.
> Trip/Ortsvergleich: Die Karte und die Bausteine liegen bereits geteilt vor (Atom/Molekül/Organismus); es entsteht keine neue Komponente, Trip und Orts-Vergleich erben den Fix gemeinsam.
> Mandantentrennung: keine Nutzerdaten betroffen. Kanäle: kein Briefing-/Alarm-Inhalt betroffen.

## Scope

### Im Scope
- `RohEinfachKnopf`: Knopf bekommt `data-tap="true"` und eine unsichtbare `::before`-Tippfläche `max(100%, var(--g-tap-min))` auf allen Breiten (Desktop und Mobil).
- `WasStehtWoKarte`: Segmented „E-Mail: Format“ wechselt von `size="sm"` auf `variant="kompakt"`.
- Node-Tests (RED/GREEN) und Staging-E2E-Wächter AC-40.

### Nicht im Scope
- Sichtbare Größe/Optik von Pille und Segmenten (bleibt laut Mockup `.mini` bzw. `.seg`).
- Keine `min-height: 44` auf Desktop (würde Zeilen aufblähen), keine Änderung der Wächterregeln, Tokens oder Goldens, keine Änderung der `size="sm"`-Regel in `app.css`.
- Haken-Atom, KanalTabelle, MetrikZeile (nutzen kompakt bereits).

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/atoms/RohEinfachKnopf.svelte` | MODIFY | `data-tap="true"`, `position:relative`, `::before` für alle Breiten |
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | MODIFY | `variant="kompakt"` statt `size="sm"` |
| `frontend/src/lib/components/atoms/__tests__/haken_roh_einfach.test.ts` | MODIFY | RED: Knopf trägt `data-tap="true"` |
| `frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts` | MODIFY | RED: Segmented rendert `data-variant="kompakt"` |

## Estimated Scope

- **LoC:** ~+30/-10
- **Files:** 4
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Segmented.svelte` (ui) | component | Prop `variant="kompakt"` mit `::before`-Tippfläche |
| `app.css` (`--g-tap-min`, Segmented kompakt, Btn `data-tap`) | stylesheet | bestehende Tokens/Muster, unverändert |
| `EinstellTabelle.svelte` | component | Einsatzort von `RohEinfachKnopf` (Raster unverändert) |
| `frontend/e2e/s3a2794-teil3-design.spec.ts` (AC-40) | E2E-Wächter | erkennt `data-tap` und kompakt, prüft per `elementFromPoint` |
| Mockup `mockup-hub-fassung4.html` | Design-Vorgabe | `.mini` (Roh/Einfach), `.seg` (E-Mail-Format) |
| KanalTabelle, MetrikZeile, `_design-system/einstelltabelle` | Mitnutzer | wirken mit, Optik darf sich nicht ändern |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird nur ein vorhandenes Muster (`data-tap` mit `::before`, Segmented `kompakt`) angewendet; ADR-0112 (Bausteine nur in Atomen/Molekülen, keine eigenen Styles außerhalb) bleibt eingehalten, da die Änderung im Atom selbst liegt.

## Implementation Details

1. `RohEinfachKnopf.svelte`: Knopf `.rek` erhält `data-tap="true"`, `position: relative` und `.rek::before` (absolut, zentriert, `width`/`height: max(100%, var(--g-tap-min))`, transparent). Pille (Padding 3/6, 10.5 px mono) unverändert. Die Mobil-Regel (min 44×44 am Knopf, Raster-Spalte 44) bleibt bestehen oder wird auf `::before` vereinheitlicht, solange die Raster-Spalte unverändert bleibt.
2. `WasStehtWoKarte.svelte` (~Z. 244-259): `size="sm"` entfällt, `variant="kompakt"` kommt, wie in KanalTabelle/MetrikZeile. `rolle="radio"` und testids bleiben.
3. Risiko Überlappung: Die Fläche von „Roh“ (32 px breit) ragt ca. 6 px seitlich in Nachbarn. Die Ecken-Treffer werden live in Playwright (Desktop und Mobil) geprüft; bei Fehltreffern wird die Fläche nicht per Wächter-Ausnahme, sondern durch Stapelreihenfolge/Abstand korrigiert.

## Expected Behavior

- **Input:** Tippen oder Klicken an einem Punkt innerhalb von 44×44 px um „Roh“, „Einfach“ oder ein E-Mail-Format-Segment.
- **Output:** Der gemeinte Knopf löst aus; Pille und Segmente sehen unverändert aus (Mockup Fassung 4).
- **Side effects:** Keine; Zeilenhöhe und Raster der Tabelle bleiben gleich.

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1: GIVEN eine gerenderte Zeile mit `RohEinfachKnopf` WHEN das Markup geprüft wird THEN trägt der Knopf `data-tap="true"` (vorher rot).
- [ ] Test 2: GIVEN die gerenderte Karte WHEN das E-Mail-Format-Segmented geprüft wird THEN hat es `data-variant="kompakt"` und kein `data-size="sm"`.
- [ ] Test 3 (E2E, Staging, Desktop und Mobil): GIVEN der Reiter Wetter WHEN AC-40 aus `s3a2794-teil3-design.spec.ts` läuft THEN meldet er keine Ziele < 44 px.
- [ ] Test 4 (E2E): GIVEN die Karte WHEN `elementFromPoint` an den vier Ecken (±21 px) und der Mitte jedes Roh-/Einfach-Knopfs und Segments geprüft wird THEN trifft es das jeweils eigene Element.
- [ ] Gegenprobe: `data-tap` entfernen ⇒ AC-40 rot; `variant` zurück auf `sm` ⇒ rot.

## Acceptance Criteria

- **AC-1:** Given die Karte „Was steht wo“ im Desktop-Fenster / When der Wächter die Tippfläche von „Roh“ und „Einfach“ misst (Messweise wie AC-40: Trefferpunkte im 44×44-Quadrat) / Then liegt jeder Punkt auf dem jeweiligen Knopf.
  - Test: Playwright Desktop, AC-40 auf Reiter Wetter, keine Meldung für `RohEinfachKnopf`.
- **AC-2:** Given die Karte auf einem Mobil-Fenster / When die Tippfläche von „Roh“ und „Einfach“ (Kurzwort „Einf.“) gemessen wird / Then beträgt sie mindestens 44×44 px und das Raster bleibt unverändert.
  - Test: Playwright Mobil, AC-40 grün, Spaltenbreite der Zeile unverändert.
- **AC-3:** Given die Zeile „E-Mail: Format“ (Ausführlich/Kompakt) auf Desktop und Mobil / When die Tippfläche beider Segmente gemessen wird / Then beträgt sie mindestens 44×44 px (Messweise wie AC-40).
  - Test: Playwright Desktop und Mobil, testids `was-steht-wo-email-format-full|compact`, Ecken-Treffer.
- **AC-4:** Given die Karte vor und nach dem Fix / When die sichtbare Größe der Roh-/Einfach-Pille (32×22 / 56×22) und der Segmente verglichen wird / Then ist sie unverändert und entspricht dem Mockup Fassung 4 (`.mini` bzw. `.seg`).
  - Test: Playwright misst Bounding-Box der Pille (unverändert) und Zeilenhöhe der Tabelle (nicht größer als vorher).
- **AC-5:** Given nebeneinanderliegende Knöpfe (Haken, Roh, Einfach, Segmente) / When an den Ecken und der Mitte der 44×44-Fläche geklickt wird / Then löst nur der gemeinte Knopf aus und kein Nachbar erhält den Treffer.
  - Test: Playwright `elementFromPoint` an Ecken (1 px eingerückt) plus echter Klick auf Ecke von „Roh“, Zustand des Nachbarn bleibt unverändert.
- **AC-6:** Given die Karte kommt im Trip-Editor und im Orts-Vergleich-Editor vor / When AC-1 bis AC-5 in beiden geprüft werden / Then gelten sie gleich in beiden Kontexten.
  - Test: Playwright für `context="route"` und `context="vergleich"`, soweit die Karte dort gerendert wird.
- **AC-7:** Given der Fix ist ausgeliefert / When der Wächter `s3a2794-teil3-design` AC-40 gegen Staging läuft / Then sind Desktop und Mobil grün.
  - Test: Staging-E2E `s3a2794-teil3-design.spec.ts` AC-40 Desktop und Mobil, Exit 0.

## Definition of Done

- Node-Tests aus dem Test Plan rot nachgewiesen, danach grün; CI-Checks grün.
- Staging-E2E AC-40 Desktop und Mobil grün, Ecken-Treffer ohne Fehltreffer.
- Visueller Vergleich gegen Mockup Fassung 4: Pille und Segmente unverändert.
- Adversary-Mutation (`data-tap` entfernen, `variant` zurück auf `sm`) wird von Tests gefangen.
- Mitnutzer (KanalTabelle, MetrikZeile, Design-System-Seite) optisch unverändert.
- Prod-Deploy, Selftest Exit 0, Issue #3212 geschlossen.

## Known Limitations

- Die 44-px-Fläche überlappt unsichtbar die Nachbarschaft (Roh ca. 6 px seitlich); Treffer an Überlappungen entscheidet die Stapelreihenfolge und wird nur an den geprüften Punkten abgesichert.
- Der Mobil-Knopfboden (36 px) greift bei Segmenten nicht mehr, weil `kompakt` die Tippfläche selbst liefert.

## Changelog

- 2026-11-20: Initial spec created (Issue #3212)
