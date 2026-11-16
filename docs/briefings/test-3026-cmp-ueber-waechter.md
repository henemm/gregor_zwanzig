---
spec_file: docs/specs/fast/test-3026-cmp-ueber-waechter.md
spec_sha256: 5342dec4b5c2afed282b283e34301ff48fa4defe6351971ecf8dc5221d73443c
spec_frozen_sha256: b0c887145aba4615262f7b176e5783cb0a8206371eccdedd9ff3e39a48594b91
---

# PO-Briefing: test-3026-cmp-ueber-waechter

- **Spec:** docs/specs/fast/test-3026-cmp-ueber-waechter.md
- **Issue:** #3026
- **Erstellt:** 2026-11-16

## Was gebaut wird

Ein neuer Absicherungs-Test stellt sicher, dass Alarme bei steigender oder fallender Tiefsttemperatur die richtige Richtung („über“ bzw. „unter“) tragen.

## Definition of Done

Der neue Test läuft grün, wird bei absichtlich eingebauter Verfälschung („über“ falsch geschrieben) rot, und kein Alarmtext ändert sich.

## Wie geprüft wird

Der Test prüft beide Richtungen am Beispiel Tiefsttemperatur; andere Metriken sind nicht betroffen, weil nur dieses Feld mehrdeutig ist.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
