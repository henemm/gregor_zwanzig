---
spec_file: docs/specs/modules/fix_1670_mail_formatdetails.md
spec_sha256: 7d889404dbf0209d4933f40ab2e6c34df4ecc56691927c74a5edc02ecfbcd14d
spec_frozen_sha256: 0a6c025a0a346c31c8ac0df863d527f21360ddb741e2f539efc05449d208250d
---

# PO-Briefing: fix-1670-mail-formatdetails

- **Spec:** docs/specs/modules/fix_1670_mail_formatdetails.md
- **Issue:** #1670
- **Erstellt:** 2026-11-02

## Was gebaut wird

Pillen in der Trip-Mail behalten mobil das Leerzeichen vor der Uhrzeit, und alle Mails zeigen für fehlende Werte denselben Strich.

## Definition of Done

Auf dem Handy steht "Max 16:00" mit Leerzeichen, fehlende Werte zeigen überall "–", und Wind ohne Daten zeigt nicht mehr "0".

## Wie geprüft wird

Automatische Tests prüfen Pillen-Aufbau, Striche und Wind-Anzeige; wie es im echten Handy-Mailprogramm aussieht, belegt nur dein Screenshot.

## Kritische Anmerkungen

- Zusatz: Wind ohne Daten zeigt künftig "–" statt "0"; das verlangte das Ticket nicht.
- Der neue Strich ändert auch Compare-Telegram und Compare-Klartext (vorher "—"); du hast das entschieden.
- C5-04, 07, 66 werden ohne Änderung abgehakt; dafür gibt es keinen eigenen Test.

## Freigabe-Frage

Soll Wind ohne Daten wirklich "–" statt "0" zeigen, obwohl das Ticket es nicht verlangt hat?

## Ampel

Ampel: rot
