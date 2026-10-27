---
spec_file: docs/specs/modules/fix_2615_befehle_pausierte_vergleiche.md
spec_sha256: a06a31b21847d7bf0b5fb9c1b78aea9bdac323d183bae07de9a87c48f13e4f0f
spec_frozen_sha256: 55601e74197cf4ed94331e53dace2a9b151c9374468e4648166ad83459541aa3
---

# PO-Briefing: fix-2615-befehle-pausierte-vergleiche

- **Spec:** docs/specs/modules/fix_2615_befehle_pausierte_vergleiche.md
- **Issue:** #2615
- **Erstellt:** 2026-10-25

## Was gebaut wird

Wetterbefehle heute, morgen und report ignorieren pausierte Ortsvergleiche, und gekürzte Premium-SMS-Rückfragen bleiben unterscheidbar und beantwortbar.

## Definition of Done

Bei einem aktiven und mehreren pausierten Ortsvergleichen antwortet heute ohne Rückfrage; pause und weiter fragen weiterhin nach.

## Wie geprüft wird

Automatische Tests ohne Netz prüfen Auflösung, zwei Nutzer und Rückfrage-Antwort-Kreislauf; echter Versand über Telegram oder Premium-SMS wird dort nicht nachgewiesen.

## Kritische Anmerkungen

- Zusatz: Antworten mit gekürztem Namen werden künftig per Anfangsbuchstaben erkannt, auch bei E-Mail-Betreff; nicht verlangt, Fehlzuordnungsrisiko.
- Abweichung: Eindeutigkeit geht vor 160 Zeichen; Premium-SMS-Rückfragen können länger, mehrteilig und teurer werden. Kein Durchnummerieren.
- Gleich benannte Ortsvergleiche bleiben unterscheidungslos; Abhilfe nur durch Umbenennen, dafür gibt es keinen Test.

## Freigabe-Frage

Sollen heute, morgen und report pausierte Ortsvergleiche ignorieren und gekürzte Namen in Antworten erkannt werden?
