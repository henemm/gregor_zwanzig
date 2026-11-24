---
spec_file: docs/specs/modules/rework_3278_lokaler_volllauf_parallel.md
spec_sha256: b6219017b98d833c80bbcdd4e9d0a62e26677db937c04224bd285417ef16f47a
spec_frozen_sha256: 05fe3f3cc1b4d4bf7b14acd82485f43900128ad680b079b7c494710f8a7a9c2d
---

# PO-Briefing: rework-3278-lokaler-volllauf-parallel

- **Spec:** docs/specs/modules/rework_3278_lokaler_volllauf_parallel.md
- **Issue:** #3278
- **Erstellt:** 2026-11-24

## Was gebaut wird

Der lokale Komplett-Testlauf darf künftig mit zwei parallelen Prozessen laufen, ohne dass echter Versand an Nutzer möglich wird.

## Definition of Done

Lokaler paralleler Volllauf auf dem Server ist messbar schneller als der serielle, ohne zusätzliche rote Tests, und der Prod-Selftest bleibt währenddessen grün.

## Wie geprüft wird

Automatische Tests belegen Freigabe und Sperre der Kommandoform sowie Netzsperren in beiden Prozessen; die Zeitersparnis zeigt nur eine Messung am Server.

## Kritische Anmerkungen

- Server-Messung (Zeitgewinn, Prod-Last) fehlt noch, Serverzugang wurde abgelehnt; Issue bleibt offen, Lieferung ist zunächst Teillieferung.
- Prioritätsstufe `nice` ist fest vorgeschrieben statt optional wie im Ticket; zwei Prozesse sind ungemessen gewählt.
- Die Tests der Kommando-Sperre laufen nicht in der CI, nur lokal.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
