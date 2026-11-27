---
spec_file: docs/specs/fast/fix-3463-test-alarm-kanaele.md
spec_sha256: 5073041ae1f4125be4c8fb90e7bfefeb1c70d8bbd7f13212f5b155d22489550d
spec_frozen_sha256: a06fd5c895fc729dbb6b8f50b223f2a05de6769b5d44a8eb7f190ce271f76d4a
---

# PO-Briefing: fix-3463-test-alarm-kanaele

- **Spec:** docs/specs/fast/fix-3463-test-alarm-kanaele.md
- **Issue:** #3463
- **Erstellt:** 2026-11-27

## Was gebaut wird

Die automatische Abnahme des Test-Alarms akzeptiert auf Staging vier Kanäle statt genau zwei und läuft deutsch und englisch.

## Definition of Done

Die Test-Alarm-Abnahme läuft auf Staging in Deutsch und Englisch grün, und die Sprache des Prüfkontos steht danach wieder auf dem Ausgangswert.

## Wie geprüft wird

Die Abnahme selbst läuft gegen Staging; die Rotprobe bei fehlendem E-Mail oder Telegram sowie die Sprach-Rücksetzung werden nur manuell geprüft.

## Kritische Anmerkungen

- Rotprobe (fehlt E-Mail oder Telegram, wird rot) und Sprach-Rücksetzung sind nur manuelle Schritte, kein automatischer Test.
- Zusatz zum Ticket: Prüfkonto-Sprache wird für den Lauf umgestellt; alle Fälle laufen in EN, nicht nur der Versandfall.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
