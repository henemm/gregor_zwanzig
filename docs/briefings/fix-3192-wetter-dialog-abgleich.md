---
spec_file: docs/specs/modules/fix_3192_wetter_dialog_abgleich.md
spec_sha256: 4d70151b4ce4d56431e080d8d04531bf66a75d2230f062060ffc34b50159dc4f
spec_frozen_sha256: eda63876813df696b89be1f0e599656ddd718b7459d8d4513c8a859243bb3e3b
---

# PO-Briefing: fix-3192-wetter-dialog-abgleich

- **Spec:** docs/specs/modules/fix_3192_wetter_dialog_abgleich.md
- **Issue:** #3192
- **Erstellt:** 2026-11-20

## Was gebaut wird

Der Abgleich prüft die Wetter-Dialoge auf der Datenlage des Mockups, und die dazugehörigen Besitzer-Einträge werden abgeräumt.

## Definition of Done

Der Staging-Abgleich in Deutsch und Englisch findet die Wetter-Dialog-Einträge, und kein Eintrag gehört mehr zu Ticket 3111.

## Wie geprüft wird

Automatische Tests und ein Staging-Lauf belegen Datenlage, Aufräumen und Speichern einer eigenen Vorlage; die Resteinträge werden nur begründet verschoben, nicht gemessen.

## Kritische Anmerkungen

- Abweichung: Das Ticket nennt nur #3189 und #3190 als Ziel; die Spec hängt Reste zusätzlich an #3151 und #3194 um.
- Mockup widerspricht sich; die Spec misst mit zwei Datensätzen (mit und ohne Abweichung) statt einer Mockup-Lage.
- Wie viele Einträge am Ende umgehängt statt abgeräumt sind, ist nicht festgelegt.

## Freigabe-Frage

Darf ein Teil der 156 Einträge statt abgeräumt an die Tickets #3151 und #3194 umgehängt werden?

## Ampel

Ampel: rot
