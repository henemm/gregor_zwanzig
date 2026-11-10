---
spec_file: docs/specs/modules/fix_1831_danger_rot.md
spec_sha256: c460d377fe8afbd7ca89429cdd90b38ff5bba90d81df6f7218c1e8d9586fe0d9
spec_frozen_sha256: 085b51fec1bfe0eb48716e6ed7fd1ade64b436b3a8dd453438f529c004a91d67
---

# PO-Briefing: fix-1831-danger-rot

- **Spec:** docs/specs/modules/fix_1831_danger_rot.md
- **Issue:** #1831
- **Erstellt:** 2026-11-10

## Was gebaut wird

Der Löschen-Knopf erscheint überall im selben Rot, und die Design-Seite nennt den richtigen Kontrastwert.

## Definition of Done

Löschen-Knopf zeigt in Hell- und Dunkelmodus nur ein Rot, Schriftkontrast mindestens 4,5:1, Design-Seite nennt 6.63, auf Produktion ausgeliefert.

## Wie geprüft wird

Rechentests und zwei Browser-Tests belegen Farben und Kontrast; die Zahl auf der Design-Seite wird nur per Rechenskript und Sichtprüfung belegt.

## Kritische Anmerkungen

- E-Mails behalten das alte Rot; Web und Mail bleiben bewusst verschieden, Angleichen braucht ein eigenes Ticket.
- Im Dunkelmodus wird die Knopffläche neu getönt, Kontrast minimal schwächer (5.34 statt 5.79), weiterhin über Grenzwert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
