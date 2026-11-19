---
spec_file: docs/specs/modules/feat_2968_elementliste_en_zuordnung.md
spec_sha256: d250908670d6aad6aaf7560a69054d207246adc4d412ed4d036ae8e1932677f0
spec_frozen_sha256: ee2b57bd7e351d7fd7851438c281c668310da7380f1c0e553632d1b56f38e8d0
---

# PO-Briefing: feat-2968-en-katalogtexte

- **Spec:** docs/specs/modules/feat_2968_elementliste_en_zuordnung.md
- **Issue:** #2968
- **Erstellt:** 2026-11-19

## Was gebaut wird

Der englische Seitenabgleich erkennt deutlich mehr Texte als prüfbar, statt sie als Lücke zu melden.

## Definition of Done

Die Restlücken liegen unter dem Ausgangswert 1022, jede hat einen anderen Besitzer als dieses Ticket, alle Prüfungen laufen grün.

## Wie geprüft wird

Tests gegen den echten Katalog belegen jede Regel samt Gegenbeispiel; ob die App selbst richtiges Englisch zeigt, prüfen sie nicht.

## Kritische Anmerkungen

- Abweichung: Statt Texte zu ergänzen, wird der Zuordner verbessert; rund 540 Lücken bleiben, gleiche Prüftiefe wie Deutsch nur teilweise.
- Nachträglich ergänzt, nicht verlangt: Regeln für Zeichen-Texte und mehrere gültige englische Varianten.

## Freigabe-Frage

Genügt es, dass rund 540 Einträge als Lücke mit neuem Besitzer bleiben, statt dass dieses Ticket sie schließt?

## Ampel

Ampel: rot
