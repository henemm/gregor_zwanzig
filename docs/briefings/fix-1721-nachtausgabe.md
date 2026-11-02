---
spec_file: docs/specs/modules/fix_1721_nachtausgabe.md
spec_sha256: ff52d865ed2a334af1a7fefcbfe2e06ff28118f21b737eebdb0431e23df2ab6c
spec_frozen_sha256: 3add61b8ff375f3451b940f51e4df0dd834d3369d6b3fcc02f38449438e6c5ec
---

# PO-Briefing: fix-1721-nachtausgabe

- **Spec:** docs/specs/modules/fix_1721_nachtausgabe.md
- **Issue:** #1721
- **Erstellt:** 2026-11-02

## Was gebaut wird

Im Wetter-Metriken-Reiter eines Trips lässt sich die Nacht-Stundentabelle der Mail ein- und ausschalten.

## Definition of Done

Mit ausgeschaltetem Schalter kommt die Trip-Mail ohne Nacht-Stundentabelle, behält Nacht-Tiefstwert und Gewitter-Aussage, und der Schalter bleibt nach Neuladen aus.

## Wie geprüft wird

Browser-Klickpfad mit zwei Nutzern und zugestellte Staging-Mails belegen Schalter und Mail; der Nachtgewitter-Fall hängt von den Wetterdaten ab.

## Kritische Anmerkungen

- Spec wurde nach dem Bauen korrigiert: Der Ausblick zeigt eine Spalte "Temp" (min/max, z.B. 3/9), nicht zwei Spalten; Code war schon gemerged.
- Ticketpunkte 2 (Spalte N) und 3 (FN) brauchen keinen Code, nur Nachweis; Punkt 2 wurde per Spec-Anpassung entschieden.
- Der Schalter erscheint nur im Trip, nicht im Ortsvergleich, weil dort keine Nacht-Stundentabelle existiert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
