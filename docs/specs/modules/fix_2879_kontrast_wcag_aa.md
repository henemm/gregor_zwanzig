---
entity_id: fix_2879_kontrast_wcag_aa
type: bugfix
created: 2026-11-09
updated: 2026-11-09
status: approved
version: "1.0"
workflow: fix-2879-kontrast
tags: [frontend-only, kontrast, wcag-aa, design-system, trip-compare-teilung, design-audit-2026-11-09]
---

# Kontrast nach WCAG-AA auf Trip- und Vergleichsseiten (Issue #2879)

## Approval

- [x] Approved (PO Henning, 2026-11-09, Freigabe per AskUserQuestion)

## Purpose

Das Audit vom 9.11.2026 hat auf den Trip- und Vergleichsseiten Text gefunden, der die WCAG-AA-Schwelle verfehlt (Text 4,5:1, großer Text ab 24 px bzw. 18,66 px fett 3:1). Leitprinzip (PO-bestätigt 2026-05-25, `docs/reference/design_system.md`): **Hoher Kontrast gewinnt gegen weiche Optik.**

Gemessene Fälle (WCAG-Formel, Token-Werte aus `frontend/src/app.css`):

| # | Wo | Ist |
|---|---|---|
| K1 | Handy-Reiterleiste, aktiver Reiter (beide Hubs) | Papier auf Accent, 13 px/600 = 3,94:1 |
| K2 | Zähler im aktiven Handy-Reiter | 2,79:1 |
| K3 | Knopf-Variante Accent (Weiter, „+ Neuer Trip“ im Leerzustand, Handy-Knopf unten, Alarm-Stufenknöpfe, Kreis-Knöpfe beim Orte-Wählen) | Weiß auf Accent = 4,34:1 |
| K4 | Fortschrittszähler „n von 5 Abschnitten“ | `--g-ink-4` = 2,71:1 |
| K5 | `--g-ink-4` als Lesetext (Status „· aktiv“ in beiden Listen, Zähler „1 von 1 Vergleichen“, Kennzahl-Beschriftungen der Übersicht, Etappen-Streifen, Feld-Hinweise, Leer-Titel „Noch kein Name“ u. a.) | 2,46 bis 2,98:1 |
| K6 | Kürzel „GR20N“ in Accent im Trip-Titel am Handy (20 px) | 3,94:1 |
| K7 | Rangnummern 01/02/03 im Orte-Reiter des Vergleichs in Accent, 13 px | 4,34 bzw. 3,58:1 (Zebrazeile) |

**Entscheidung (Tech Lead, im Issue vorgezeichnet):**
1. **Accent als Fläche unter Text** wird zu `--g-accent-deep` (#8c3e1a): Weiß darauf = 7,45:1, Papier darauf = 6,77:1. Das betrifft die Knopf-Variante Accent (`app.css`, `MBtn`), den aktiven Handy-Reiter und alle handgeschriebenen Accent-Flächen mit Text auf den Trip-/Vergleichsseiten. Hover: 85 % `--g-accent-deep` mit Schwarz gemischt.
2. **Accent als Textfarbe** (Kürzel im Titel, Rangnummern) wird zu `--g-accent-deep` (6,77:1 auf Papier, über 6:1 auf `--g-paper-deep`).
3. **`--g-accent` bleibt**, wo es keinen Text trägt: Unterstrich des aktiven Reiters, Fortschritts-Segmente, Rahmen, Punkte. Dort gilt die Nicht-Text-Schwelle 3:1 (Accent auf Papier 3,94:1, erfüllt).
4. **`--g-ink-4` nur noch für Platzhalter und gesperrte Elemente** (wie `design_system.md` schon sagt). Jeder Lesetext, der heute `--g-ink-4` (oder `--g-ink-faint`) nutzt, bekommt `--g-ink-3` (5,13:1 auf Papier, 4,66:1 auf `--g-paper-deep`).
5. **Zähler im aktiven Handy-Reiter** wird neutral wie alle Zähler: Grund `--g-paper-deep`, Schrift `--g-ink-3` (4,66:1), passend zu ADR-0110 („Zähler neutral“).
6. **ADR-0110 bekommt einen Nachtrag:** „Weiter“ bleibt die Accent-Variante, deren Fläche ist jetzt `--g-accent-deep`; damit ist der im ADR selbst festgehaltene AA-Verstoß behoben. Keine stille Abweichung.

**Nicht hier:** Fundstellen, die nur in den Reitern Wertebereiche, Alarme und Layout liegen (`CorridorEditor*`, `AlarmeTab`, `layout-tab/*`, `AlertChannelPicker`, sofern nur dort genutzt) und im Reiter Wetter-Metriken, entfallen bzw. werden mit #2794 neu gebaut; sie sind dort als Eingabe vermerkt. Disabled-Zustände (`[disabled]`, `aria-disabled="true"`) sind nach WCAG ausgenommen und bleiben `--g-ink-4`.

## Source

- **Geändert (Auswahl, vollständige Liste ergibt sich aus dem Prüftest AC-1):**
  - `frontend/src/app.css`: `[data-slot="btn"][data-variant="accent"]` Fläche und Rand `--g-accent-deep`, Schrift `var(--g-paper)` statt `#fff`, Hover dunkler.
  - `frontend/src/lib/components/mobile/MBtn.svelte`: Variante `accent` mit `--g-accent-deep`.
  - `frontend/src/lib/components/mobile/MTabBar.svelte`: aktiver Handy-Reiter `--g-accent-deep`; Zähler im aktiven Reiter neutral.
  - `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `frontend/src/lib/components/compare/steps/Step2Orte.svelte`, `frontend/src/lib/components/compare-new/CompareNewEditor.svelte`: handgeschriebene Accent-Flächen mit Text und `--g-ink-4`-Lesetext.
  - `frontend/src/lib/components/shared/anlege-rahmen/AnlegeFortschritt.svelte`, `AnlegeRahmen.svelte` (Leer-Titel), `organisms/ListNameCell.svelte`, `organisms/ListTableRow.svelte`, `routes/trips/+page.svelte`, `routes/compare/+page.svelte`, `shared/hub-uebersicht/HubUebersicht.svelte`, `atoms/Stat.svelte`, `trip-detail/waypoints/EtappenStrip.svelte`, `trip-detail/waypoints/StageCard.svelte`, `mobile/StageCardM.svelte`, `mobile/MField.svelte`, `molecules/Field.svelte` (Hinweis), `trip-detail/TripHeader.svelte` (Kürzel), `molecules/CompareLocationRow.svelte` (Rang).
  - `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md`: Nachtrag.
  - `docs/reference/design_system.md`: Abschnitt Accent um die Regel „Accent unter Text = accent-deep“ ergänzen.
- **Neu:** `frontend/e2e/kontrast-trip-vergleich.spec.ts`; der Messhelfer (Hintergrund über die Vorfahren suchen, Transparenz mischen, Verhältnis berechnen) wandert aus `kuerzel-legende-lesbar.staging.spec.ts` nach `frontend/e2e/helpers.ts` und wird von beiden genutzt.

> **Schicht:** nur Frontend und Doku.
> **Trip/Ortsvergleich-Teilung:** Änderungen in geteilten Bausteinen wirken auf beiden Seiten gleich; der Test prüft beide Seiten.
> **Mandantentrennung / Kanäle:** nicht betroffen (keine Mail-Darstellung; Mail-Farben sind nicht Teil dieser Spec).

## Estimated Scope

- **LoC:** ca. +60 / -60 Code (Farbwerte), ca. +250 Test
- **Files:** ca. 20 Komponenten, 1 neue E2E-Datei, Helfer, 2 Doku-Dateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Tokens `--g-accent-deep`, `--g-ink-3`, `--g-paper-deep` | Design-Tokens | vorhanden, keine neuen Tokens |
| `frontend/e2e/helpers.ts` `kontrastVerhaeltnis` | Testhelfer | wird um Vorfahren-Suche und Mischung erweitert |
| ADR-0110 | ADR | Nachtrag |
| #2880 | Vorgänger | ändert Anlegen-Bausteine; diese Spec läuft danach |

## Implementation Details

1. Prüftest zuerst (RED): `kontrast-trip-vergleich.spec.ts` sammelt auf jeder geprüften Seite alle sichtbaren Textknoten (TreeWalker über Textknoten mit nicht-leerem Text, Element sichtbar, `opacity` > 0, im Viewport oder per Scrollen erreichbar), berechnet Schriftfarbe gegen den effektiven Hintergrund (erster deckender Vorfahre, transparente Schichten gemischt) und vergleicht mit 4,5:1 bzw. 3:1 für großen Text (`font-size` ≥ 24 px oder ≥ 18,66 px bei `font-weight` ≥ 700). Ausnahmen: Element oder Vorfahre mit `disabled` oder `aria-disabled="true"`, Platzhaltertext, Elemente mit `aria-hidden="true"`. Die Meldung nennt je Verstoß Seite, Text, Farben, Verhältnis und einen CSS-Pfad.
2. Danach die Farben wie in der Entscheidung oben umstellen, bis der Test grün ist.
3. Pflicht-Mutationen: (a) `app.css` Accent-Knopf zurück auf `--g-accent`, (b) `ListNameCell` Status zurück auf `--g-ink-4`, (c) aktiver Handy-Reiter zurück auf `--g-accent`, (d) im Prüfhelfer die Mischung transparenter Hintergründe entfernen. (a) bis (c) müssen AC-1/AC-2 rot machen; (d) muss den Zähler-Fall K2 (transluzenter Grund) übersehen lassen und damit einen Helfer-Selbsttest rot machen.

## Expected Behavior

- **Input:** Trip-Liste, Vergleichsliste, Trip-Hub und Vergleichs-Hub (Kopf, Reiterleiste, Reiter Übersicht und Etappen bzw. Orte), Anlegen von Trip und Vergleich (alle Schritte, die ohne Netz erreichbar sind).
- **Output:** jeder sichtbare Text erfüllt WCAG-AA.
- **Side effects:** Accent-Knöpfe und der aktive Handy-Reiter werden dunkler (rostbraun statt orange). Graue Hinweise und Zähler werden etwas dunkler. Unterstriche, Fortschrittsbalken und Rahmen behalten das helle Orange.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit einem Trip (3 Etappen) und einem Ortsvergleich (3 Orte) / When Trip-Liste, Vergleichsliste, Trip-Hub (Kopf, Reiterleiste, Reiter Übersicht und Etappen) und Vergleichs-Hub (Kopf, Reiterleiste, Reiter Übersicht und Orte) bei 1280 × 900 Pixel auf Deutsch und auf Englisch geöffnet werden / Then hat jeder sichtbare, nicht gesperrte Textknoten ein Kontrastverhältnis zu seinem effektiven Hintergrund von mindestens 4,5:1, großer Text mindestens 3:1.
  - Test: Playwright `kontrast-trip-vergleich.spec.ts` KO-1, Verstoßliste muss leer sein.

- **AC-2:** Given dieselben Seiten bei 390 × 844 Pixel / When sie auf Deutsch und Englisch geöffnet werden, jeweils mit einem aktiven Reiter, der einen Zähler trägt (Etappen bzw. Orte) / Then gilt dieselbe Schwelle für jeden sichtbaren Textknoten, ausdrücklich auch für den aktiven Reiter (K1), seinen Zähler (K2) und das Kürzel im Trip-Titel (K6).
  - Test: Playwright KO-2.

- **AC-3:** Given das Anlegen eines Trips und eines Vergleichs bei 1280 × 900 und 390 × 844 Pixel, auf Deutsch und Englisch / When jeder ohne Netz erreichbare Schritt geöffnet wird, einmal ohne Namen (Weiter gesperrt) und einmal mit Namen (Weiter aktiv) / Then erfüllt jeder sichtbare, nicht gesperrte Textknoten die Schwelle, ausdrücklich auch der aktive „Weiter“-Knopf, der Handy-Knopf unten und der Fortschrittszähler (K3, K4).
  - Test: Playwright KO-3.

- **AC-4:** Given die Liste mit Trips bzw. Vergleichen / When die Statuszeile „· aktiv“ und der Zähler „x von y“ gemessen werden / Then liegen beide bei mindestens 4,5:1, und `--g-ink-4` erscheint auf diesen Seiten als Schriftfarbe nur an gesperrten Elementen oder Platzhaltern.
  - Test: Playwright KO-4, alle Textknoten mit Schriftfarbe rgb(154, 149, 138) (`--g-ink-4`) müssen eine Ausnahme (gesperrt, Platzhalter) erfüllen.

- **AC-5:** Given ein aktiver „Weiter“-Knopf / When er betrachtet und dann mit der Maus überfahren wird / Then ist die Fläche `--g-accent-deep` (rgb(140, 62, 26)) bzw. im Hover dunkler, die Schrift hell, das Verhältnis in beiden Zuständen mindestens 4,5:1; der Unterstrich des aktiven Hub-Reiters am Computer bleibt `--g-accent` (rgb(196, 90, 42)).
  - Test: Playwright KO-5, `getComputedStyle` vor und nach `hover()`.

- **AC-6:** Given der Messhelfer / When er auf eine Testseite mit bekannten Farben angewandt wird (deckender Grund, transluzenter Grund über Accent, gesperrter Knopf, aria-hidden-Text) / Then meldet er genau die bekannten Verstöße (z. B. Papier auf rgba(255,255,255,0.22) über Accent = 2,79:1) und keine Ausnahmen.
  - Test: Playwright KO-6 über `page.setContent()` mit festem HTML (Selbsttest des Helfers, schützt AC-1 bis AC-4 gegen einen stumpfen Helfer).

## Test Plan

- Playwright KO-1 bis KO-6 am isolierten Stack, Trip und Vergleich, DE und EN, Computer und Handy.
- Bestehende Tests, die feste Farben erwarten (z. B. Accent-Knopf weiß auf `--g-accent`), werden auf die neue Regel umgestellt, nicht gelöscht.
- RED-Nachweis: KO-1 bis KO-4 schlagen auf dem Stand vor der Umsetzung mit den Fällen K1 bis K7 fehl.

## Definition of Done

- AC-1 bis AC-6 grün, Adversary VERIFIED mit den vier Pflicht-Mutationen gefangen.
- ADR-0110-Nachtrag und `design_system.md` aktualisiert; ADR-Index konsistent (`tests/test_adr_index_drift.py`).
- PR mit allen 6 CI-Checks grün gemergt; Staging-Prüfung und Prod-Deploy über die Server-Sitzung; Fresh-Eyes-Blick auf Screenshots (Liste, Hub, Anlegen, Handy).

## Known Limitations

- Mail-, Telegram- und SMS-Darstellung sind nicht Teil dieser Spec.
- Seiten außerhalb von Trip und Vergleich (Konto, Archiv, Startseite) werden nur mitgezogen, soweit sie dieselben Bausteine nutzen; ein eigener Prüflauf für sie ist nicht Teil dieser Spec.
- Der Fortschrittsbalken beim Anlegen (offene Segmente `--g-rule`, 1,4:1) ist Nicht-Text und trägt keine eigene Information (der Zähler daneben sagt dasselbe als Text); die Festlegung dazu trifft ADR-0111 aus #2881.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** Nachtrag zu ADR-0110 (kein neues ADR).
- **Rationale:** ADR-0110 hält selbst fest, dass Weiß auf Accent AA verfehlt, und verlangt doch „Weiter“ in Accent. Der Nachtrag löst den Widerspruch nach dem PO-Leitprinzip auf, ohne die Rollenverteilung (Hauptaktion Ink, Weiter Accent) zu ändern.

## Changelog

- 2026-11-09: Initial spec (Issue #2879).
- 2026-11-09: Vom PO freigegeben.
