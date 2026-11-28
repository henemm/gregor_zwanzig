---
spec_file: docs/specs/modules/fix_3241_elementliste_en_metrikzeile_chips.md
spec_sha256: e1d70b1f3f3c16a8110e0299e46db443f974eff921f4f4808382b522429c9cb4
spec_frozen_sha256: acfa5be43783c5e8a65ebb4c2750dc623f3d733ffabcb37cbcd81aa303455fe5
---

# PO-Briefing: fix-3241-en-chips-abgleich

- **Spec:** docs/specs/modules/fix_3241_elementliste_en_metrikzeile_chips.md
- **Issue:** #3241
- **Erstellt:** 2026-11-28

## Was gebaut wird

Der englische Prüfabgleich im Reiter Wetter erkennt Metrik-Chips und Einheit-Hinweiszeilen einzeln, sodass die Sammel-Ausnahmen entfallen.

## Definition of Done

Der englische Staging-Abgleich findet die Chips und Hinweiszeilen, der deutsche Lauf bleibt unverändert, und keine Ausnahme verweist mehr auf dieses Ticket.

## Wie geprüft wird

Automatische Tests prüfen Zuordnung und Chip-Bewertung gegen echte Katalogdaten; der echte Konto-Nachweis erfolgt erst im Staging-Lauf, nicht in den Tests.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
