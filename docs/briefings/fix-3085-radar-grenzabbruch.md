---
spec_file: docs/specs/modules/fix_3085_radar_grenzabbruch.md
spec_sha256: 535d99fcfdd679abf2181b8be8e1b142ba3c7c6dda4fb83a2dbc6a987ab5859a
spec_frozen_sha256: 0ec576882b37d865aadd33f122147018e58910e7ab87e7f89535a50cc250295c
---

# PO-Briefing: fix-3085-radar-grenzabbruch

- **Spec:** docs/specs/modules/fix_3085_radar_grenzabbruch.md
- **Issue:** #3085
- **Erstellt:** 2026-11-17

## Was gebaut wird

Läuft beim Regenradar-Alarm die Zeit ab, wird die Einheit abgebrochen statt mit Lücken ausgewertet.

## Definition of Done

Bei Zeitablauf löst keine Einheit Alarm, Eintrag oder Stempel aus, kommt im nächsten Lauf zuerst dran, und der Lauf meldet teilweise.

## Wie geprüft wird

Automatische Tests mit echten Abläufen prüfen Abbruch, Reihenfolge und unveränderte Normalfälle; langsame Quellen im Livebetrieb bleiben ungeprüft.

## Kritische Anmerkungen

- Beim Ortsvergleich entfällt bei Zeitüberschreitung der bisherige Ausfall-Eintrag; zwei bestehende Tests werden bewusst umgedreht.
- Dauerhaft langsame Einheit bricht jeden Lauf ab und bleibt vorn; Spec nennt dies als bekannte Restwirkung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
