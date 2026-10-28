---
spec_file: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md
spec_sha256: e649f5d3f0d659f24148a1c341811cf6be9c6cf561f72671fd2a66c9a9d17b0e
spec_frozen_sha256: 263cdaee75138dffe447fa1edbfbca351e0a408ce943b7a69ffbc22f2f3d51fa
---

# PO-Briefing: feat-2347-s3a-paritaets-e2e

- **Spec:** docs/specs/modules/feat_2347_s3a_paritaets_e2e.md
- **Issue:** #2347
- **Erstellt:** 2026-10-27

## Was gebaut wird

Alarme, Wertebereiche, Wetter-Metriken und Speichern werden für Trip und Ortsvergleich durch dieselben automatischen Browser-Tests geprüft statt nur für den Ortsvergleich.

## Definition of Done

Die sechs gemeinsamen Tests laufen für Trip und Ortsvergleich dreimal hintereinander grün, die sechs alten Ortsvergleich-Tests sind ersetzt, die Altlast-Zahl sinkt auf 34.

## Wie geprüft wird

Browser-Tests gegen den Testaufbau beweisen Speichern, Neuladen und Nutzertrennung je Trip und Ortsvergleich; Mails, Versand und echte Geräte bleiben ungeprüft.

## Kritische Anmerkungen

- Rote Trip-Fälle erzwingen Produktänderungen im selben Ticket; Umfang vorab unbekannt.
- Sechs alte Tests werden gelöscht; Verlustschutz ist Prozessprüfung, kein automatischer Test.
- Abweichung 34 statt 35 ist schlüssig begründet; Kontextdokument nennt noch 35.

## Freigabe-Frage

Geben Sie die Spec frei, obwohl rote Trip-Fälle zusätzliche Produktänderungen im selben Ticket auslösen können?
