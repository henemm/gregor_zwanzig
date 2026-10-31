---
spec_file: docs/specs/modules/feat_2347_s4_paritaets_e2e.md
spec_sha256: 3bb472f6a65e3aa22987ad6981cdb5b4e93c71d446ff6bbc14a920b084c25ba2
spec_frozen_sha256: a62806066c5becbee26de90f5b5aa266d880bfb640e8b2c9c886721da64f29ec
---

# PO-Briefing: feat-2347-s4-paritaets-e2e-altlast-leer

- **Spec:** docs/specs/modules/feat_2347_s4_paritaets_e2e.md
- **Issue:** #2347
- **Erstellt:** 2026-10-31

## Was gebaut wird

Die letzten reinen Vergleichs-Browsertests werden mit den Trip-Tests zusammengelegt, gelöscht oder als "nur Vergleich" begründet.

## Definition of Done

Fertig ist es, wenn die Liste offener Vergleichs-Altlasten leer ist, alle Prüfungen grün sind und der Produktions-Selbsttest besteht.

## Wie geprüft wird

Gemeinsame Tests für Trip und Vergleich laufen in der CI; sechs Rest-Tests laufen nur auf Staging.

## Kritische Anmerkungen

- AC-9 geändert: Beim Trip trägt die Anlege-Anfrage eine selbst erzeugte Kennung, beim Vergleich keine; entspricht dem Ist-Zustand.
- Hub-Übersicht ist doppelt gebaut, keine erlaubte Vergleichs-Eigenheit, wird nur geparkt.
- Rote Trip-Testfälle wahrscheinlich, Produktfix im selben Ticket.

## Freigabe-Frage

Soll die doppelt gebaute Hub-Übersicht vorerst als Vergleichs-Ausnahme gelten, oder ein eigenes Angleich-Ticket bekommen?

## Ampel

Ampel: rot
