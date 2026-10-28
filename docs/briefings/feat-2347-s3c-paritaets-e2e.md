---
spec_file: docs/specs/modules/feat_2347_s3c_paritaets_e2e.md
spec_sha256: 505257b898d38f749e938361e9adfec17313c1f3353f3e5f76b6769c5dfffd64
spec_frozen_sha256: 2b160cde60eac18d1a5ef24a36ec6cad9dbbd48a86501a66778f58e15da2cf2a
---

# PO-Briefing: feat-2347-s3c-paritaets-e2e

- **Spec:** docs/specs/modules/feat_2347_s3c_paritaets_e2e.md
- **Issue:** #2347
- **Erstellt:** 2026-10-28

## Was gebaut wird

Der Schutz gegen Datenverlust bei zwei offenen Fenstern wird für Trip und Ortsvergleich durch dieselben Browser-Tests geprüft.

## Definition of Done

Neue gemeinsame Testdatei läuft für beide dreimal grün, die alte Ortsvergleich-Datei ist gelöscht, Altlast sinkt von 30 auf 29.

## Wie geprüft wird

Browser-Tests öffnen zwei Fenster desselben Nutzers: Fremde Änderung bleibt, eigene geht nicht verloren; Mails und Geräte ungeprüft.

## Kritische Anmerkungen

- Rote Trip-Fälle erzwingen Produktänderungen im selben Ticket; Umfang vorab unbekannt.
- Beim Pausieren kennt nur der Ortsvergleich einen Konflikt; beide werden einzeln geprüft.
- Der Orte-Fall bleibt eine eigene Ortsvergleich-Datei, weil der Trip dafür kein Gegenstück hat.

## Freigabe-Frage

Geben Sie die Spec frei, obwohl rote Trip-Fälle zusätzliche Produktänderungen im selben Ticket auslösen können?
