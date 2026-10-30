---
spec_file: docs/specs/modules/feat_2347_s4_paritaets_e2e.md
spec_sha256: b1fdf014257314277d59eca5aafebe743c00467d142da6b0c61f360c3fd9cf57
spec_frozen_sha256: 19ac279fbfed0b590eb163b2ead9a45dda28ed716b254778d99230e8018cc7e2
---

# PO-Briefing: feat-2347-s4-paritaets-e2e-altlast-leer

- **Spec:** docs/specs/modules/feat_2347_s4_paritaets_e2e.md
- **Issue:** #2347
- **Erstellt:** 2026-10-30

## Was gebaut wird

Die letzten reinen Vergleichs-Browsertests werden mit den Trip-Tests zusammengelegt, gelöscht oder als "nur Vergleich" begründet.

## Definition of Done

Fertig ist es, wenn die Liste offener Vergleichs-Altlasten leer ist, alle Prüfungen grün sind und der Produktions-Selbsttest besteht.

## Wie geprüft wird

Gemeinsame Tests für Trip und Vergleich laufen in der CI; sechs Rest-Tests laufen nur auf Staging.

## Kritische Anmerkungen

- Hub-Übersicht ist doppelt gebaut, keine erlaubte Vergleichs-Eigenheit, wird nur geparkt.
- Spec weicht von der Analyse ab: Mehrere Dateien bleiben gekürzt statt gelöscht.
- Weit über Zeilenlimit (Override); rote Trip-Fälle wahrscheinlich, Produktfix im selben Ticket.

## Freigabe-Frage

Soll die doppelt gebaute Hub-Übersicht vorerst als Vergleichs-Ausnahme gelten, oder ein eigenes Angleich-Ticket bekommen?

## Ampel

Ampel: rot
