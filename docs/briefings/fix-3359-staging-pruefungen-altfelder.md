---
spec_file: docs/specs/modules/fix_3359_e2e_pruefungen_ohne_altfelder.md
spec_sha256: 34c3a0a7fcc031a44bb3d18159501a06ff98c5027bfde88dbee98199ec2e14e1
spec_frozen_sha256: a3f178df12c8290742682f0e4158d5a3b8b8c319d099bc6116151d1189577e6c
---

# PO-Briefing: fix-3359-staging-pruefungen-altfelder

- **Spec:** docs/specs/modules/fix_3359_e2e_pruefungen_ohne_altfelder.md
- **Issue:** #3359
- **Erstellt:** 2026-11-25

## Was gebaut wird

Automatische Browser-Prüfungen nutzen nicht mehr die zehn veralteten Einstellungen, sondern nur noch "Was steht wo"; das Produkt bleibt unverändert.

## Definition of Done

Die zwei roten Prüfungen laufen auf Staging grün, jede umgestellte Prüfung wird bei absichtlichem Fehler rot, alle CI-Checks sind grün.

## Wie geprüft wird

Prüfungen laufen auf Staging und lokal, ein Gegentest verfälscht jede gezielt; unbelegt bleibt, wenn Karte und Server gemeinsam zu viele Haken zeigen.

## Kritische Anmerkungen

- Umfang größer als verlangt: 13 statt 2 Prüfdateien; Golden-C-Testdaten bleiben unverändert statt umgestellt.
- Golden-C-Prüfung wird schwächer (nur Teilmengen-Vergleich); Python-Tests fangen die Restlücke.
- Kurz-SMS-Prüfung zur gefühlten Temperatur wird eventuell gestrichen; Entscheidung fällt erst im Testlauf.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
