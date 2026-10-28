---
spec_file: docs/specs/modules/feat_2347_s3b_paritaets_e2e.md
spec_sha256: 6b56ce58e55c1c0a05654dba5614365ac079683cb1504fd887814f9d92bcc408
spec_frozen_sha256: e3c8f43dcd7e8d567cb221bc2c9e8d56b7e45f0c1699891fcf64a57f464ac289
---

# PO-Briefing: feat-2347-s3b-paritaets-e2e

- **Spec:** docs/specs/modules/feat_2347_s3b_paritaets_e2e.md
- **Issue:** #2347
- **Erstellt:** 2026-10-28

## Was gebaut wird

Versand-Einstellungen, Pausieren und Briefing-Anzeige werden für Trip und Ortsvergleich durch dieselben automatischen Browser-Tests geprüft.

## Definition of Done

Vier gemeinsame Testdateien laufen für beide dreimal grün, vier alte Ortsvergleich-Dateien sind gelöscht, Altlast sinkt von 34 auf 30.

## Wie geprüft wird

Browser-Tests beweisen Speichern, Pausieren und Neuladen je Trip und Ortsvergleich; Mails, echter Versand und Geräte bleiben ungeprüft.

## Kritische Anmerkungen

- Rote Trip-Fälle erzwingen Produktänderungen im selben Ticket; Umfang vorab unbekannt.
- Briefing-Anzeige unterscheidet sich bei Trip und Ortsvergleich; Tests bilden das ab, gleichen nicht an.
- Vorschau-Fall entfällt (Reiter gestrichen); Anlege-Test bleibt bis S4 am Alt-Assistenten.

## Freigabe-Frage

Geben Sie die Spec frei, obwohl rote Trip-Fälle zusätzliche Produktänderungen im selben Ticket auslösen können?
