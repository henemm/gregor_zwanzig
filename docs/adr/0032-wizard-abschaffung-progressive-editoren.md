# ADR-0032: Multi-Step-Wizards abgeschafft — progressive Tab-Editoren mit Auto-Save

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-07-22 — PO-bekräftigt 2026-07-19, Issue #1343)
- **Datum:** 2026-07-22
- **Bezug:** #622 (TripNewEditor), Epic #1273/#1301 (Compare-Konsolidierung), CLAUDE.md §Trip/Ortsvergleich-Code-Teilung, `shared/__tests__/legacy_wizard_removed.test.ts`

## Kontext

Trip-Anlage (Epic #136) und Compare-Anlage (Epic #438) waren als 4- bzw.
5-Schritt-Wizards mit Stepper gebaut. Zwei parallele Wizard-Systeme
duplizierten Editor-Logik, wichen vom Bearbeitungs-Pfad (Detail-Hub mit Tabs)
ab und erzeugten wiederholt Drift zwischen Anlegen und Bearbeiten.

## Entscheidung

Es gibt keine Multi-Step-Wizards mehr. Anlegen und Bearbeiten verwenden
dasselbe Muster: progressive Tab-Editoren mit Auto-Save aus geteilten
Bausteinen (`shared/`-Tab-Organismen, Parameter `context="route"|"vergleich"`).
`/trips/new` = `TripNewEditor` (#622), `/compare/new` = `CompareNewEditor`
(#1301 F2). `trip-wizard/`, `CompareWizard.svelte` und `CompareEditor.svelte`
wurden ersatzlos gelöscht; die Entfernung ist testgesichert
(`legacy_wizard_removed.test.ts`). **Es gibt keine offene Designfrage dazu —
nicht erneut vorlegen** (PO, 2026-07-19).

## Verworfene Alternativen

- **Wizards beibehalten und teilen** — Stepper-Semantik (linear, abschließend)
  passt nicht zum Auto-Save-Modell und bleibt ein zweites Editor-Paradigma.
- **Eigener Compare-Anlege-Editor** — verletzt die Code-Teilungs-Invariante
  (Anti-Pattern-Referenz #1170).

## Konsequenzen

- **Positiv:** Ein Editor-Paradigma, geteilte Bausteine, Anlegen = Bearbeiten.
- **Negativ / Preis:** Kein „Schritt-für-Schritt-geführt"-Gefühl für
  Erstnutzer; Freischalt-Logik (`tripNewLogic.ts`/`compareNewLogic.ts`) muss
  Progressive Disclosure leisten.
- **Folgepflichten:** Neue Anlege-/Editor-Flächen folgen dem geteilten Muster;
  eine neue Compare-Komponente mit Trip-Pendant (oder umgekehrt) ist ein
  Verstoß, Ausnahme nur mit dokumentierter Begründung in der Spec.
