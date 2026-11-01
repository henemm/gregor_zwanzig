---
spec_file: docs/specs/modules/fix_2314_restfenster_date_today.md
spec_sha256: 8a43336cea47d40652475eaeab64e37e05a468afc58f15222ff610c67b3be30c
spec_frozen_sha256: 3e0c15735260e231f7e1834a3d1650e331c7a6e8bc6de5ae2df307aecccd3369
---

# PO-Briefing: fix-2314-restfenster-date-today

- **Spec:** docs/specs/modules/fix_2314_restfenster_date_today.md
- **Issue:** #2314
- **Erstellt:** 2026-11-01

## Was gebaut wird

Zwei Tests rechnen nachts mit dem falschen Tag und werden korrigiert; zusätzlich läuft die Qualitätsprüfung täglich automatisch um 00:30 UTC.

## Definition of Done

Beide Tests sind in der Normal- und der Nachtzeit-Simulation grün, und der erste automatische Nachtlauf nach dem Merge ist grün.

## Wie geprüft wird

Die beiden Tests werden vorher rot, nachher grün gemessen; der tägliche Zeitplan selbst wird erst am Morgen nach dem Merge nachgewiesen.

## Kritische Anmerkungen

- Täglicher Zeitplan (ein CI-Lauf pro Tag) war nicht verlangt und ist laut Spec noch nicht vom PO entschieden.
- Ursprungs-Issue nicht im Wortlaut gelesen, nur über das Kontext-Dokument; Abgleich mit dessen Akzeptanzkriterien unvollständig.
- AC-5 und AC-7 (Zeitplan-Eintrag, kein Produktivcode) haben keinen automatischen Test, nur Sichtprüfung.

## Freigabe-Frage

Soll die Qualitätsprüfung dauerhaft jeden Tag um 00:30 UTC automatisch laufen, mit einem zusätzlichen CI-Lauf pro Tag?

## Ampel

Ampel: rot
