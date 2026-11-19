---
spec_file: docs/specs/modules/handler_hoehen_fixture.md
spec_sha256: 9e53070038d25fdbe4484c20b9a7cfcc65e73a2600f2511c10d2f8f31e95c667
spec_frozen_sha256: a91c6f536095f33845a3bfe3b84747db88f683afef4ba1668adbdf04106783ff
---

# PO-Briefing: feat-3158-hoehe-fixture

- **Spec:** docs/specs/modules/handler_hoehen_fixture.md
- **Issue:** #3158
- **Erstellt:** 2026-11-19

## Was gebaut wird

Die Tests der Ortssuche prüfen die Höhe künftig gegen einen lokalen Nachbau des Höhendienstes statt eine Ablehnung zu dulden.

## Definition of Done

Die drei Koordinaten-Tests prüfen die Höhe 1235, die Duldung ist entfernt, und jeder ungewollte Höhenabruf macht den Testlauf rot.

## Wie geprüft wird

Die Tests laufen durch den echten Ablauf mit lokalem Nachbau und prüfen Höhe, Koordinaten und Wiederherstellung der Netzsperre; die Produktion bleibt unverändert.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
