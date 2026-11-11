---
spec_file: docs/specs/modules/fix_1972_zonenwechsel_browsernachweis.md
spec_sha256: 42932ec6dd743f965ed127188686f332c6be2acb18f8c6c54ba8dbcf50027984
spec_frozen_sha256: 6f39d0d4ae6adb0a605b97fd2bac916bd6bdc6e5d43e6cd115cbd9e6d78ab3ec
---

# PO-Briefing: fix-1972-zonenwechsel-browsernachweis

- **Spec:** docs/specs/modules/fix_1972_zonenwechsel_browsernachweis.md
- **Issue:** #1972
- **Erstellt:** 2026-11-11

## Was gebaut wird

Ein automatischer Browsertest belegt, dass die Konto-Seite „Nächste Prüfung" in Wien und New York unterschiedliche Uhrzeiten zeigt.

## Definition of Done

Der neue Test ist auf der Testumgebung grün, der bestehende Test bleibt grün, und drei absichtlich eingebaute Fehler machen ihn rot.

## Wie geprüft wird

Zwei Browser mit Zeitzone Wien und New York sehen einen eingespielten Festtermin; nicht belegt wird, dass der echte Scheduler Termine liefert.

## Kritische Anmerkungen

- Gelöst durch Umschreiben der Serverantwort im Browser, nicht über einen der drei vorgeschlagenen Wege; Produktcode bleibt unverändert.
- Dass die Serverzone nie sichtbar wird, bleibt ungeprüft und nur durch Bauweise gesichert (als Einschränkung dokumentiert).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
