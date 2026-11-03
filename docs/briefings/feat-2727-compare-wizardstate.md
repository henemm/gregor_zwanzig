---
spec_file: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md
spec_sha256: 3e1de140c50ea80596da658fd9cfe55c245360a471ab76cfdb72ae22e073fa3c
spec_frozen_sha256: 41af9a010147ae0d02922b2447ee2831895ce980cc07774e7ae93405e8506a3e
---

# PO-Briefing: feat-2727-compare-wizardstate

- **Spec:** docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md
- **Issue:** #2727
- **Erstellt:** 2026-11-01

## Was gebaut wird

Ortsvergleich-Anlegen und -Hub verlieren den gemeinsamen Zwischenspeicher; für Nutzer ändert sich nichts, ein Wächter verhindert die Rückkehr.

## Definition of Done

Der alte Zwischenspeicher ist gelöscht, Anlegen und Hub speichern wie zuvor, und alle automatischen Prüfungen samt Staging-Paritätstest sind grün.

## Wie geprüft wird

Tests belegen unverändertes Anlegen, Speichern, Konflikte und Datenerhalt sowie den Wächter; Aussehen im Browser prüft nur der Staging-Lauf.

## Kritische Anmerkungen

- Der Hub behält einen eigenen lokalen Zwischenstand; die vom Ticket verlangte Trip-Gleichheit ist nicht erreicht, Spec verschiebt sie auf ein Folgevorhaben.
- Fehler beim Anlegen bleiben für Nutzer unsichtbar; nur im Sammel-Issue vermerkt, nicht behoben.

## Freigabe-Frage

Akzeptieren Sie, dass der Hub vorerst einen eigenen Zwischenstand behält und die volle Trip-Gleichheit als Folgeticket kommt?

## Ampel

Ampel: rot
