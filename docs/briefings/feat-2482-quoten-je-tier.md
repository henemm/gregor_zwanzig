---
spec_file: docs/specs/modules/mengen_quoten_je_tier.md
spec_sha256: 0a6e75f7ef9cf9d537c7b0ade44da131b02355e144ec8c9de2bc26ca74a6d3bc
---

# PO-Briefing: feat-2482-quoten-je-tier

- **Spec:** docs/specs/modules/mengen_quoten_je_tier.md
- **Issue:** #2482
- **Erstellt:** 2026-10-02

## Was gebaut wird

Je Tarif gibt es Obergrenzen für Trips, Ortsvergleiche und Orte; wer sie erreicht, bekommt beim Neuanlegen eine deutsche Meldung.

## Definition of Done

Ein Free-Nutzer kann keinen vierten Trip anlegen und sieht die Meldung, vorhandene Daten bleiben bearbeitbar, und /account zeigt "x von N".

## Wie geprüft wird

Automatische Tests prüfen Grenzen, zwei Nutzer, Parallelität und Ausnahmen; die sichtbare Meldung im Frontend wird nur manuell auf Staging geprüft.

## Kritische Anmerkungen

- Empfängerkanäle (im Issue verlangt) bekommen keine Quote; die Spec begründet das mit fehlender zählbarer Größe, ohne Folge-Issue.
- Grenzwerte (Free 3 Trips, 2 Ortsvergleiche, 10 Orte; Standard 15/10/50; Premium 50/30/200) sind ungeprüfte Schätzungen und brauchen Ihre Freigabe.
- Zusätze ohne Anfrage: Wiederherstellen aus dem Archiv wird geprüft, Ausnahme-Liste für Testkonten; Archivierte zählen nicht mit.

## Freigabe-Frage

Sind Sie mit den vorgeschlagenen Grenzwerten und dem Verzicht auf eine Quote für Empfängerkanäle einverstanden?
