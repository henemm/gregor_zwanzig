---
spec_file: docs/specs/modules/fix_2464_brightsky_konvektions_sidecar.md
spec_sha256: 915440550808a9f6f2dea39225925ea3fba62ce92f1adc6b19f6ef4423c9f15f
---

# PO-Briefing: fix-2464-brightsky-konvektion

- **Spec:** docs/specs/modules/fix_2464_brightsky_konvektions_sidecar.md
- **Issue:** #2464
- **Erstellt:** 2026-09-30

## Was gebaut wird

Der Radar-Alarm erkennt an Orten in Deutschland erstmals Gewitter und Hagel, wie schon in Österreich und auf Korsika.

## Definition of Done

Für einen deutschen Ort zeigt der Radar bei Gewitter-Signal Gewitter oder Hagel; fällt die Prüfung aus, steht „Storm check not available." in allen vier Kanälen.

## Wie geprüft wird

Netzfreie Tests mit aufgezeichneten Beispieldaten und fünf Gegenproben; echte Daten nur einmal auf Staging, das Gewitter selbst nur über nachgestellte Wetterdaten.

## Kritische Anmerkungen

- Das Gewitter-Signal stammt aus dem Wettermodell, nicht aus dem Radarbild; es erscheint trotzdem als Radar-Beobachtung. Falschmeldungen sind möglich.
- Abweichung vom Ticket: Ein Zwischenspeicher-Fehler wird zusätzlich behoben, das ändert auch Österreich und Korsika; jede deutsche Radarabfrage kostet einen Open-Meteo-Aufruf mehr.
- Erstmals möglich: Gewitter-Alarme und Akut-Meldungen in Deutschland; Tests belegen nur eine Beispiel-Ausgabe, nicht jeden Kanal einzeln.

## Freigabe-Frage

Sollen Gewitter- und Hagel-Alarme in Deutschland mit Zusatzaufruf und Zwischenspeicher-Korrektur für alle Regionen jetzt starten?
