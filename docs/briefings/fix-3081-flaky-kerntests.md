---
spec_file: docs/specs/modules/fix_3081_flaky_kerntests.md
spec_sha256: dd6429d0ab4b0a9a2cdcc997dfab267ddd808fe46f72eb2bf78fae9edccfc62d
spec_frozen_sha256: 61a02a417bd0c08b906de13147fe4d74179cd951357014fb1e948887dd70d80f
---

# PO-Briefing: fix-3081-flaky-kerntests

- **Spec:** docs/specs/modules/fix_3081_flaky_kerntests.md
- **Issue:** #3081
- **Erstellt:** 2026-11-16

## Was gebaut wird

Zwei wackelnde Kern-Tests werden stabilisiert, damit die automatische Prüfung nicht mehr zufällig rot wird.

## Definition of Done

Je 10 Läufe einzeln, im Batch und gemischt grün, Zusicherungen unverändert scharf, Nachweis als Kommentar im Ticket.

## Wie geprüft wird

Wiederholte Testläufe und gezielte Verfälschung belegen Stabilität und Schärfe; ob die ursprüngliche Alarm-Test-Störung behoben ist, belegen sie nicht.

## Kritische Anmerkungen

- Alarm-Test: Ursache nicht gefunden, laut Ticket verlangt. Spec liefert nur Vorsichtsmaßnahme plus bessere Fehlermeldung, ohne Beweis der Behebung.
- Zweiter Radar-Flake (gleichzeitige Nutzer) nicht reproduziert; kein Fix, nur Beobachtung.
- Neues Ticket für Nebenbefund: Frist-Abbruch greift in Produktion praktisch nie.

## Freigabe-Frage

Genügt Ihnen für den Alarm-Test Vorsorge plus bessere Fehlermeldung, obwohl die Ursache ungeklärt bleibt?

## Ampel

Ampel: rot
