---
spec_file: docs/specs/modules/feat_2347_s1_paritaets_e2e.md
spec_sha256: d9df327003a5bbca117b3b4026cb33b5ab974db83ceedd4838cdad76344b4723
spec_frozen_sha256: 504aacb82ca3f84408fede19e02ff8db8c5e62c2d6dc4537c26d06e921b05a47
---

# PO-Briefing: feat-2347-paritaets-e2e

- **Spec:** docs/specs/modules/feat_2347_s1_paritaets_e2e.md
- **Issue:** #2347
- **Erstellt:** 2026-10-26

## Was gebaut wird

Tests belegen für Trip und Ortsvergleich gleiches Verhalten bei Versandzeit-Speichern und Fremdzugriff; ein Wächter stoppt unbegründete Ortsvergleich-Sondertests.

## Definition of Done

Alle Prüfungen laufen dreimal grün; Fremdzugriff wird bei beiden abgewiesen, Versandzeit bleibt gespeichert, unbegründete neue Ortsvergleich-Tests färben den Wächter rot.

## Wie geprüft wird

Tests ändern die Versandzeit, prüfen Speichern und Neuladen und versuchen Fremdschreiben mit zweitem Nutzer; Optik prüfen sie nicht.

## Kritische Anmerkungen

- Nur erste von vier Scheiben; Hub-Kopf, Anlegen, Listen und übrige Compare-Tests folgen, Ticket bleibt offen.
- Altlastliste erlaubt vorerst unbegründete Compare-Specs (Frist 24.01.2027), obwohl das Ticket für jede eine Begründung verlangt.
- Erwartete Testzahl 369 ist geschätzt, wird erst gemessen.

## Freigabe-Frage

Freigabe für diese erste Scheibe, mit Altlastliste statt sofort vollständig begründeter Compare-Tests?
