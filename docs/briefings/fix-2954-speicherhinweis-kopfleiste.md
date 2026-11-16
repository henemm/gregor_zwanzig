---
spec_file: docs/specs/modules/fix_2954_speicherhinweis_kopfleiste.md
spec_sha256: b2c5925d1c15e2a0a923ebaccd421c52ea17a30f9c49ce5546bc785c099d8cab
spec_frozen_sha256: 0ca0079bc6b45d62aea0a744a6a8662db3455b42e383015abd425c0e1dbabbc2
---

# PO-Briefing: fix-2954-speicherhinweis-kopfleiste

- **Spec:** docs/specs/modules/fix_2954_speicherhinweis_kopfleiste.md
- **Issue:** #2954
- **Erstellt:** 2026-11-15

## Was gebaut wird

Das „Gespeichert"-Feld wandert als Text in die Kopfleiste und überdeckt nichts mehr im Inhalt.

## Definition of Done

Nach dem Speichern erscheint „Gespeichert" links vom Menü, verschwindet nach 5 Sekunden, und kein Bedienelement ist bei 390, 1024, 1280 Pixel mehr verdeckt.

## Wie geprüft wird

Automatische Browser-Tests prüfen Position, Farbe, Zeitablauf, Verdeckung und Kontrast für Trip und Orte; keine Prüfung durch Sie nötig.

## Kritische Anmerkungen

- Abweichung vom Ticket: Fehler und Konflikt verschwinden nicht nach 5 Sekunden, sondern bleiben stehen, damit ein Speicherfehler nicht unbemerkt bleibt.
- Zusatz: Beim Öffnen einer Seite steht noch kein „Gespeichert"; der Text erscheint erst nach echtem Speichern.

## Freigabe-Frage

Soll ein Speicherfehler stehen bleiben, bis er behoben ist, statt wie im Ticket nach 5 Sekunden zu verschwinden?

## Ampel

Ampel: rot
