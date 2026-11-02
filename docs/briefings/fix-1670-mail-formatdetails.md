---
spec_file: docs/specs/modules/fix_1670_mail_formatdetails.md
spec_sha256: fea7063c291d204707346d6832c20879ac2f59916cd288a0be5684b2c210e7cc
spec_frozen_sha256: 726679fa9ebef6bf1a5389867dd5f1dfbd5d259a7324e5ade187c606506d7505
---

# PO-Briefing: fix-1670-mail-formatdetails

- **Spec:** docs/specs/modules/fix_1670_mail_formatdetails.md
- **Issue:** #1670
- **Erstellt:** 2026-11-02

## Was gebaut wird

Pillen in der Trip-Mail behalten mobil das Leerzeichen vor der Uhrzeit, und die Vergleichs-Mail nutzt überall denselben Strich.

## Definition of Done

Auf dem Handy steht "Max 16:00" mit Leerzeichen, die Vergleichs-Mail zeigt nur noch "–" für fehlende Werte, und Wind ohne Daten zeigt nicht "0".

## Wie geprüft wird

Automatische Tests prüfen Pillen-Aufbau, Striche und Wind-Anzeige; ob es im echten Handy-Mailprogramm gut aussieht, belegt nur dein Screenshot.

## Kritische Anmerkungen

- Zusatz: Wind ohne Daten zeigt künftig "–" statt "0". Das hat das Ticket nicht verlangt.
- Drei Ticket-Punkte (C5-04, 07, 66) werden ohne Änderung abgehakt; AC-7 hat keinen eigenen Test.
- Mobile Wirkung des Pillen-Fixes ist nicht automatisch prüfbar.

## Freigabe-Frage

Soll Wind ohne Daten wirklich "–" statt "0" zeigen, und sind die drei Punkte ohne Änderung abgehakt in Ordnung?

## Ampel

Ampel: rot
