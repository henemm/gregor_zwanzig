---
spec_file: docs/specs/modules/fix_2913_metrikliste_mockup.md
spec_sha256: 6a9b4de9ea350abe198ade26f4bfcdae99c28867342d3796bd49be36fb18943d
spec_frozen_sha256: e1e197ac1eb8de626c40b3104a50a2c90c3eeef32eca463b4c6a7fe82f9ae180
---

# PO-Briefing: fix-2913-metrikliste-mockup

- **Spec:** docs/specs/modules/fix_2913_metrikliste_mockup.md
- **Issue:** #2913
- **Erstellt:** 2026-11-12

## Was gebaut wird

Die Metrik-Liste im Reiter Wetter sieht bei Trip und Orts-Vergleich wieder aus wie das freigegebene Mockup.

## Definition of Done

Auf Staging stimmen Spaltenbreiten, Zeilenhöhen, Untertitel, grüne Angabe und helle „Alarm ab“-Stufe bei allen Breiten mit dem Mockup überein; Soll/Ist-Bild liegt vor.

## Wie geprüft wird

Automatische Messungen bei mehreren Fensterbreiten in Deutsch und Englisch sowie Bildvergleich Mockup gegen Staging; Dunkelmodus nur auf Lesbarkeit.

## Kritische Anmerkungen

- Karte ist wegen der Seitenleiste 1012 statt 1068 px breit (Mockup ohne Seitenleiste); unvermeidbar, Seitenleiste bleibt.
- Sichtweite in km statt m bleibt bewusst unbehoben (Ticket #2946).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
