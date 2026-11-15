---
spec_file: docs/specs/modules/fix_3015_temp_spanne_en.md
spec_sha256: b84d0abfc3e8b4f27463e98d7867b89f3ebdd320d0c0ff99d2e434c6cf9bcd89
spec_frozen_sha256: edbd4cbad6fdb54528e773d22a3e77b58810ea97ffe8f60c5101e6860da19649
---

# PO-Briefing: fix-3015-temp-spanne-en

- **Spec:** docs/specs/modules/fix_3015_temp_spanne_en.md
- **Issue:** #3015
- **Erstellt:** 2026-11-15

## Was gebaut wird

Minus-Temperaturspannen erscheinen in deutschen und englischen Mails sprachneutral als "-3 – 0°C", ohne Wort "bis".

## Definition of Done

Echte Briefing- und Vergleichs-Mails zeigen in beiden Sprachen "-3 – 0°C", Plusgrade bleiben "8–14°C", und die automatischen Prüfungen sind grün.

## Wie geprüft wird

Tests rendern echte Mails und Kurzzusammenfassungen in Deutsch und Englisch; nicht geprüft wird der separate Textbericht, der "bis" behält.

## Kritische Anmerkungen

- Zusatz: Bei gleichen gerundeten Werten zeigt die Kurzzusammenfassung nun "5°C" statt "5–5°C"; folgt aus der gemeinsamen Formel.
- Der Textbericht schreibt weiter "bis" bei Minusgraden, also nicht überall einheitlich.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
