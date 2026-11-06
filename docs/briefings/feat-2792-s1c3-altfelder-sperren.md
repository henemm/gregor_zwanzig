---
spec_file: docs/specs/modules/feat_2792_s1_profil_ampel.md
spec_sha256: bebe67fe83779bfeed3ad30c21df99f3837188eef1fb31ccc93af3e900b90b47
spec_frozen_sha256: 7c26386b2c2eb0b40a21ebe198ab0728c3cec2a6019b95bfba30eaa6f378d956
---

# PO-Briefing: feat-2792-s1c3-altfelder-sperren

- **Spec:** docs/specs/modules/feat_2792_s1_profil_ampel.md
- **Issue:** #2792
- **Erstellt:** 2026-11-05

## Was gebaut wird

Wertebereiche und SMS-Empfindlichkeits-Regler sind in Trip und Vergleich nur noch lesbar, mit Hinweis; gespeicherte Werte bleiben erhalten.

## Definition of Done

In Trip und Vergleich, Deutsch und Englisch, sind die Felder gesperrt, zeigen Altwerte samt Hinweis, und nach dem Speichern stehen die Werte unverändert da.

## Wie geprüft wird

Komponenten- und Funktionstests prüfen Sperre, Hinweistexte und Datenerhalt; die Zwei-Nutzer-Prüfung der gespeicherten Datei erfolgt erst im Staging-Test.

## Kritische Anmerkungen

- Die Alarm-Empfindlichkeit im Wertebereiche-Reiter bleibt bearbeitbar (gehört laut Ticket zu S2); der Reiter ist also nicht ganz gesperrt.
- Bis zum Umschalt-Schnitt S1c-4 wirken Altwerte weiter, sind aber nicht änderbar.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
