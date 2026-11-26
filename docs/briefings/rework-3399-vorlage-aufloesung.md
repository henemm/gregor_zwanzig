---
spec_file: docs/specs/modules/rework_3399_vorlage_aufloesung.md
spec_sha256: 21902ac3303f08d842b2d647b5c1b5106722dceef33b16c85477ba039c996d29
spec_frozen_sha256: 695acb8868ed99f358d9dc161d10bf854d1b4613e70bce6a1a931def639e5c22
---

# PO-Briefing: rework-3399-vorlage-aufloesung

- **Spec:** docs/specs/modules/rework_3399_vorlage_aufloesung.md
- **Issue:** #3399
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die Wetter-Vorlage eines Trips oder Ortsvergleichs bestimmt nur noch der Server; die Oberfläche übernimmt sie.

## Definition of Done

Alarme, Karten, Listen und Kopie-Anlegen zeigen die Server-Vorlage, die alte Rangfolge ist gelöscht, Produktion läuft mit bestandenem Selftest.

## Wie geprüft wird

Tests nutzen die echte Server-Auflösung für alle neun Kriterien; Live-Prüfung gegen Staging gibt es nur für Alarme, Karten und Kopie.

## Kritische Anmerkungen

- Bis zur Serverantwort, bei Fehler und offline steht "—" statt eines Vorlagennamens; kurzes Aufblitzen beim Öffnen.
- Ortsvergleiche mit gesetztem Vorlagennamen zeigen künftig die Server-Vorlage; die alte Anzeige ignorierte diesen Namen.
- Lieferung in fünf Teilen; Issue schließt erst nach dem letzten.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
