---
spec_file: docs/specs/modules/sms_nummer_verifikation.md
spec_sha256: 55324607ebb82aa5c7f73dab0c7b5262336747af42eecf5252d9f750c783f3a7
---

# PO-Briefing: feat-2406-sms-verifikation

- **Spec:** docs/specs/modules/sms_nummer_verifikation.md
- **Issue:** #2406
- **Erstellt:** 2026-09-23

## Was gebaut wird

SMS-Nummern werden erst nach Bestätigung per Code aktiv — Versand an fremde, nicht bestätigte Nummern wird verhindert.

## Definition of Done

Eine neu eingetragene SMS-Nummer verschickt erst nach Eingabe des per SMS erhaltenen Codes tatsächlich Wetter-Nachrichten; vorher bleibt die alte oder gar keine Nummer aktiv.

## Wie geprüft wird

Automatisierte Tests plus ein Live-Test im Browser auf der Testumgebung prüfen den kompletten Ablauf; Angriffsfälle mit zwei Nutzern sind eigens abgedeckt.

## Kritische Anmerkungen

- Bereits heute eingetragene, möglicherweise fremde Nummern gelten automatisch als bestätigt — der neue Schutz wirkt nur für künftige Änderungen.
- Ein falsch eingegebener Code und ein durch eine neue Anfrage ungültig gewordener Code zeigen dieselbe Fehlermeldung.

## Freigabe-Frage

Soll SMS an eine neue Nummer künftig erst nach Bestätigung per Code aktiv werden — inklusive der Einschränkung bei alten, unbestätigten Bestandsnummern?
