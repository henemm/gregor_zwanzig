---
spec_file: docs/specs/fast/fix-2973-hub-anker-warten.md
spec_sha256: d6c502de77bafe9b561d0de9361a28c4a2b8f5acbd0ab8962586b3c7677f8ed4
spec_frozen_sha256: 2fe453944ad8e782618ee20f373637e2c86cdb20688dde6bac77fd9eb1d96178
---

# PO-Briefing: fix-2973-hub-anker-warten

- **Spec:** docs/specs/fast/fix-2973-hub-anker-warten.md
- **Issue:** #2973
- **Erstellt:** 2026-11-19

## Was gebaut wird

Der Abnahme-Lauf des Elementlisten-Abgleichs wartet bei langsamer Staging-Antwort bis zu fünf Sekunden auf die Seitenmarker, statt sofort rot zu werden.

## Definition of Done

Der Abnahme-Lauf auf Staging läuft grün durch; fehlen die Marker auch nach dem Warten, bleibt er weiterhin rot.

## Wie geprüft wird

Tests belegen Warteverhalten, sofortigen Erfolg und weiterhin rotes Ergebnis; ob die Verdrahtung greift, wird nur über Code-Prüfung und Staging-Lauf gesehen.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
