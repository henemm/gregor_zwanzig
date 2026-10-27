---
spec_file: docs/specs/modules/feat_2050_sz12_fehlende_vergleichsbasis.md
spec_sha256: ae10cffe896235390d5455f6fe40c94cca600fc6cd2194a7802c65c18ac9329f
---

# PO-Briefing: feat-2050-sz12-fehlende-vergleichsbasis

- **Spec:** docs/specs/modules/feat_2050_sz12_fehlende_vergleichsbasis.md
- **Issue:** #2050 (Szenario 12)
- **Erstellt:** 2026-10-01

## Was gebaut wird

Trips ohne gültige Vergleichsbasis hinterlassen im Alarmprotokoll einen benannten Grund statt stillem Nichts.

## Definition of Done

Jeder Trip oder Ortsvergleich ohne Vergleichsbasis erzeugt täglich einen Protokolleintrag, sichtbar im nächsten E-Mail-Briefing.

## Wie geprüft wird

Szenario-Tests über echte Prüfläufe belegen Eintrag, Einmaligkeit pro Tag und Hinweistext; Telegram und SMS bleiben ungeprüft.

## Kritische Anmerkungen

- Hinweis nur im E-Mail-Briefing, nicht Telegram/SMS — Spannung zu gleichrangigen Kanälen; bewusst ausgeklammert.
- Ortsvergleich ist mitgebaut, obwohl das Ticket nur Trips nennt: mehr Umfang im zentralen Alarmlauf.
- Ohne Vergleichsbasis wird weiterhin nichts geprüft; der Nutzer erfährt es erst im nächsten Briefing.

## Freigabe-Frage

Genügt es, dass fehlende Vergleichsbasis nur protokolliert und im Briefing gemeldet wird, statt sofort zu alarmieren?
