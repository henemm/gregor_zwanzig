---
spec_file: docs/specs/modules/rework_2988_ampel_ableitung.md
spec_sha256: fa0ce10ceac58458411ab2ab1f8644ca590cf3cbc4a1a567c4e9006d2f471812
spec_frozen_sha256: c74d4aa93fbff9ae532a4983df12d229c425d56e2ce8ecbee12dfe8c39df82af
---

# PO-Briefing: rework-2988-ampel-ableitung

- **Spec:** docs/specs/modules/rework_2988_ampel_ableitung.md
- **Issue:** #2988
- **Erstellt:** 2026-11-25

## Was gebaut wird

Die Wetter-Ampel wird nur noch im Server berechnet, die Oberfläche zeigt das Ergebnis an, sichtbar ändert sich nichts.

## Definition of Done

Reiter Wetter, Zähler, Übersichten und gespeicherte Daten verhalten sich wie vorher, im Frontend steckt keine zweite Ampel-Rechnung mehr, Produktion läuft.

## Wie geprüft wird

Automatische Tests vergleichen alle Ergebnisse mit Referenzzahlen aus dem alten Stand; Staging-Tests prüfen Laden, Fehlerfall und Konflikt, nicht aber Optik.

## Kritische Anmerkungen

- Das Editier-Delta (Abweichungszähler) bleibt bewusst im Frontend, weil der Zähler sofort reagieren muss; Issue-Text verlangt mehr.
- Gespeicherte eigene Vorlagen behalten künftig Windrichtungs-Einstellungen; bisher gingen sie verloren (kleine ungefragte Verbesserung).
- Öffnen des Reiters braucht nun erreichbaren Server, sonst erscheint „Erneut laden".

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
