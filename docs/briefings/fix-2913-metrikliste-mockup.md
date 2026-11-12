---
spec_file: docs/specs/modules/fix_2913_metrikliste_mockup.md
spec_sha256: 8f3ab492f80f28b7306f529ea38d9feba2af4f2bb9c98b8a2d629e3187dc5f17
spec_frozen_sha256: a81935c44f8b85988982f293291d7775bd015b4e1ea999a3dab0dacdfe25ee35
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

Automatische Messungen bei mehreren Fensterbreiten in Deutsch und Englisch sowie Bildvergleich Mockup gegen Staging; Dunkelmodus wird nur auf Lesbarkeit geprüft.

## Kritische Anmerkungen

- Sichtweite in km statt m bleibt bewusst unbehoben (eigenes Ticket #2946).
- Dunkelmodus wird nicht gegen das Mockup abgenommen, nur auf Lesbarkeit.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
