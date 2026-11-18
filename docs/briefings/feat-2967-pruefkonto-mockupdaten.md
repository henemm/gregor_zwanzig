---
spec_file: docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md
spec_sha256: 2b4113d7459122648ecffda6cb403d28e83584c41b1e1e476312ebe95ccbe4fe
spec_frozen_sha256: 53a6f451b2fe1e3e966ab855b4194a368dd5065d03d274a75964d187b9fa10d0
---

# PO-Briefing: feat-2967-pruefkonto-mockupdaten

- **Spec:** docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md
- **Issue:** #2967
- **Erstellt:** 2026-11-18

## Was gebaut wird

Ein Testkonto auf Staging bekommt automatisch die Beispieldaten des Mockups: Trip GR221 Mallorca, Vergleich Münsterland und alle vier verbundenen Kanäle.

## Definition of Done

Das Skript läuft zweimal fehlerfrei, der Abgleich zeigt keine Scheinabweichungen aus Kontounterschieden mehr, und alle 247 Einträge sind gelöst oder neu zugeordnet.

## Wie geprüft wird

Automatische Tests mit simuliertem Server prüfen Daten, Wiederholbarkeit, Produktionsschutz und Nutzertrennung; Abgleich und Kanalverbindung werden nur live auf Staging nachgewiesen.

## Kritische Anmerkungen

- Echte Abweichungen (Reihenfolge „Nicht im Briefing", Vorlage „allgemein", Rückadresse-Datum) bleiben sichtbar und werden eigene Folge-Tickets.
- Premium-SMS-Datum ist nicht wie im Mockup fest, sondern der Laufzeitpunkt; sonst würde der Zustand nach 30 Tagen kippen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
