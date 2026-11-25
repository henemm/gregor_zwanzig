---
spec_file: docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md
spec_sha256: a82c1d7817af132440df7dabafa82b495120c9e543c6f175856f050063fd0f3f
spec_frozen_sha256: 163fb7b11b8179300b57d50ceb4f76de41edfea7175cf1badd0ed264c3c5bc5e
---

# PO-Briefing: rework-3036-uebergangsblock-aufloesen

- **Spec:** docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md
- **Issue:** #3036
- **Erstellt:** 2026-11-24

## Was gebaut wird

Der Rahmen „Vorübergehend hier“ verschwindet, und Kurz-Zusammenfassung sowie Großwetterlage bekommen je einen eigenen Schalter für Trip-Mails.

## Definition of Done

Auf Produktion lassen sich beide Blöcke ein- und ausschalten, die Mail folgt, Beispiel-Alarm und Pausieren bleiben bedienbar, kein Übergangsrahmen mehr.

## Wie geprüft wird

Automatische Tests und eine echt zugestellte Staging-Mail belegen Schalter, Speichern und Mail-Inhalt; Telegram, SMS und Kompakt-Mail folgen den Schaltern nicht.

## Kritische Anmerkungen

- Abweichung vom Ticket: Alt-Bausteine und die Anzeige „telegram_kurzform“ werden nicht gelöscht, sondern auf #3020 verschoben. Nutzer merken nichts davon.
- Telegram zeigt die Großwetterlage unabhängig vom neuen Schalter; als Hinweis dokumentiert, nicht gelöst.

## Freigabe-Frage

Darf das Löschen der Alt-Bausteine und der Anzeige „telegram_kurzform“ von diesem Issue auf #3020 verschoben werden?

## Ampel

Ampel: rot
