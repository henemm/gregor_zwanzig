---
spec_file: docs/specs/modules/i18n_p13_ratsche_renderer_2783.md
spec_sha256: b7f9ddefbda834691b1aab86e948c77a94cbe68d66a19d73957dbb2bbcbd1c53
spec_frozen_sha256: 784ae22d687c26e043625503cd889312e1b503b795a631d3284ac51a6bc5d35f
---

# PO-Briefing: i18n-2783-ratsche-renderer

- **Spec:** docs/specs/modules/i18n_p13_ratsche_renderer_2783.md
- **Issue:** #2783
- **Erstellt:** 2026-11-15

## Was gebaut wird

Die letzten 17 fest eingebauten deutschen Texte im Berichts-Code werden markiert oder entfernt, sodass die Sprachprüfung leer ist.

## Definition of Done

Die Sprachprüfung meldet keine offenen Funde, Berichte und Alarme sehen unverändert aus, Staging-Testmails sind geprüft und grün.

## Wie geprüft wird

Bestehende Vergleichstests und Staging-Testmails belegen unveränderte Ausgabe; nicht belegt wird, dass der entfernte Highlights-Code nie sichtbar war.

## Kritische Anmerkungen

- Abweichung: Das Ticket verlangt Übersetzung der Highlights-Texte; die Spec löscht den Code stattdessen, weil er nie angezeigt wird.
- Eine unsichtbare Zeile entfällt in jeder Mail; dafür werden etwa zwölf Referenzdateien angepasst.

## Freigabe-Frage

Darf der nie angezeigte Highlights-Code gelöscht statt übersetzt werden, obwohl das Ticket Übersetzung vorsieht?

## Ampel

Ampel: rot
