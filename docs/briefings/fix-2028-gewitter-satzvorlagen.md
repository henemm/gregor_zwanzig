---
spec_file: docs/specs/modules/fix_2028_gewitter_satzvorlagen.md
spec_sha256: 892add593a11e28ab99fc9c97ba6ebc52725d351794040165c89e6ce372d92ee
---

# PO-Briefing: fix-2028-gewitter-satzvorlagen

- **Spec:** docs/specs/modules/fix_2028_gewitter_satzvorlagen.md
- **Issue:** #2028
- **Erstellt:** 2026-09-24

## Was gebaut wird

Die Warntexte für Gewitter werden intern vereinheitlicht, ohne dass sich der Wortlaut für Wanderer ändert.

## Definition of Done

Der automatische Gewitter-Text-Wächter meldet die drei bekannten Altlasten nicht mehr, der Wortlaut bleibt für Nutzer gleich.

## Wie geprüft wird

Automatisierte Tests sichern gleichen Wortlaut und Rückdreh-Erkennung ab, prüfen aber nicht die beiden Bauwege mit identischem Input gegeneinander.

## Kritische Anmerkungen

- Die Spec entscheidet die vom Ticket als klärungsbedürftig markierte Nachtwort-Frage selbst, ohne erneute PO-Rückfrage.
- Falls beim Umbau eine vierte Fundstelle auftaucht, wächst der Auftrag automatisch mit, ohne erneute Rückfrage.

## Freigabe-Frage

Sollen die drei doppelten Gewitter-Textstellen zusammengeführt werden, obwohl die interne Nachtwort-Entscheidung nicht erneut mit dir abgestimmt wurde?
