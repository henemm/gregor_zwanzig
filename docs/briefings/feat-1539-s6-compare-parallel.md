---
spec_file: docs/specs/modules/feat_1539_s6_compare_parallel.md
spec_sha256: 52905cee86ffc0a352cecfdc2a77e427952f4272fe0a9cca9d6bd462f860531c
spec_frozen_sha256: 2a9f5b94f8b4e0296c18eca5cc680ad4cd7d50b74703a968c7c2bf691d14dc9d
---

# PO-Briefing: feat-1539-s6-compare-parallel

- **Spec:** docs/specs/modules/feat_1539_s6_compare_parallel.md
- **Issue:** #1539
- **Erstellt:** 2026-10-30

## Was gebaut wird

Die beiden Ortsvergleich-Alarme (Änderung und amtliche Warnung) holen ihre Daten für alle Orte gleichzeitig statt nacheinander.

## Definition of Done

Beide Alarme melden dieselben Treffer in gleicher Reihenfolge wie vorher, ein Quellenausfall gilt nie als Entwarnung, und die Abrufe laufen nachweislich überlappend.

## Wie geprüft wird

Tests mit künstlichen Verzögerungen belegen Überlappung, Reihenfolge, Fehlerverhalten, Fristen und Nutzertrennung; die echte Beschleunigung im Betrieb belegen sie nicht.

## Kritische Anmerkungen

- Wirkung nur im Produktivbetrieb messbar, nicht auf Staging; der Gewinn bleibt klein (typisch 2 bis 6 Orte, höchstens drei gleichzeitig).
- Neu ist eine Zeitgrenze (60 Sekunden je Vergleich, 180 Sekunden je Lauf); bei Überschreitung zählt der Ort bzw. der Vergleich als gescheitert, sichtbar im Protokoll.
- Ticket #1539 bleibt offen (Nutzer-Verteilung im Takt folgt als S7); Warnungen erhalten eine eigene Abruf-Begrenzung, kleine Ergänzung ohne Ticketforderung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
