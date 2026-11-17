---
spec_file: docs/specs/modules/feat_2984_regionszeile_ortsformatierer.md
spec_sha256: 8814e59fd7162af1ddcf403137b85ab3abf8ac3a264f5eba148767b2f91b359c
spec_frozen_sha256: 0dfa098d247d7ed388ffc2ff66b0374f95bab0169bd1a0149b565f9737210943
---

# PO-Briefing: feat-2984-regionszeile-ortsformatierer

- **Spec:** docs/specs/modules/feat_2984_regionszeile_ortsformatierer.md
- **Issue:** #2984
- **Erstellt:** 2026-11-17

## Was gebaut wird

Bei amtlichen Warnungen nennt jede Zeile derselben Nachricht denselben Ort, etwa „km 12-20" statt teils „Segment 3".

## Definition of Done

Ein echt zugestellter Trip-Alarm mit amtlicher Warnung zeigt in Kopf, Ortsangabe und Klartext/Telegram überall dieselbe Angabe; SMS und Fälle ohne Kilometerwert bleiben unverändert.

## Wie geprüft wird

Automatische Tests vergleichen alle Zeilen für Kilometer, Segment, Sonderkennung, leer, Deutsch und Englisch; nicht geprüft wird die Optik auf echten Geräten.

## Kritische Anmerkungen

- Zusatz gegenüber der Regionszeile: Der Orts-Chip der HTML-Warnkarte ändert sich ebenfalls (AC-9); folgt der Entscheidung #2036.
- Ursprungsanfrage nur über den Kontext-Auszug gelesen, Issue-Text selbst war nicht abrufbar.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
