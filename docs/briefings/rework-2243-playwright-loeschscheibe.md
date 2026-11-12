---
spec_file: docs/specs/modules/rework_2243_playwright_loeschscheibe.md
spec_sha256: a5e6fcb350c141fdd1e30b8c029e0e2d0ed7dceaf5c042da7a46ebbd73159afd
spec_frozen_sha256: ca2905e2b24274657cc40bc72d48bf0fbf316731f87b9ef12cbeb0defd244c18
---

# PO-Briefing: rework-2243-playwright-loeschscheibe

- **Spec:** docs/specs/modules/rework_2243_playwright_loeschscheibe.md
- **Issue:** #2243
- **Erstellt:** 2026-11-12

## Was gebaut wird

Veraltete Browser-Tests, toter Hilfscode und verwaiste Testkonfigurationen werden gelöscht; ein neuer Wächter verhindert fest verdrahtete Serverpfade.

## Definition of Done

Die sieben toten Testdateien und drei verwaisten Konfigurationen sind weg, die übrigen Tests laufen ohne Ladefehler, die automatische Prüfung bleibt grün.

## Wie geprüft wird

Neue Tests belegen Löschung, Sortierung der Etappen und den Pfadwächter samt Gegenprobe; Produktverhalten wird nicht berührt oder geprüft.

## Kritische Anmerkungen

- Abweichung: Vier Layout-Reiter-Tests werden behalten statt gelöscht; ihre Zusicherungen wären sonst verloren.
- Abweichung: Konfigurationen werden nur gelöscht, wenn verwaist; die verlangte Zusammenlegung auf zwei Configs folgt später als eigenes Ticket.

## Freigabe-Frage

Bist du einverstanden, dass die Layout-Reiter-Tests bleiben und die Config-Zusammenlegung in ein Folgeticket wandert?

## Ampel

Ampel: rot
