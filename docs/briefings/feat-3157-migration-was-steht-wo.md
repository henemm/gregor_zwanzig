---
spec_file: docs/specs/modules/feat_3157_migration_placements.md
spec_sha256: ee126ba7509810d9d0cf2ae56768f2e95bac34d50f54b389e1992d5bffe023a0
spec_frozen_sha256: 559935cf57867120c78521bd14d7dea4b2ea34fd9a206804a182ec6cab98f0b9
---

# PO-Briefing: feat-3157-migration-was-steht-wo

- **Spec:** docs/specs/modules/feat_3157_migration_placements.md
- **Issue:** #3157
- **Erstellt:** 2026-11-21

## Was gebaut wird

Deine 21 bestehenden Trips und Orts-Vergleiche werden einmalig ins neue „Was steht wo“-Format umgestellt, mit Probelauf und Sicherung.

## Definition of Done

Alle 21 Abos tragen die neue Tabelle, ein zweiter Probelauf findet nichts mehr, Sicherungen liegen vor, und der Selbsttest auf Produktion ist fehlerfrei.

## Wie geprüft wird

Automatische Tests prüfen Probelauf, Sicherung, Nutzertrennung und Wiederholbarkeit; der echte Produktionslauf wird nur von Hand nachgewiesen, nicht automatisch getestet.

## Kritische Anmerkungen

- Deine Freigabe gilt zugleich für zwei sichtbare Änderungen: Nur-Text-Mails folgen der HTML-Form (13 Trips), E-Mail und Telegram übernehmen die SMS-Reihenfolge (1 Trip, 3 Vergleiche).
- Das Entfernen der alten Felder und Lese-Wege ist abgespalten (#3237); der Altpfad bleibt vorerst bestehen.

## Freigabe-Frage

Bist du mit den beiden sichtbaren Änderungen (Nur-Text-Form, SMS-Reihenfolge in E-Mail und Telegram) für deine 14 betroffenen Abos einverstanden?

## Ampel

Ampel: rot
