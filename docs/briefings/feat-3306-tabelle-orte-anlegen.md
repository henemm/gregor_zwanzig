---
spec_file: docs/specs/modules/feat_3306_tabelle_orte_anlegen.md
spec_sha256: 2a729e1164185974aa38a5d4031a6042d337bb37912a7cbf9fa5dff7fb5d0c25
spec_frozen_sha256: 710d07222cc47b67c31ad2f4f3476ca1e0d3f6183d0931d5be07f8c990ed7fec
---

# PO-Briefing: feat-3306-tabelle-orte-anlegen

- **Spec:** docs/specs/modules/feat_3306_tabelle_orte_anlegen.md
- **Issue:** #3306
- **Erstellt:** 2026-11-24

## Was gebaut wird

Beim Anlegen eines Ortsvergleichs stellt der Nutzer die Tabelle „Was steht wo“ samt Schaltern ein, und sie wird mitgespeichert.

## Definition of Done

Ein neu angelegter Ortsvergleich zeigt im Reiter Wetter genau die beim Anlegen eingestellten Haken, Formate, Reihenfolge und Schalter, auf Produktion bestätigt.

## Wie geprüft wird

Automatische Tests und Live-Prüfung auf Staging belegen genau einen Speichervorgang, den Stand im Reiter Wetter und die Trennung zweier Nutzer.

## Kritische Anmerkungen

- Stundenverlauf und Telegram-Kurzstil sind bis zum Folgeticket #3307 an zwei Stellen einstellbar; die Karte gewinnt nur bei Änderung.
- Vorschau zeigt feste Beispielwerte, keine echten Wetterdaten.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
