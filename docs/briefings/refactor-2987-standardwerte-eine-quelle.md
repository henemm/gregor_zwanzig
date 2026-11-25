---
spec_file: docs/specs/modules/refactor_2987_standardwerte_eine_quelle.md
spec_sha256: aba7193aadbf009d9a17d16b216b47a9fe5c1a32b4a50d81ad54f14385162778
spec_frozen_sha256: ae82f33b59753e9a29e983f6bf019164ab54f9545d599d1128ab90fb66ae1c18
---

# PO-Briefing: refactor-2987-standardwerte-eine-quelle

- **Spec:** docs/specs/modules/refactor_2987_standardwerte_eine_quelle.md
- **Issue:** #2987
- **Erstellt:** 2026-11-25

## Was gebaut wird

Die Startwerte beim Anlegen eines Trips kommen aus einer gemeinsamen Quelle; für Nutzer ändert sich nichts Sichtbares.

## Definition of Done

Ein mit Standardwerten angelegter Trip zeigt Zustellung 07:00/18:00, beide Briefings an, nur E-Mail aktiv; Produktion ausgeliefert, Selbsttest erfolgreich.

## Wie geprüft wird

Automatische Tests vergleichen das Gesendete mit festen Sollwerten, gezielte Verfälschungen müssen auffallen; nicht geprüft werden Bestandsdaten mit leerer Zeit.

## Kritische Anmerkungen

- Umfang ca. 305 Zeilen in 6 Dateien, über der Richtgrenze; die Freigabe deckt bis 320 Zeilen ab.
- Einzige Verhaltensabweichung: leere oder ungültige Zeit ergibt 07:00/18:00; über die Bedienung nicht erreichbar.
- Löschen der Alt-Bausteine und weitere Zeit-Literale bleiben ausdrücklich draussen (Issue 3020).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
