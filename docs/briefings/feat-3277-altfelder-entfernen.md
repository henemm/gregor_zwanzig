---
spec_file: docs/specs/modules/feat_3277_altfelder_entfernen.md
spec_sha256: 7cedb4165491f693ddea82c51fb6d4188dbe1f524aa754e222515846a86aea0e
spec_frozen_sha256: fee3c6bdd02164923bf37a0843157f289f7a2c2259c72f929390ee7f2e8517e1
---

# PO-Briefing: feat-3277-altfelder-entfernen

- **Spec:** docs/specs/modules/feat_3277_altfelder_entfernen.md
- **Issue:** #3277
- **Erstellt:** 2026-11-25

## Was gebaut wird

Zehn alte, wirkungslose Einstellungsfelder werden aus dem Programm entfernt; Mails, Telegram und SMS bleiben für Nutzer unverändert.

## Definition of Done

Briefings aller vier Kanäle sind zeichengleich zu vorher, Speichern entfernt die Altfelder, und Staging sowie Produktion laufen ohne Prüffehler.

## Wie geprüft wird

Automatische Tests vergleichen alle vier Kanäle mit und ohne Altfelder und prüfen zwei Nutzer; Bestandsdaten und Bedienoberfläche werden nicht geprüft.

## Kritische Anmerkungen

- Das verlangte Bereinigungsskript fehlt hier: Datenlauf und Schließen von #3102 sind bewusst nach #3351 verschoben.
- Bestehende Altfelder bleiben auf der Platte, bis der Datenlauf läuft; sie sind wirkungslos.
- Zusätzlich zu den zwei genannten Feldern entfallen acht weitere, darunter der Ausblick-Schalter für Ortsvergleiche.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
