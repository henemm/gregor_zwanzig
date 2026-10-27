---
spec_file: docs/specs/modules/fix_2216_ort_loeschen_sperre.md
spec_sha256: 6d799b4b2857397edf1af1fb8e30937e57d853aea8c40121d7ac094560578372
---

# PO-Briefing: fix-2216-ort-loeschen-sperre

- **Spec:** docs/specs/modules/fix_2216_ort_loeschen_sperre.md
- **Issue:** #2216
- **Erstellt:** 2026-10-08

## Was gebaut wird

Ein Ort, der in einem Ortsvergleich steckt, lässt sich nicht löschen; die App nennt die betroffenen Ortsvergleiche.

## Definition of Done

Löschversuch zeigt die nutzenden Ortsvergleiche und der Ort bleibt; andere Orte löschen wie bisher; Versand nennt fehlende Orte verständlich.

## Wie geprüft wird

Automatische Tests prüfen Sperre, Nutzertrennung und Versandmeldung; Oberfläche wird auf Staging geprüft, Mail-Inhalt und gleichzeitiges Speichern nicht.

## Kritische Anmerkungen

- Fehlen nur einzelne Orte, läuft der Versand weiter; Hinweis nur in App und Log, nicht in der Mail.
- Gleichzeitiges Speichern und Löschen kann weiter einen verwaisten Ortsvergleich erzeugen; bewusst ungelöst.
- Bereits verwaiste Ortsvergleiche bleiben unrepariert.

## Freigabe-Frage

Soll das Löschen benutzter Orte gesperrt werden, trotz fehlendem Mail-Hinweis und Restrisiko?
