---
spec_file: docs/specs/modules/rework_3278_lokaler_volllauf_parallel.md
spec_sha256: 196f5dad1b0379532897362adc90cfe1c9ce330637f10f30e81bf8398975bd70
spec_frozen_sha256: 9fe920fc70ad9c15e8ae3beba0e361d8691888441d9fe11c5917b9d7b433a4dc
---

# PO-Briefing: rework-3278-lokaler-volllauf-parallel

- **Spec:** docs/specs/modules/rework_3278_lokaler_volllauf_parallel.md
- **Issue:** #3278
- **Erstellt:** 2026-11-24

## Was gebaut wird

Der lokale Komplett-Testlauf darf zusätzlich in einer genau festgelegten, sicheren Form mit zwei parallelen Prozessen laufen.

## Definition of Done

Das Prüftor lässt die parallele Form frei und blockt jede Abwandlung; Doku und Meldung nennen beide Formen; alle Tests grün.

## Wie geprüft wird

Automatische Tests belegen Freigabe, Blockade und Netzsperren in beiden Prozessen; Zeitgewinn und Serverlast werden nicht gemessen.

## Kritische Anmerkungen

- Zwei Abschlusskriterien des Tickets (schneller belegt, Prod-Dienste unbeeinträchtigt) fehlen; Messung ausgelagert in #3323, Ticket bleibt offen.
- Nur zwei Prozesse und festes niedrigeres Ausführungs-Gewicht statt wählbar 2 oder 3; ungemessen.

## Freigabe-Frage

Soll die parallele Form freigegeben werden, obwohl Zeitgewinn und Prod-Verträglichkeit erst später in #3323 gemessen werden?

## Ampel

Ampel: rot
