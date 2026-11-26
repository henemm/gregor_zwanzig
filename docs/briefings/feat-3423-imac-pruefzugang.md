---
spec_file: docs/specs/modules/e2e_verify_imac_pruefzugang.md
spec_sha256: ee9cfeeefda8a92fb8f491d290d8ce1549fa978121e62a921c46add02b68536b
spec_frozen_sha256: 66556d6b69ce03a6231f0eed0d663d2e9c9fed817f4cdf806a98900f4e396fd2
---

# PO-Briefing: feat-3423-imac-pruefzugang

- **Spec:** docs/specs/modules/e2e_verify_imac_pruefzugang.md
- **Issue:** #3423
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die Abnahme-Anleitung für den iMac nutzt nur noch die fünf festen Prüfbefehle statt freier Serverbefehle.

## Definition of Done

Die Anleitung ordnet jedem Abnahmeschritt einen festen Prüfbefehl zu, ohne gesperrte Befehlsformen, und das Betriebshandbuch nennt denselben Weg.

## Wie geprüft wird

Automatische Textprüfungen weisen nach, dass die Anleitung nur erlaubte Befehle enthält; ob der iMac damit wirklich abnimmt, zeigt nur ein echtes Ticket.

## Kritische Anmerkungen

- Der geforderte echte Ticket-Durchlauf vom iMac fehlt noch; das Ticket bleibt offen, die zwei Sperr-Tickets werden erst danach geschlossen.
- Die Prüfungen lesen nur den Anleitungstext; die Sperre selbst wird nicht getestet.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
