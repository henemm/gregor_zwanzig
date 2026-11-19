---
spec_file: docs/specs/modules/feat_3101_ein_vokabular.md
spec_sha256: 4aed78b02cd963d9bbc8a65e0ab92439ac2093fbd8310f4e6043afd5c97a62d6
spec_frozen_sha256: ee9102ae07480d1eaa33b2860f3b0d387672a09623ea37c2a7a35e1f5d04dceb
---

# PO-Briefing: feat-3101-ein-vokabular

- **Spec:** docs/specs/modules/feat_3101_ein_vokabular.md
- **Issue:** #3101
- **Erstellt:** 2026-11-18

## Was gebaut wird

Die Orte-Ausgaben sprechen intern dieselbe Sprache wie Ausblick und Stundenverlauf; Mail, Telegram und SMS bleiben für Nutzer unverändert.

## Definition of Done

Alle vier Kanäle liefern Zeichen für Zeichen dieselbe Ausgabe wie vorher, geprüft an den Vergleichsdateien und an einer echt zugestellten Staging-Mail.

## Wie geprüft wird

Automatische Tests vergleichen jede Ausgabe mit den gespeicherten Vergleichsdateien, Tabelle und Zwei-Nutzer-Trennung; die Staging-Mail wird beim Ausliefern geprüft.

## Kritische Anmerkungen

- Alarm-Pfad behält bewusst seine eigene Abbildung; ein zweites Vokabular bleibt dort bis zu einem späteren Ticket bestehen.
- Bau wartet auf Auslieferung des offenen Nachbar-Pakets (B1b), sonst drohen Konflikte; reine Reihenfolge, keine Entscheidung nötig.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
