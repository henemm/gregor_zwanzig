---
spec_file: docs/specs/modules/rework_3399_vorlage_aufloesung.md
spec_sha256: 252e23a909750d0b13bd780a6c503242cef37253d5485bbcb84c8b46ba008763
spec_frozen_sha256: 695acb8868ed99f358d9dc161d10bf854d1b4613e70bce6a1a931def639e5c22
---

# PO-Briefing: rework-3399-s2-kopie

- **Spec:** docs/specs/modules/rework_3399_vorlage_aufloesung.md (Scheibe S2)
- **Issue:** #3399
- **Erstellt:** 2026-11-26

## Was gebaut wird

Beim Anlegen eines Vergleichs als Kopie übernimmt die Kopie die vom Server bestimmte Wetter-Vorlage der Quelle.

## Definition of Done

Die Kopie zeigt sofort dieselbe Vorlage wie die Quelle; fällt der Server aus, öffnet der Editor trotzdem mit allen übrigen Werten.

## Wie geprüft wird

Automatische Tests mit dem echten Server-Rechner belegen Vorlage und Fehlerfall; die Anzeige im Browser prüft nur ein Live-Test gegen Staging.

## Kritische Anmerkungen

- Bei Serverfehler erhält die Kopie still die Vorlage Allgemein statt der Quellvorlage; kein Hinweis an den Nutzer.
- Unbekannte Vorlagen der Quelle werden künftig zu Allgemein, bisher wörtlich übernommen; Spec nennt das gewollt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
