---
spec_file: docs/specs/modules/fix_2210_mail_renderfehler.md
spec_sha256: 4b26e012bfd0d9cf069af99c8e1a591c2256ba1872a6866e6970690427e58555
spec_frozen_sha256: a04d5c2fe8c92d8491e91f47ef21d5769840f7f85167884610e7ce756bdcb665
---

# PO-Briefing: fix-2210-mail-renderfehler

- **Spec:** docs/specs/modules/fix_2210_mail_renderfehler.md
- **Issue:** #2210
- **Erstellt:** 2026-11-01

## Was gebaut wird

Vier Darstellungsfehler in Mails werden behoben: deutscher Wochentag, lesbare Minus-Temperaturspannen, keine leere Stundentabelle, toter Code entfernt.

## Definition of Done

Deutsche Vergleichs-Mail zeigt „Montag, 02.11.2026", Frost-Spannen lauten „-12 bis -4°C", und bei abgewählten Metriken erscheint am Desktop keine Stundentabelle.

## Wie geprüft wird

Echte Renderaufrufe belegen alle zehn Kriterien; die Gewitter-Anzeige wird nicht geprüft, weil ihr Code entfernt wird.

## Kritische Anmerkungen

- Gewitter-„0 %" wird nicht repariert, sondern ungenutzter Code gelöscht; das Ticket verlangte eine Korrektur.
- Negative Spannen lauten künftig „-12 bis -4°C", auch in englischen Mails; Format ist Spec-Vorschlag, nicht vom PO entschieden.

## Freigabe-Frage

Darf der Gewitter-Punkt entfallen, weil nur ungenutzter Code gelöscht wird, und gilt „-12 bis -4°C" als gewünschtes Format?

## Ampel

Ampel: rot
