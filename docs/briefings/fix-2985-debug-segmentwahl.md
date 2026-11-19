---
spec_file: docs/specs/fast/fix-2985-debug-segmentwahl.md
spec_sha256: 32a30a0c8cda7b1b4287b9f35c8e26beedba21ffec47f4e27945ec6da8e7bbcd
spec_frozen_sha256: 1cf19e821e5b690d4c972f8ea860d667d3f5267b69b81a457447871277196ed7
---

# PO-Briefing: fix-2985-debug-segmentwahl

- **Spec:** docs/specs/fast/fix-2985-debug-segmentwahl.md
- **Issue:** #2985
- **Erstellt:** 2026-11-19

## Was gebaut wird

Die Test-Funktion für Radar-Alarme auf Staging wählt die Etappe mit demselben Baustein wie der echte Alarm, nicht mehr mit einer Kopie.

## Definition of Done

Die Test-Funktion wählt dieselbe Etappe wie der echte Alarm, einschliesslich Etappen nach Mitternacht, und kennt nur noch diese eine Auswahl.

## Wie geprüft wird

Neue Tests rufen die Auswahl mit echten Trips auf; eine gezielte Fälschung muss rot werden, die Live-Mail wird nicht geprüft.

## Kritische Anmerkungen

- Der im Ticket erwähnte Paritätstest wird nicht behandelt (entfällt oder bleibt); Folge gering, nur Aufräumfrage.
- Rückfall auf erste Etappe bleibt ein Sonderweg nur für Staging-Testdaten; dort bleibt eine kleine Restlogik bestehen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
